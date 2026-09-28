"""A1.2: comparação campo a campo entre a fonte (duas leituras) e a base.

Resolução entre extratores, sem intervenção humana:
  - Playwright e Chrome concordam  → valor aceito como verdade da fonte;
  - discordam                      → DIVERGENCIA_EXTRACAO (fora da taxa principal);
  - só uma leitura disponível      → verdade = leitura Playwright, marcada LEITURA_UNICA.

Regras: texto normalizado (minúsculas, sem acento, espaços colapsados) + Levenshtein
normalizado reportado à parte; valores monetários com tolerância; datas em ISO 8601;
listas por precisão, revocação e F1.
"""

from __future__ import annotations

import shutil

from validacao.comum import (data_iso, norm_texto, prf1, similaridade_lev, so_digitos, valor_brl)

ESCALARES = [
    # (campo, tipo, coluna da base)
    ("objeto", "texto", "objeto"),
    ("modalidade", "texto", "modalidade"),
    ("situacao", "texto", "situacao"),
    ("nr_edital", "texto", "nr_edital"),
    ("dt_abertura", "data", "dt_abertura"),
    ("total_forn_participantes", "inteiro", "total_forn_participantes"),
    ("total_forn_retiraram_edital", "inteiro", "total_forn_retiraram_edital"),
]
LISTAS = ["itens", "participantes", "vencedores", "empenhos"]
CATEGORICOS = ["modalidade", "situacao"]
# Campos consumidos pelas tarefas da A2 (restrição do sorteio; seção 4.2.2)
CAMPOS_A2 = ["objeto", "dt_abertura", "itens", "vencedores", "participantes", "empenhos"]


def _escalar(tipo: str, v):
    if v is None or (isinstance(v, float) and v != v):
        return None
    if tipo == "texto":
        s = norm_texto(v)
        return s or None
    if tipo == "data":
        return data_iso(v)
    if tipo == "inteiro":
        x = valor_brl(v)
        return int(round(x)) if x is not None else None
    return v


def _num(v, casas=2):
    x = valor_brl(v)
    return round(x, casas) if x is not None else None


def lista_fonte(det: dict, campo: str) -> list:
    if det is None:
        return []
    if campo == "itens":
        return [(norm_texto(i.get("descricao")), norm_texto(i.get("unidade")), _num(i.get("quantidade"), 3),
                 _num(i.get("valor_unitario"))) for i in det.get("itens", [])]
    if campo == "participantes":
        return sorted({so_digitos(p.get("doc")) for p in det.get("participantes", []) if so_digitos(p.get("doc"))})
    if campo == "vencedores":
        return sorted({so_digitos(i.get("cnpj")) for i in det.get("itens", []) if len(so_digitos(i.get("cnpj"))) >= 11})
    if campo == "empenhos":
        return [(str(so_digitos(e.get("numero"))).lstrip("0"), _num(e.get("valor")))
                for e in det.get("empenhos", []) if so_digitos(e.get("numero"))]
    return []


def lista_base(proc: dict, campo: str) -> list:
    if campo == "itens":
        return [(norm_texto(i.get("descricao")), norm_texto(i.get("unidade_medida")),
                 _num(i.get("qt_solicitada"), 3), _num(i.get("valor_unitario"))) for i in proc["itens"]]
    if campo == "participantes":
        return sorted(set(proc["participantes"]))
    if campo == "vencedores":
        return sorted(set(proc["vencedores"]))
    if campo == "empenhos":
        return [(str(so_digitos(e.get("nr_empenho"))).lstrip("0"), _num(e.get("valor_empenhado")))
                for e in proc["empenhos"]]
    return []


def _desc_compativel(a: str, b: str) -> bool:
    """A base herdada do portal JSF guarda a descrição truncada na 1ª vírgula ('bebida lactea,');
    a fonte atual traz a descrição completa. Compatível = uma é prefixo da outra."""
    a, b = (a or "").rstrip(" ,.;"), (b or "").rstrip(" ,.;")
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def prf1_itens(base: list, fonte: list, tol: float) -> dict:
    """Pareamento guloso: mesma quantidade, valor unitário dentro da tolerância e descrição
    compatível (prefixo). A unidade de medida é comparada à parte (abreviação × extenso)."""
    livres = list(range(len(fonte)))
    pares = 0
    for d, _u, q, v in base:
        for j in livres:
            fd, _fu, fq, fv = fonte[j]
            # Quantidade vazia na tela (credenciamentos) equivale a 0 na base.
            if (q or 0.0) == (fq or 0.0) and v is not None and fv is not None and abs(v - fv) <= tol and _desc_compativel(d, fd):
                livres.remove(j)
                pares += 1
                break
    p = pares / len(base) if base else (1.0 if not fonte else 0.0)
    r = pares / len(fonte) if fonte else (1.0 if not base else 0.0)
    return {"precisao": p, "revocacao": r, "f1": (2 * p * r / (p + r)) if p + r else 0.0}


