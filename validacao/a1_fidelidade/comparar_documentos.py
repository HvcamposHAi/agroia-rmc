"""A1.3: documentos. Disponibilidade, integridade e cobertura.

A base não guarda hash dos arquivos (docs/ESQUEMA.md). A integridade é avaliada por:
tamanho em bytes (contra `tamanho_bytes` da base e contra o arquivo do portal), número de
páginas e similaridade do texto extraído (Jaccard sobre 5-gramas de palavras).
O SHA-256 do download atual é registrado para execuções futuras.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from validacao import estado
from validacao.comum import (LimiteTaxa, get_com_backoff, jaccard, ngramas, norm_texto, salvar_json,
                             ler_json, sessao_http, sha256_bytes, similaridade_lev)


def _id_drive(url: str) -> str | None:
    m = re.search(r"/d/([A-Za-z0-9_-]{10,})", url or "") or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", url or "")
    return m.group(1) if m else None


def _analisar_pdf(conteudo: bytes) -> dict:
    out = {"paginas": None, "texto_chars": None, "erro_pdf": None}
    try:
        import fitz
        with fitz.open(stream=conteudo, filetype="pdf") as doc:
            out["paginas"] = doc.page_count
            texto = "\n".join(p.get_text() for p in doc)
        out["texto_chars"] = len(texto)
        out["_texto"] = texto
    except Exception as e:  # noqa: BLE001
        out["erro_pdf"] = str(e)[:200]
    return out


class Baixador:
    def __init__(self, cfg: dict, cache: Path):
        self.cfg = cfg
        self.s = sessao_http(cfg)
        self.lim = LimiteTaxa(cfg["acesso"]["intervalo_min_s"])
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(cfg["a1"]["tamanho_max_download_mb"]) * 1024 * 1024

    def baixar(self, url: str, rotulo: str) -> dict:
        chave = sha256_bytes(url.encode())[:20]
        meta_arq = self.cache / f"{chave}.json"
        meta = ler_json(meta_arq)
        if meta is not None:
            return meta
        alvo = url
        did = _id_drive(url) if "drive.google" in url else None
        if did:
            alvo = f"https://drive.usercontent.google.com/download?id={did}&export=download&confirm=t"
        r, erro = get_com_backoff(self.s, alvo, self.cfg, self.lim, stream=True)
        meta = {"url": url, "url_baixada": alvo, "rotulo": rotulo, "status_http": None, "content_type": None,
                "tamanho": None, "sha256": None, "paginas": None, "texto_chars": None, "erro": erro,
                "truncado": False}
        if r is not None:
            meta["status_http"] = r.status_code
            meta["content_type"] = r.headers.get("content-type")
            if r.ok:
                buf = bytearray()
                for bloco in r.iter_content(1 << 16):
                    buf += bloco
                    if len(buf) > self.max_bytes:
                        meta["truncado"] = True
                        break
                conteudo = bytes(buf)
                meta["tamanho"] = len(conteudo) if not meta["truncado"] else None
                meta["sha256"] = sha256_bytes(conteudo) if not meta["truncado"] else None
                if conteudo[:4] == b"%PDF" and not meta["truncado"]:
                    (self.cache / f"{chave}.pdf").write_bytes(conteudo)
                    info = _analisar_pdf(conteudo)
                    texto = info.pop("_texto", "")
                    meta.update(info)
                    (self.cache / f"{chave}.txt").write_text(texto, encoding="utf-8")
                elif b"<html" in conteudo[:2000].lower():
                    meta["erro"] = "resposta HTML (arquivo indisponível ou exige confirmação)"
            r.close()
        meta["_texto_arq"] = f"{chave}.txt"
        salvar_json(meta_arq, meta)
        return meta

    def ngramas(self, meta: dict) -> set:
        p = self.cache / meta.get("_texto_arq", "")
        return ngramas(p.read_text(encoding="utf-8")) if p.is_file() else set()


def vinculo_suspeito(nome_doc: str | None, chave: str | None) -> bool | None:
    """True quando o nome do arquivo traz um ano diferente do ano do processo a que está ligado
    (ex.: 'DS_62_-_FAAC_-_2020.pdf' ligado ao DS 62/2021). None se o nome não tem ano."""
    anos = re.findall(r"(?<!\d)(20[0-3]\d)(?!\d)", nome_doc or "")
    m = re.search(r"/(\d{4})$", chave or "")
    if not anos or not m:
        return None
    return m.group(1) not in anos


def disponivel(meta: dict) -> bool:
    return bool(meta.get("status_http") == 200 and not meta.get("erro"))


def comparar(run_id: str, cfg: dict, snap, amostra_det: dict[str, dict], dir_a1: Path, dir_cache: Path) -> dict:
    """amostra_det: chave → detalhe Playwright (com 'arquivos')."""
    b = Baixador(cfg, dir_cache / "docs")
    lim_proc = int(cfg["a1"]["limite_documentos_por_processo"])
    docs_base = snap.df("documentos_licitacao")
    chunks = snap.df("pdf_chunks")
    com_chunks = set(chunks["documento_id"].dropna().astype(int)) if not chunks.empty else set()
    lics = snap.licitacoes.set_index("id")
    linhas = []

    # 1) Disponibilidade de todos os documentos referenciados na base.
    estado.evento(run_id, "a1", f"documentos: verificando {len(docs_base)} arquivos da base")
    for d in docs_base.to_dict("records"):
        url = d.get("url_publica") or d.get("storage_path")
        chave = lics.loc[d["licitacao_id"], "chave"] if d["licitacao_id"] in lics.index else None
        meta = b.baixar(url, "base") if url else {"erro": "sem URL"}
        tam_base = d.get("tamanho_bytes")
        linhas.append({
            "lado": "BASE", "chave": chave, "documento_id": d["id"], "nome": d.get("nome_doc") or d.get("nome_arquivo"),
            "url": url, "status_http": meta.get("status_http"), "content_type": meta.get("content_type"),
            "disponivel": disponivel(meta), "tamanho": meta.get("tamanho"),
            "tamanho_base": int(tam_base) if pd.notna(tam_base) else None,
            "tamanho_confere_base": (meta.get("tamanho") == int(tam_base)) if meta.get("tamanho") and pd.notna(tam_base) else None,
            "paginas": meta.get("paginas"), "sha256": meta.get("sha256"), "tem_chunks_rag": int(d["id"]) in com_chunks,
            "na_amostra": chave in amostra_det, "par_portal": None, "sim_nome": None, "jaccard_texto": None,
            "mesmo_tamanho_portal": None, "mesmo_sha_portal": None, "mesmas_paginas_portal": None,
            "vinculo_suspeito": vinculo_suspeito(d.get("nome_doc") or d.get("nome_arquivo"), chave),
            "erro": meta.get("erro")})

    # 2) Documentos do portal nos processos da amostra + pareamento com a base.
    for chave, det in amostra_det.items():
        arquivos = (det or {}).get("arquivos", [])[:lim_proc]
        metas_portal = []
        for a in arquivos:
            m = b.baixar(a["url"], "portal")
            metas_portal.append((a, m))
            linhas.append({"lado": "PORTAL", "chave": chave, "documento_id": None, "nome": a.get("nome"),
                           "url": a["url"], "status_http": m.get("status_http"), "content_type": m.get("content_type"),
                           "disponivel": disponivel(m), "tamanho": m.get("tamanho"), "tamanho_base": None,
                           "tamanho_confere_base": None, "paginas": m.get("paginas"), "sha256": m.get("sha256"),
                           "tem_chunks_rag": None, "na_amostra": True, "par_portal": None, "sim_nome": None,
                           "jaccard_texto": None, "mesmo_tamanho_portal": None, "mesmo_sha_portal": None,
                           "mesmas_paginas_portal": None, "erro": m.get("erro"), "tem_par_base": False})
        base_proc = [l for l in linhas if l["lado"] == "BASE" and l["chave"] == chave]
        for lb in base_proc:
            mb = b.baixar(lb["url"], "base")
            ng_b = b.ngramas(mb)
            melhor = None
            for a, mp in metas_portal:
                sn = similaridade_lev(lb["nome"], a.get("nome"))
                jt = jaccard(ng_b, b.ngramas(mp)) if ng_b else None
                score = (jt if jt is not None else 0) + 0.5 * sn
                if melhor is None or score > melhor[0]:
                    melhor = (score, a, mp, sn, jt)
            if melhor and (melhor[3] >= 0.8 or (melhor[4] or 0) >= 0.5):
                _, a, mp, sn, jt = melhor
                lb.update({"par_portal": a["url"], "sim_nome": round(sn, 4),
                           "jaccard_texto": round(jt, 4) if jt is not None else None,
                           "mesmo_tamanho_portal": (lb["tamanho"] == mp.get("tamanho")) if lb["tamanho"] else None,
                           "mesmo_sha_portal": (lb["sha256"] == mp.get("sha256")) if lb["sha256"] else None,
                           "mesmas_paginas_portal": (lb["paginas"] == mp.get("paginas")) if lb["paginas"] else None})
                for l in linhas:
                    if l["lado"] == "PORTAL" and l["url"] == a["url"]:
                        l["tem_par_base"] = True
    df = pd.DataFrame(linhas)
    df.to_csv(dir_a1 / "documentos.csv", index=False, encoding="utf-8")

    base = df[df["lado"] == "BASE"]
    portal = df[df["lado"] == "PORTAL"]
    base_am = base[base["na_amostra"]]
    res = {
        "base_total": int(len(base)), "base_disponiveis": int(base["disponivel"].sum()),
        "base_tamanho_confere": int((base["tamanho_confere_base"] == True).sum()),  # noqa: E712
        "base_tamanho_verificavel": int(base["tamanho_confere_base"].notna().sum()),
        "base_com_ano_no_nome": int(base["vinculo_suspeito"].notna().sum()),
        "base_vinculo_suspeito": int((base["vinculo_suspeito"] == True).sum()),  # noqa: E712
        "base_vinculo_suspeito_lista": [f"{r.chave} ← {r.nome}" for r in base[base["vinculo_suspeito"] == True].itertuples()],  # noqa: E712
        "rag_docs_com_chunks": int(base["tem_chunks_rag"].sum()),
        "rag_cobertura": float(base["tem_chunks_rag"].mean()) if len(base) else None,
        "amostra_portal_docs": int(len(portal)), "amostra_portal_disponiveis": int(portal["disponivel"].sum()) if len(portal) else 0,
        "amostra_portal_com_par_base": int(portal.get("tem_par_base", pd.Series(dtype=bool)).fillna(False).sum()) if len(portal) else 0,
        "amostra_base_docs": int(len(base_am)), "amostra_base_com_par_portal": int(base_am["par_portal"].notna().sum()),
        "amostra_jaccard_mediana": float(base_am["jaccard_texto"].dropna().median()) if base_am["jaccard_texto"].notna().any() else None,
        "amostra_mesmo_sha": int((base_am["mesmo_sha_portal"] == True).sum()),  # noqa: E712
        "amostra_mesmas_paginas": int((base_am["mesmas_paginas_portal"] == True).sum()),  # noqa: E712
    }
    salvar_json(dir_a1 / "documentos.json", res)
    return res
