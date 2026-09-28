"""A1.2: segunda leitura independente da página de detalhe, pelo Claude in Chrome.

O agente abre a URL, lê a tela e devolve JSON no esquema fixo, copiando os valores como
aparecem (sem converter formatos). O resultado é normalizado para a mesma estrutura do
extrator Playwright, para a comparação campo a campo.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from validacao import claude_chrome as cc
from validacao.comum import ler_json, norm_processo, salvar_json

ESQUEMA = {
    "processo": "texto do título 'Detalhes Licitacao - ...' sem o prefixo",
    "objeto": "Licitação/Contratação",
    "modalidade": "Modalidade da Contratação",
    "situacao": "Situação do Processo",
    "nr_edital": "Nº Edital",
    "dt_abertura": "Data Abertura Edital",
    "total_forn_retiraram_edital": "Total de Forn. que Retiraram o Edital",
    "total_forn_participantes": "Total de Fornecedores Participantes",
    "participantes": [{"doc": "CPF/CNPJ", "razao": "Razão Social"}],
    "itens": [{"descricao": "Item", "quantidade": "Quantidade", "unidade": "Unidade Medida",
               "fornecedor": "Fornecedor/Contratado", "cnpj": "CNPJ",
               "valor_unitario": "Valor Unitário", "valor_total": "Valor Total"}],
    "empenhos": [{"numero": "Num Empenho", "credor": "Nome Contratado", "doc": "CNPJ",
                  "valor": "Empenhado"}],
    "arquivos": [{"nome": "Documento", "url": "endereço do link Download"}],
}

PROMPT = """Abra {url}. Leia a página e os documentos listados nela.
Use a aba que já existe no grupo do navegador (tabs_context_mcp) e navegue nela; não crie abas novas.
Não navegue para outras páginas além dos links desta página.
Devolva SOMENTE um JSON no esquema abaixo, copiando os valores exatamente
como aparecem na tela (sem converter formatos):
{esquema}
Campos que não aparecem na página devem ser null.
Listas devem conter todas as linhas das tabelas correspondentes, na ordem da tela.
Não abra os arquivos para download: para "arquivos", informe o nome e o endereço do link."""


def extrair_json(texto: str):
    """Último objeto JSON válido do texto (aceita bloco ```json)."""
    if not texto:
        return None
    blocos = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", texto, flags=re.S)
    # Objetos com chaves balanceadas; preferência: o que termina por último e, entre esses,
    # o que começa primeiro (o objeto externo, não um aninhado).
    achados = []
    for ini in (m.start() for m in re.finditer(r"\{", texto)):
        prof, em_str, esc = 0, False, False
        for i in range(ini, len(texto)):
            ch = texto[i]
            if em_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    em_str = False
                continue
            if ch == '"':
                em_str = True
            elif ch == "{":
                prof += 1
            elif ch == "}":
                prof -= 1
                if prof == 0:
                    achados.append((i, -ini, texto[ini:i + 1]))
                    break
    candidatos = list(reversed(blocos)) + [c for _, _, c in sorted(achados, reverse=True)]
    for c in candidatos:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def ler_detalhe(url: str, cfg: dict, dir_trabalho: Path, dir_saida: Path, tentativas: int = 2) -> dict:
    """Executa o agente e devolve {status, dados|None, meta}. Cache em disco."""
    m = re.search(r"id=(\d+)", url)
    ident = m.group(1) if m else re.sub(r"\W", "_", url)[-40:]
    arq = dir_saida / f"chrome_{ident}.json"
    em_cache = ler_json(arq)
    if em_cache and em_cache.get("status") == "OK":
        return em_cache
    prompt = PROMPT.format(url=url, esquema=json.dumps(ESQUEMA, ensure_ascii=False, indent=1))
    ultimo = None
    for n in range(tentativas + 1):
        saida = dir_saida / f"chrome_{ident}_t{n}.jsonl"
        meta = cc.executar(prompt, cfg, dir_trabalho / ident, saida, cfg["a1"].get("timeout_chrome_s", 600),
                           max_turns=max(20, int(cfg["a2"]["max_turns"])))
        ev = cc.ler_eventos(saida)
        final = cc.resultado_final(ev) or {}
        dados = extrair_json(final.get("result") or "")
        if meta["status"] == "OK" and dados is not None:
            res = {"status": "OK", "dados": normalizar(dados), "meta": meta, "log": saida.name,
                   "custo_usd": final.get("total_cost_usd"), "turnos": final.get("num_turns")}
            salvar_json(arq, res)
            return res
        ultimo = {"status": meta["status"] if meta["status"] != "OK" else "FORMATO", "dados": None,
                  "meta": meta, "log": saida.name}
        if meta["status"] not in ("ERRO_INFRA_CHROME", "ERRO_INFRA", "FORMATO", "OK"):
            break
    salvar_json(arq, ultimo)
    return ultimo


def normalizar(d: dict) -> dict:
    """Estrutura igual à do extrator Playwright (valores ainda como texto da tela)."""
    def lista(k):
        v = d.get(k)
        return v if isinstance(v, list) else []
    return {
        "processo": norm_processo(d.get("processo") or ""),
        "objeto": d.get("objeto"), "modalidade": d.get("modalidade"), "situacao": d.get("situacao"),
        "nr_edital": d.get("nr_edital"), "dt_abertura": d.get("dt_abertura"),
        "total_forn_retiraram_edital": d.get("total_forn_retiraram_edital"),
        "total_forn_participantes": d.get("total_forn_participantes"),
        "participantes": [x for x in lista("participantes") if isinstance(x, dict)],
        "itens": [x for x in lista("itens") if isinstance(x, dict)],
        "empenhos": [x for x in lista("empenhos") if isinstance(x, dict)],
        "arquivos": [x for x in lista("arquivos") if isinstance(x, dict)],
    }