def _iguais_escalar(tipo, a, b, tol) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if tipo in ("monetario",):
        return abs(a - b) <= tol
    return a == b


def comparar_processo(chave: str, proc: dict, pw: dict | None, ch: dict | None, cfg: dict,
                      ev_dir=None, cache_dir=None) -> list[dict]:
    tol = cfg["a1"]["tolerancia_monetaria"]
    lic = proc["licitacao"]
    base_comum = {"chave": chave, "ano": lic.get("ano"), "modalidade_estrato": lic.get("modalidade"),
                  "origem": proc["origem"], "itens_legado": proc["itens_legado"],
                  "leitura_chrome": ch is not None}
    linhas = []
    for campo, tipo, col in ESCALARES:
        vp = _escalar(tipo, (pw or {}).get(campo))
        vc = _escalar(tipo, ch.get(campo)) if ch is not None else None
        vb = _escalar(tipo, lic.get(col))
        concord = None if ch is None else _iguais_escalar(tipo, vp, vc, tol)
        if ch is not None and not concord:
            status, verdade = "DIVERGENCIA_EXTRACAO", None
        else:
            verdade = vp
            status = "CORRESPONDE" if _iguais_escalar(tipo, verdade, vb, tol) else "DIVERGE"
        linhas.append({**base_comum, "campo": campo, "tipo": tipo, "valor_fonte": verdade, "valor_playwright": vp,
                       "valor_chrome": vc, "valor_base": vb, "concordancia_extratores": concord,
                       "status": status,
                       "similaridade_lev": similaridade_lev(verdade, vb) if tipo == "texto" and status != "DIVERGENCIA_EXTRACAO" else None,
                       "precisao": None, "revocacao": None, "f1": None})
    for campo in LISTAS:
        lp, lb = lista_fonte(pw, campo), lista_base(proc, campo)
        lc = lista_fonte(ch, campo) if ch is not None else None
        medir = (lambda x, y: prf1_itens(x, y, tol)) if campo == "itens" else prf1
        concord = None if lc is None else medir(lp, lc)["f1"] == 1.0
        if lc is not None and not concord:
            status, m = "DIVERGENCIA_EXTRACAO", {"precisao": None, "revocacao": None, "f1": None}
        else:
            m = medir(lb, lp)   # previsto = base, real = fonte
            status = "CORRESPONDE" if m["f1"] == 1.0 else "DIVERGE"
        linhas.append({**base_comum, "campo": campo, "tipo": "lista", "valor_fonte": len(lp),
                       "valor_playwright": len(lp), "valor_chrome": len(lc) if lc is not None else None,
                       "valor_base": len(lb), "concordancia_extratores": concord, "status": status,
                       "similaridade_lev": None, "precisao": m.get("precisao"), "revocacao": m.get("revocacao"),
                       "f1": m.get("f1")})
    # Derivado (fora da taxa global): soma dos valores totais dos itens.
    sp = sum(valor_brl(i.get("valor_total")) or 0 for i in (pw or {}).get("itens", []))
    sb = sum(float(i.get("valor_total") or 0) for i in proc["itens"])
    linhas.append({**base_comum, "campo": "soma_valor_itens", "tipo": "derivado", "valor_fonte": round(sp, 2),
                   "valor_playwright": round(sp, 2), "valor_chrome": None, "valor_base": round(sb, 2),
                   "concordancia_extratores": None,
                   "status": "CORRESPONDE" if abs(sp - sb) <= tol else "DIVERGE",
                   "similaridade_lev": None, "precisao": None, "revocacao": None, "f1": None})
    for l in linhas:
        if ch is None and l["status"] != "DIVERGENCIA_EXTRACAO":
            l["leitura"] = "LEITURA_UNICA"
        else:
            l["leitura"] = "DUPLA"
    # Evidências de divergência entre extratores: HTML e captura da página.
    if ev_dir and cache_dir and pw and any(l["status"] == "DIVERGENCIA_EXTRACAO" for l in linhas):
        ev_dir.mkdir(parents=True, exist_ok=True)
        for ext in ("html",):
            src = cache_dir / f"detalhe_{pw.get('id_portal')}.{ext}"
            if src.exists():
                shutil.copy2(src, ev_dir / f"{chave.replace('/', '-').replace(' ', '_')}.{ext}")
    return linhas


def processo_verificado(linhas: list[dict]) -> dict:
    ok = sorted({l["campo"] for l in linhas if l["status"] == "CORRESPONDE"})
    return {"campos_ok": ok, "todos_campos_a2": all(c in ok for c in CAMPOS_A2)}
