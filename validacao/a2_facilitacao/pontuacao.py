"""Correção automática da resposta final contra o gabarito (regras determinísticas).

Extrai o último bloco JSON da saída do agente; ausente ou inválido → INCORRETO (FORMATO).
Desfechos: CORRETO | INCORRETO | NAO_ENCONTROU_DECLARADO | BLOQUEADO | TIMEOUT | ERRO_INFRA
| ERRO_INFRA_CHROME.
"""

from __future__ import annotations

import json
import re

from validacao.a1_fidelidade.extrator_chrome import extrair_json
from validacao.comum import data_iso, norm_texto, prf1, so_digitos, valor_brl

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
         "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9,
         "out": 10, "nov": 11, "dez": 12}
BLOQUEIO_RE = re.compile(r"captcha|recaptcha|n[aã]o sou um rob[oô]|fa[cç]a login|tela de login|acesso negado", re.I)
STOP = {"de", "da", "do", "das", "dos", "e", "a", "o", "para", "com", "em", "no", "na", "por", "as", "os"}


def _texto(resp) -> str:
    return json.dumps(resp, ensure_ascii=False) if not isinstance(resp, str) else resp


def numeros(texto: str) -> list[float]:
    out = []
    # O sinal de menos só vale quando não segue um dígito ou letra ("2019-2026" são dois anos).
    for m in re.finditer(r"(?<![\w])-?\d[\d.,]*|(?<=\w)\d[\d.,]*", texto or ""):
        v = valor_brl(m.group(0).rstrip(".,"))
        if v is not None:
            out.append(v)
    return out


def datas(texto: str) -> set:
    out = set()
    for m in re.finditer(r"\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}", texto or ""):
        d = data_iso(m.group(0))
        if d:
            out.add(d)
    return out


def meses(texto: str, ano: int | None = None) -> set:
    t = norm_texto(texto)
    out = set()
    for nome, n in MESES.items():
        if re.search(rf"\b{nome}\b", t):
            out.add(n)
    for m in re.finditer(r"\b(\d{1,2})/(\d{4})\b", t):
        if ano is None or int(m.group(2)) == ano:
            if 1 <= int(m.group(1)) <= 12:
                out.add(int(m.group(1)))
    if not out and isinstance(texto, str):
        for m in re.finditer(r"\b(\d{1,2})\b", t):
            if 1 <= int(m.group(1)) <= 12:
                out.add(int(m.group(1)))
    return out


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"\w+", norm_texto(s)) if w not in STOP and len(w) > 2}


def _contem_nome(texto: str, nome: str, limiar: float = 0.6) -> bool:
    alvo = _tokens(nome)
    if not alvo:
        return False
    return len(alvo & _tokens(texto)) / len(alvo) >= limiar


