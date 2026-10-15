"""Linha de base dos contratos de não impacto (plano v3, E0) e comparação.

Mede o que nenhuma etapa do pacote pauta/safra/projeção pode mudar:
  - hash das listas de ferramentas do agente (TOOLS_SCHEMA, PRODUTOR_TOOLS_SCHEMA);
  - hash dos prompts de sistema;
  - SHA-256 de requirements-api.txt e Dockerfile;
  - rotas da API (caminho + métodos);
  - definição das views (função SQL contrato_viewdefs, se aplicada; senão, colunas);
  - assinatura das tabelas antigas (contagens só podem crescer, pela coleta diária).

Uso:
  python scripts/linha_base_contratos.py                      # grava validacao/relatorios/base_<data>.json
  python scripts/linha_base_contratos.py --comparar ARQ.json  # sai 1 se algum contrato mudou
  python scripts/linha_base_contratos.py --sem-banco          # só código (CI sem credenciais)
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

VIEWS = [
    "vw_itens_agro", "vw_cruzamento_precos_ceasa", "vw_ofertas_produtores", "vw_demanda_agro_ano",
    "vw_licitacoes_agro_documentos", "v_prohort_analise", "v_prohort_baseline_24m",
    "v_prohort_serie_diaria",
]
ARQUIVOS = ["requirements-api.txt", "Dockerfile"]


def _sha(texto: str | bytes) -> str:
    if isinstance(texto, str):
        texto = texto.encode("utf-8")
    return hashlib.sha256(texto).hexdigest()


def _json_canonico(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def contratos_codigo() -> dict:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    from chat import prompts
    from chat.tools import PRODUTOR_TOOLS_SCHEMA, TOOLS_SCHEMA

    out = {
        "tools_schema": {"n": len(TOOLS_SCHEMA), "sha256": _sha(_json_canonico(TOOLS_SCHEMA)),
                         "nomes": [t["name"] for t in TOOLS_SCHEMA]},
        "produtor_tools_schema": {"n": len(PRODUTOR_TOOLS_SCHEMA),
                                  "sha256": _sha(_json_canonico(PRODUTOR_TOOLS_SCHEMA))},
        "prompts": {nome: _sha(getattr(prompts, nome))
                    for nome in ("SYSTEM_PROMPT", "PRECOS_SYSTEM_PROMPT", "PRODUTOR_SYSTEM_PROMPT")},
        "arquivos": {a: _sha((RAIZ / a).read_bytes()) for a in ARQUIVOS if (RAIZ / a).exists()},
    }
    try:
        from api.main import app
        out["rotas"] = sorted(f"{m} {r.path}" for r in app.routes
                              for m in getattr(r, "methods", None) or () if m != "HEAD")
    except Exception as e:  # a API exige variáveis de ambiente; sem elas, registra o motivo
        out["rotas"] = {"erro": f"{type(e).__name__}: {e}"[:200]}
    return out


def contratos_banco() -> dict:
    from validacao.snapshot.congelar import assinatura_rapida, cliente

    sb = cliente()
    out = {"assinatura": assinatura_rapida(sb)}
    try:
        linhas = sb.rpc("contrato_viewdefs", {"nomes": VIEWS}).execute().data
        out["views"] = {"modo": "pg_get_viewdef",
                        "def": {l["nome"]: _sha(l["definicao"]) for l in linhas}}
    except Exception as e:
        colunas = {}
        for v in VIEWS:
            try:
                d = sb.table(v).select("*").limit(1).execute().data
                colunas[v] = sorted(d[0]) if d else []
            except Exception as ev:
                colunas[v] = f"ERRO {type(ev).__name__}"
        out["views"] = {"modo": "colunas (aplicar sql/contrato_viewdefs.sql para pg_get_viewdef)",
                        "motivo": str(e)[:160], "def": colunas}
    return out


def medir(sem_banco: bool) -> dict:
    out = {"medido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "codigo": contratos_codigo()}
    if not sem_banco:
        out["banco"] = contratos_banco()
    return out


def comparar(base: dict, atual: dict) -> list[str]:
    """Lista de violações. Contagens podem crescer; todo o resto tem de ser igual."""
    erros = []
    bc, ac = base["codigo"], atual["codigo"]
    for chave in ("tools_schema", "produtor_tools_schema", "prompts", "arquivos"):
        if bc.get(chave) != ac.get(chave):
            erros.append(f"{chave} mudou")
    if isinstance(bc.get("rotas"), list) and isinstance(ac.get("rotas"), list):
        sumiram = set(bc["rotas"]) - set(ac["rotas"])
        fora = [r for r in set(ac["rotas"]) - set(bc["rotas"]) if not r.split(" ", 1)[1].startswith("/pauta")]
        if sumiram:
            erros.append(f"rotas sumiram: {sorted(sumiram)}")
        if fora:
            erros.append(f"rotas novas fora de /pauta: {sorted(fora)}")
    if "banco" in base and "banco" in atual:
        bv, av = base["banco"]["views"], atual["banco"]["views"]
        if bv["modo"] == av["modo"] and bv["def"] != av["def"]:
            erros.append("definição/colunas de views mudaram")
        ba, aa = base["banco"]["assinatura"], atual["banco"]["assinatura"]
        for t, v in ba.items():
            if isinstance(v, dict) and (aa.get(t, {}).get("linhas") or 0) < (v["linhas"] or 0):
                erros.append(f"{t} perdeu linhas: {v['linhas']} -> {aa.get(t, {}).get('linhas')}")
    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comparar", type=Path)
    ap.add_argument("--sem-banco", action="store_true")
    ap.add_argument("--saida", type=Path)
    a = ap.parse_args()

    atual = medir(a.sem_banco)
    if a.comparar:
        erros = comparar(json.loads(a.comparar.read_text(encoding="utf-8")), atual)
        for e in erros:
            print(f"VIOLAÇÃO: {e}")
        print("Contratos intactos." if not erros else f"{len(erros)} violação(ões).")
        sys.exit(1 if erros else 0)

    saida = a.saida or RAIZ / "validacao" / "relatorios" / f"base_{datetime.now():%Y-%m-%d}.json"
    saida.write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    print(saida)


if __name__ == "__main__":
    main()
