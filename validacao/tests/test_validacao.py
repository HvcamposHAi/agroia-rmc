"""Testes offline da validação (seção 10): normalização, comparação, extração de JSON,
parser do stream-json, KLM, amostra, estatística (contra SciPy/statsmodels e exemplos
publicados) e geração de relatório com dados sintéticos."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from validacao import comum
from validacao.a1_fidelidade import amostragem
from validacao.a1_fidelidade.comparar_campos import _desc_compativel, prf1_itens
from validacao.a1_fidelidade.extrator_chrome import extrair_json
from validacao.a2_facilitacao import klm, parser_log, pontuacao
from validacao.estatistica import multiplos, pareados, proporcoes

FIX = Path(__file__).with_name("fixtures")


# ─── normalização e comparação ───────────────────────────────────────────────
def test_norm_texto():
    assert comum.norm_texto("  AQUISIÇÃO   de  Café ") == "aquisicao de cafe"
    assert comum.norm_texto(None) == ""


def test_norm_processo():
    assert comum.norm_processo("PE 83 /2026") == "PE 83/2026"
    assert comum.norm_processo("pe 083/2026 - SMSAN/FAAC") == "PE 83/2026"
    assert comum.ano_processo("PE 3/2025") == 2025


@pytest.mark.parametrize("txt,esperado", [
    ("R$ 1.234,56", 1234.56), ("R$ 0,01", 0.01), ("120.000", 120000.0), ("3,97", 3.97),
    ("1", 1.0), ("", None), (12.5, 12.5), ("-", None)])
def test_valor_brl(txt, esperado):
    assert comum.valor_brl(txt) == esperado


def test_tolerancia_monetaria():
    a, b = comum.valor_brl("R$ 10,00"), comum.valor_brl("10.009")
    assert abs(a - 10.0) <= 0.01
    assert b == 10009.0      # separador de milhar pt-BR


def test_data_iso():
    assert comum.data_iso("03/02/2025") == "2025-02-03"
    assert comum.data_iso("2025-02-03T10:00") == "2025-02-03"
    assert comum.data_iso("x") is None


def test_levenshtein_e_similaridade():
    assert comum.levenshtein("kitten", "sitting") == 3
    assert comum.similaridade_lev("abc", "abc") == 1.0
    assert 0 < comum.similaridade_lev("pregão eletrônico", "pregao eletronic") < 1


def test_prf1_e_jaccard():
    m = comum.prf1([1, 2, 3], [2, 3, 4])
    assert m["precisao"] == pytest.approx(2 / 3) and m["revocacao"] == pytest.approx(2 / 3)
    assert comum.prf1([], [])["f1"] == 0.0 or comum.prf1([], [])["precisao"] == 1.0
    a = comum.ngramas("um dois tres quatro cinco seis")
    assert comum.jaccard(a, a) == 1.0


def test_itens_prefixo():
    assert _desc_compativel("bebida lactea,", "bebida lactea, uht, sabor chocolate,")
    base = [("bebida lactea,", "unidade", 192000.0, 0.81)]
    fonte = [("bebida lactea, uht", "un", 192000.0, 0.81)]
    assert prf1_itens(base, fonte, 0.01)["f1"] == 1.0
    assert prf1_itens(base, [("bebida lactea, uht", "un", 192000.0, 0.90)], 0.01)["f1"] == 0.0


# ─── extração do JSON final do agente ────────────────────────────────────────
def test_extrair_json():
    txt = 'Pronto.\n```json\n{"resposta": 42, "encontrada": true, "fontes": [], "observacao": "x"}\n```'
    assert extrair_json(txt)["resposta"] == 42
    assert extrair_json('texto {"a": {"b": "}"}} fim')["a"]["b"] == "}"
    assert extrair_json("sem json") is None
    assert extrair_json('{"a": 1} e depois {"resposta": "b"}')["resposta"] == "b"


# ─── parser do stream-json ───────────────────────────────────────────────────
def _linha(tipo, **kw):
    return json.dumps({"type": tipo, **kw})


def test_parser_log_sintetico(tmp_path):
    P = "mcp__claude-in-chrome__"
    uso = lambda i, n, inp: {"type": "tool_use", "id": i, "name": P + n, "input": inp}  # noqa: E731
    linhas = [
        _linha("system", subtype="init", mcp_servers=[{"name": "claude-in-chrome", "status": "connected"}]),
        _linha("assistant", message={"content": [uso("1", "gif_creator", {"action": "start_recording"})]}),
        _linha("assistant", message={"content": [uso("2", "navigate", {"url": "https://agroia-rmc.pages.dev/assistente"})]}),
        _linha("user", message={"content": [{"type": "tool_result", "tool_use_id": "2",
                                             "content": 'Tab Context: tabId 1 ("https://agroia-rmc.pages.dev/assistente")'}]}),
        _linha("assistant", message={"content": [uso("3", "computer", {"action": "left_click", "coordinate": [1, 2]}),
                                                 uso("4", "computer", {"action": "type", "text": "tomate"}),
                                                 uso("5", "computer", {"action": "scroll"}),
                                                 uso("6", "get_page_text", {})]}),
        _linha("user", message={"content": [{"type": "tool_result", "tool_use_id": "6", "content": "x" * 100}]}),
        _linha("result", subtype="success", num_turns=4, result='{"resposta": 1, "encontrada": true}',
               usage={"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 3}),
    ]
    p = tmp_path / "log.jsonl"
    p.write_text("\n".join(linhas), encoding="utf-8")
    m = parser_log.analisar(p)
    assert m["n_acoes"] == 5
    assert m["n_acoes_por_tipo"] == {"navegar": 1, "clicar": 1, "digitar": 1, "rolar": 1, "ler_pagina": 1}
    assert m["usou_chat"] is True
    assert m["tokens_entrada"] == 13 and m["turnos"] == 4
    assert m["chars_lidos"] == 100
    esperado = klm.tempo_total([{"tipo": "navegar", "url": "https://agroia-rmc.pages.dev/assistente"},
                                {"tipo": "clicar"}, {"tipo": "digitar", "texto": "tomate"}, {"tipo": "rolar"}])
    assert m["tempo_humano_klm_s"] == esperado


def test_parser_log_fixture_real():
    """Log real de sonda: só instrumentação (tabs_context_mcp) → zero ações de navegação."""
    m = parser_log.analisar(FIX / "sonda_chrome.jsonl")
    assert m["n_acoes"] == 0 and m["turnos"] == 2 and "OK" in m["texto_final"]


# ─── KLM ─────────────────────────────────────────────────────────────────────
def test_klm_operadores():
    assert klm.tempo_acao({"tipo": "clicar"}) == pytest.approx(1.35 + 1.1 + 0.2)
    assert klm.tempo_acao({"tipo": "digitar", "texto": "abc"}) == pytest.approx(1.35 + 0.8 + 3 * 0.28)
    assert klm.tempo_acao({"tipo": "rolar"}) == pytest.approx(1.3)
    assert klm.tempo_acao({"tipo": "ler_pagina"}) == 0


# ─── pontuação da A2 ─────────────────────────────────────────────────────────
def test_pontuacao_numero_e_abstencao():
    inst = {"pontuacao": {"tipo": "numero", "tolerancia_abs": 0.01}, "gabarito": {"valor": 3.97}, "parametros": {}}
    ok = pontuacao.pontuar(inst, '{"resposta": "R$ 3,97", "encontrada": true, "fontes": []}', "OK")
    assert ok["desfecho"] == "CORRETO"
    nf = pontuacao.pontuar(inst, '{"resposta": null, "encontrada": false, "observacao": "não achei"}', "OK")
    assert nf["desfecho"] == "NAO_ENCONTROU_DECLARADO"
    assert pontuacao.pontuar(inst, "sem json", "OK")["motivo"] == "FORMATO"
    assert pontuacao.pontuar(inst, "", "TIMEOUT")["desfecho"] == "TIMEOUT"
    t12 = {"pontuacao": {"tipo": "abstencao"}, "gabarito": {"abstencao": True}, "parametros": {}}
    assert pontuacao.pontuar(t12, '{"resposta": null, "encontrada": false}', "OK")["sucesso"] == 1


def test_pontuacao_meses_e_categorica():
    inst = {"pontuacao": {"tipo": "conjunto_meses"}, "gabarito": {"meses": [3, 7]}, "parametros": {"ano": 2025}}
    r = pontuacao.pontuar(inst, '{"resposta": ["março", "julho"], "encontrada": true}', "OK")
    assert r["sucesso"] == 1
    cat = {"pontuacao": {"tipo": "categorica"}, "gabarito": {"categoria": "acima"}, "parametros": {}}
    assert pontuacao.pontuar(cat, '{"resposta": "acima", "encontrada": true}', "OK")["sucesso"] == 1


# ─── amostra ─────────────────────────────────────────────────────────────────
def test_tamanho_amostra_cochran():
    r = amostragem.tamanho_amostra(838)
    n0 = 1.959964 ** 2 * 0.25 / 0.05 ** 2
    assert r["n0"] == pytest.approx(n0, rel=1e-4)
    assert r["n"] == math.ceil(n0 / (1 + (n0 - 1) / 838)) == 264
    assert amostragem.tamanho_amostra(10)["n"] <= 10


def test_alocacao_proporcional():
    estr = {"a": list(range(50)), "b": list(range(30)), "c": list(range(20))}
    al = amostragem.alocar(estr, 10)
    assert sum(al.values()) == 10 and al == {"a": 5, "b": 3, "c": 2}


def test_sorteio_reprodutivel():
    itens = [{"chave": f"P {i}/2025", "g": i % 3} for i in range(40)]
    a, _ = amostragem.sortear(itens, lambda x: str(x["g"]), 12, 7)
    b, _ = amostragem.sortear(itens, lambda x: str(x["g"]), 12, 7)
    assert [x["chave"] for x in a] == [x["chave"] for x in b] and len(a) == 12


# ─── estatística ─────────────────────────────────────────────────────────────
def test_wilson_contra_statsmodels():
    from statsmodels.stats.proportion import proportion_confint
    for k, n in ((0, 10), (7, 10), (81, 100), (10, 10)):
        r = proporcoes.wilson(k, n)
        li, ls = proportion_confint(k, n, alpha=0.05, method="wilson")
        assert r["li"] == pytest.approx(li, abs=1e-9) and r["ls"] == pytest.approx(ls, abs=1e-9)


def test_mcnemar_exato_contra_statsmodels():
    from statsmodels.stats.contingency_tables import mcnemar
    for b, c in ((9, 2), (5, 5), (12, 1), (0, 6)):
        ref = mcnemar([[10, b], [c, 10]], exact=True).pvalue
        assert pareados.mcnemar_exato(b, c)["p_valor"] == pytest.approx(ref, rel=1e-9)
    assert pareados.mcnemar_exato(0, 0)["p_valor"] == 1.0


def test_wilcoxon_contra_scipy():
    rng = np.random.default_rng(1)
    x = rng.normal(10, 2, 15)
    y = x + rng.normal(1, 1, 15)
    r = pareados.wilcoxon_pareado(list(x), list(y))
    ref = stats.wilcoxon(x, y)
    assert r["p_valor"] == pytest.approx(ref.pvalue, rel=1e-9)
    assert 0 <= r["r"] <= 1


def test_cliff_delta_exemplo():
    assert pareados.cliff_delta([1, 2, 3], [4, 5, 6]) == -1.0
    assert pareados.cliff_delta([1, 2], [1, 2]) == 0.0
    assert pareados.magnitude_cliff(0.5) == "grande"


def test_cochran_q_contra_statsmodels():
    from statsmodels.stats.contingency_tables import cochrans_q
    rng = np.random.default_rng(3)
    x = (rng.random((24, 4)) < [0.8, 0.5, 0.4, 0.6]).astype(int)
    ref = cochrans_q(x)
    r = multiplos.cochran_q(x.tolist())
    assert r["q"] == pytest.approx(ref.statistic, rel=1e-9) and r["p_valor"] == pytest.approx(ref.pvalue, rel=1e-9)


def test_friedman_contra_scipy():
    a, b, c = [1, 2, 3, 4, 5], [2, 3, 4, 5, 7], [3, 3, 5, 6, 8]
    assert multiplos.friedman(a, b, c)["p_valor"] == pytest.approx(stats.friedmanchisquare(a, b, c).pvalue)


def test_holm_contra_statsmodels():
    from statsmodels.stats.multitest import multipletests
    ps = {"H1": 0.01, "H2": 0.04, "H3": 0.03, "H5": 0.2}
    ref = multipletests(list(ps.values()), method="holm")[1]
    r = multiplos.holm(ps)
    for (k, _), pr in zip(ps.items(), ref):
        assert r[k]["p_holm"] == pytest.approx(pr)
    assert multiplos.holm({"H1": None})["H1"]["p_holm"] is None


def test_kappas():
    from sklearn.metrics import cohen_kappa_score
    a, b = list("aabbcabc"), list("abbbcacc")
    assert multiplos.cohen_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b))
    from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa
    dados = [["x", "x", "y"], ["y", "y", "y"], ["x", "y", "x"], ["x", "x", "x"]]
    tab, _ = aggregate_raters(np.array([[{"x": 0, "y": 1}[v] for v in r] for r in dados]))
    assert multiplos.fleiss_kappa(dados) == pytest.approx(fleiss_kappa(tab))


def test_poder_mcnemar():
    assert pareados.minimo_discordantes(0.05) == 6       # 2·0,5^6 = 0,031 < 0,05
    assert 0 < pareados.menor_efeito_detectavel(24, 0.5) <= 0.5


# ─── relatório com dados sintéticos ──────────────────────────────────────────
def test_relatorio_sintetico(tmp_path, monkeypatch):
    from validacao import comum as c
    from validacao.relatorios import gerar
    monkeypatch.setattr(c, "EXECUCOES", tmp_path)
    monkeypatch.setattr(gerar, "dir_execucao", lambda r: (tmp_path / r))
    run = tmp_path / "sint"
    (run / "snapshot").mkdir(parents=True)
    (run / "a1").mkdir()
    c.salvar_json(run / "snapshot" / "snapshot.json", {"hash_agregado": "ab" * 32, "tabelas": {"licitacoes": {"linhas": 5, "sha256_conteudo": "cd" * 32}}})
    censo = {"global": {"P": 10, "P_inter_B": 9, "faltantes_na_base": 1, "ausentes_no_portal": 0,
                        "nao_verificaveis_fonte_desativada": 0, "completude": 0.9, "precisao_existencia": 1.0,
                        "B_verificaveis": 9, "nao_verificados_erro_portal": 0},
             "por_ano": {"2025": {"P": 10, "P_inter_B": 9, "faltantes_na_base": 1, "ausentes_no_portal": 0,
                                  "nao_verificaveis_fonte_desativada": 0, "completude": 0.9, "precisao_existencia": 1.0}},
             "escopo_af": {"precisao_existencia": 1.0, "P_inter_B": 9, "B_verificaveis": 9}, "erros_ano": {},
             "portal_requisicoes": 20}
    c.salvar_json(run / "a1" / "resumo.json", {
        "censo": censo, "global": proporcoes.wilson(8, 10), "global_por_origem": {},
        "por_campo": {"objeto": {**proporcoes.wilson(9, 10), "divergencia_extracao": 0, "f1_medio": None,
                                 "lev_medio": 0.98, "por_origem": {}}},
        "documentos": {k: 0 for k in ("base_total", "base_disponiveis", "base_tamanho_confere", "base_tamanho_verificavel",
                                      "rag_docs_com_chunks", "amostra_portal_docs", "amostra_portal_disponiveis",
                                      "amostra_portal_com_par_base", "amostra_base_docs", "amostra_base_com_par_portal",
                                      "amostra_mesmo_sha", "amostra_mesmas_paginas")} | {"rag_cobertura": None, "amostra_jaccard_mediana": None},
        "agregados": {"por_ano": [], "nota": "Nota."}, "chrome": {"usado": False, "degradado": True, "afetados": 10},
        "amostra_n": 10, "amostra_calculo": amostragem.tamanho_amostra(9), "amostra_lida": 10,
        "concordancia_extratores": None, "divergencia_extracao_total": 0, "kappa_categoricos": {}})
    arqs = gerar.gerar("sint", partes=["A", "B"])
    assert "resultados_A.html" in arqs and "metodologia_B.md" in arqs
    md = (run / "relatorios" / "resultados_A.md").read_text(encoding="utf-8")
    assert "90,0%" in md and "Tabela 1" in md and " — " not in md