def pontuar(inst: dict, saida_texto: str, status_exec: str) -> dict:
    """Devolve {desfecho, sucesso, pontuacao, motivo, resposta_json}."""
    if status_exec in ("TIMEOUT", "ERRO_INFRA", "ERRO_INFRA_CHROME"):
        return {"desfecho": status_exec, "sucesso": 0, "pontuacao": 0.0, "motivo": status_exec, "resposta_json": None}
    js = extrair_json(saida_texto)
    if js is None or "resposta" not in js:
        if BLOQUEIO_RE.search(saida_texto or ""):
            return {"desfecho": "BLOQUEADO", "sucesso": 0, "pontuacao": 0.0, "motivo": "bloqueio", "resposta_json": None}
        return {"desfecho": "INCORRETO", "sucesso": 0, "pontuacao": 0.0, "motivo": "FORMATO", "resposta_json": None}
    resp, encontrada = js.get("resposta"), js.get("encontrada")
    txt = _texto(resp)
    obs = str(js.get("observacao") or "")
    tipo = inst["pontuacao"]["tipo"]
    g = inst["gabarito"]

    if tipo == "abstencao":
        ok = encontrada is False or (encontrada in (None, "false") and not numeros(txt))
        return _d(ok, 1.0 if ok else 0.0, "abstenção" if ok else "respondeu com valor", js)
    if encontrada is False:
        des = "BLOQUEADO" if BLOQUEIO_RE.search(obs) else "NAO_ENCONTROU_DECLARADO"
        return {"desfecho": des, "sucesso": 0, "pontuacao": 0.0, "motivo": obs[:200], "resposta_json": js}

    p = inst["pontuacao"]
    if tipo == "objeto_data":
        ok_data = g["data"] in datas(txt)
        ok_obj = _contem_nome(txt, g["objeto"], 0.7)
        return _d(ok_data and ok_obj, (ok_data + ok_obj) / 2, f"data={ok_data} objeto={ok_obj}", js)
    if tipo == "documento_data":
        fontes = " ".join(map(str, js.get("fontes") or [])) + " " + txt
        ok_doc = any(u.split("?")[0] in fontes or _id_drive(u) and _id_drive(u) in fontes for u in g["documentos"])
        ok_data = g["data"] in datas(txt)
        return _d(ok_doc and ok_data, (ok_doc + ok_data) / 2, f"documento={ok_doc} data={ok_data}", js)
    if tipo == "numero":
        alvo = g["valor"]
        nums = numeros(txt)
        if "tolerancia_rel" in p:
            ok = any(abs(n - alvo) <= p["tolerancia_rel"] * abs(alvo) for n in nums)
        else:
            ok = any(abs(n - alvo) <= p.get("tolerancia_abs", 0) + 1e-9 for n in nums)
        return _d(ok, float(ok), f"esperado {alvo}; lidos {nums[:6]}", js)
    if tipo == "conjunto_fornecedores":
        docs_resp = {so_digitos(m) for m in re.findall(r"\d[\d./-]{10,}\d", txt)}
        achados = []
        for f in g["fornecedores"]:
            achados.append(f["doc"] in docs_resp or _contem_nome(txt, f["nome"], 0.6))
        tp = sum(achados)
        n_resp = max(len(resp) if isinstance(resp, list) else 1, tp)
        prec = tp / n_resp if n_resp else 0.0
        rev = tp / len(achados) if achados else 0.0
        f1 = 2 * prec * rev / (prec + rev) if prec + rev else 0.0
        return _d(f1 == 1.0, f1, f"F1={f1:.2f}", js)
    if tipo == "topk":
        k = p.get("k", 5)
        acertos = sum(1 for nome in g["itens"] if _contem_nome(txt, nome, 1.0))
        prop = acertos / k
        return _d(prop == 1.0, prop, f"{acertos}/{k} no top-{k}", js)
    if tipo == "conjunto_meses":
        prev = meses(txt, inst["parametros"].get("ano"))
        m = prf1(sorted(prev), g["meses"])
        return _d(m["f1"] == 1.0, m["f1"], f"meses lidos {sorted(prev)} esperado {g['meses']}", js)
    if tipo == "categorica":
        t = norm_texto(txt)
        cats = [c for c in ("acima", "abaixo", "igual") if re.search(rf"\b{c}\b", t)]
        ok = cats == [g["categoria"]]
        return _d(ok, float(ok), f"lido {cats} esperado {g['categoria']}", js)
    if tipo == "prazo_dias":
        ok = g["valor"] in [int(n) for n in numeros(txt) if float(n).is_integer()]
        return _d(ok, float(ok), f"esperado {g['valor']}", js)
    return _d(False, 0.0, f"regra desconhecida {tipo}", js)


def _id_drive(u: str):
    m = re.search(r"/d/([A-Za-z0-9_-]{10,})", u or "")
    return m.group(1) if m else None


def _d(ok: bool, pont: float, motivo: str, js) -> dict:
    return {"desfecho": "CORRETO" if ok else "INCORRETO", "sucesso": int(bool(ok)), "pontuacao": float(pont),
            "motivo": motivo, "resposta_json": js}
