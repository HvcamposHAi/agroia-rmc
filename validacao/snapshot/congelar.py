"""Etapa 0: snapshot congelado do Supabase em Parquet.

Cada tabela é lida por completo, ordenada pela chave configurada e gravada em Parquet.
O hash de cada tabela é calculado sobre uma serialização canônica do conteúdo (CSV
ordenado), e não sobre os bytes do Parquet, para não depender de metadados do escritor.
O hash agregado é o SHA-256 das linhas "tabela:hash" em ordem alfabética.

Uso:
  python -m validacao.snapshot.congelar --run-id RUN            # congela
  python -m validacao.snapshot.congelar --run-id RUN --reusar OUTRO_RUN
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import time
from pathlib import Path

import pandas as pd

from validacao import estado
from validacao.comum import (carimbo, carregar_config, carregar_env, dir_execucao, git_info,
                             ler_json, salvar_json, sha256_arquivo)

FILTROS = {
    # Só as cotações das unidades da CEASA-PR entram (tarefas T09 e perguntas de preço da B).
    "prohort_precos": ("origem", "ilike", "CEASA/PR%"),
}


def cliente():
    import os
    from supabase import create_client
    carregar_env()
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def ler_tabela(sb, tabela: str, ordem: list[str], omitir: list[str], pagina: int = 1000) -> pd.DataFrame:
    linhas, off = [], 0
    filtro = FILTROS.get(tabela)
    while True:
        for tentativa in range(5):
            try:
                q = sb.table(tabela).select("*")
                if filtro:
                    q = getattr(q, filtro[1])(filtro[0], filtro[2])
                for c in ordem:
                    q = q.order(c)
                dados = q.range(off, off + pagina - 1).execute().data
                break
            except Exception:
                if tentativa == 4:
                    raise
                time.sleep(2 ** (tentativa + 1))
        linhas += [{k: v for k, v in d.items() if k not in omitir} for d in dados]
        if len(dados) < pagina:
            break
        off += pagina
    df = pd.DataFrame(linhas)
    if not df.empty:
        df = df[sorted(df.columns)]
        df = df.sort_values([c for c in ordem if c in df.columns], kind="mergesort").reset_index(drop=True)
    return df


def hash_conteudo(df: pd.DataFrame) -> str:
    """SHA-256 de uma serialização canônica (colunas e linhas ordenadas, CSV)."""
    txt = df.to_csv(index=False, lineterminator="\n", date_format="%Y-%m-%dT%H:%M:%S.%f")
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def hash_agregado(hashes: dict[str, str]) -> str:
    base = "\n".join(f"{t}:{h}" for t, h in sorted(hashes.items()))
    return hashlib.sha256(base.encode()).hexdigest()


def congelar(run_id: str, cfg: dict | None = None, destino: Path | None = None) -> dict:
    cfg = cfg or carregar_config()
    destino = destino or (dir_execucao(run_id) / "snapshot")
    destino.mkdir(parents=True, exist_ok=True)
    sb = cliente()
    scfg = cfg["snapshot"]
    info = {"iniciado_em": carimbo(), "tabelas": {}, "ausentes": [], "filtros": {
        t: f"{c} {op} '{v}'" for t, (c, op, v) in FILTROS.items()}}
    hashes = {}
    tabelas = dict(scfg["tabelas"])
    for opc in scfg.get("opcionais", []):
        tabelas.setdefault(opc, ["id"])
    for tabela, ordem in tabelas.items():
        estado.evento(run_id, "snapshot", f"exportando {tabela}")
        try:
            df = ler_tabela(sb, tabela, ordem, scfg.get("omitir_colunas", {}).get(tabela, []))
        except Exception as e:  # noqa: BLE001
            if tabela in scfg.get("opcionais", []):
                info["ausentes"].append({"tabela": tabela, "erro": str(e)[:300]})
                estado.evento(run_id, "snapshot", f"{tabela} ausente no banco (opcional): {str(e)[:120]}", "aviso")
                continue
            raise
        arq = destino / f"{tabela}.parquet"
        df.to_parquet(arq, index=False)
        h = hash_conteudo(df)
        hashes[tabela] = h
        info["tabelas"][tabela] = {"linhas": int(len(df)), "colunas": list(df.columns),
                                   "sha256_conteudo": h, "sha256_arquivo": sha256_arquivo(arq)}
    info["hash_agregado"] = hash_agregado(hashes)
    info["finalizado_em"] = carimbo()
    info["git"] = git_info()
    salvar_json(destino / "snapshot.json", info)
    estado.evento(run_id, "snapshot", f"hash agregado {info['hash_agregado'][:16]}")
    return info


def reusar(run_id: str, origem_run: str) -> dict:
    origem = dir_execucao(origem_run) / "snapshot"
    info = ler_json(origem / "snapshot.json")
    if not info:
        raise FileNotFoundError(f"Snapshot inexistente em {origem}")
    destino = dir_execucao(run_id) / "snapshot"
    if destino.resolve() != origem.resolve():
        shutil.copytree(origem, destino, dirs_exist_ok=True)
    info = dict(info)
    info["reusado_de"] = origem_run
    salvar_json(destino / "snapshot.json", info)
    return info


def assinatura_rapida(sb=None) -> dict:
    """Assinatura leve da base viva (contagem + maior id), usada para verificar que a base
    não mudou durante a janela do benchmark (modo_dados = pausar_coleta)."""
    sb = sb or cliente()
    out = {}
    for t in ("licitacoes", "itens_licitacao", "participacoes", "empenhos", "documentos_licitacao",
              "fornecedores"):
        r = sb.table(t).select("id", count="exact").order("id", desc=True).limit(1).execute()
        out[t] = {"linhas": r.count, "max_id": (r.data[0]["id"] if r.data else None)}
    r = sb.table("licitacoes").select("coletado_em").order("coletado_em", desc=True).limit(1).execute()
    out["licitacoes_max_coletado_em"] = r.data[0]["coletado_em"] if r.data else None
    r = sb.table("prohort_precos").select("data_coleta").order("data_coleta", desc=True).limit(1).execute()
    out["prohort_max_data"] = r.data[0]["data_coleta"] if r.data else None
    out["hash"] = hashlib.sha256(repr(sorted(out.items())).encode()).hexdigest()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--reusar")
    ap.add_argument("--destino")
    a = ap.parse_args()
    if a.reusar:
        info = reusar(a.run_id, a.reusar)
    else:
        info = congelar(a.run_id, destino=Path(a.destino) if a.destino else None)
    print(info["hash_agregado"])


if __name__ == "__main__":
    main()
