"""Busca atos oficiais no portal da Prefeitura de Curitiba e baixa os PDFs.

Fonte: Atos Públicos Municipais — https://legisladocexterno.curitiba.pr.gov.br/AtosConsultaExterna.aspx
(formulário ASP.NET; cada ato publicado no Diário Oficial Eletrônico tem um PDF assinado
digitalmente — envelope PKCS#7/CMS — do qual este script extrai o PDF e o texto).

Exemplos:
    python scripts/buscar_atos_curitiba.py --tipo PORTARIA --numero 175 --ano 2026 --orgao "SEGURANCA ALIMENTAR"
    python scripts/buscar_atos_curitiba.py --tipo PORTARIA --ano 2026 --orgao "SEGURANCA ALIMENTAR" --texto "Sacolão"
    python scripts/buscar_atos_curitiba.py --tipo RESOLUCAO --ano 2026 --orgao "SEGURANCA ALIMENTAR" --baixar docs/legislacao

Só lê o portal público. Dependências: httpx, pypdf, asn1crypto (opcional; sem ela o PDF é
recortado do envelope pelos marcadores %PDF/%%EOF).
"""

from __future__ import annotations

import argparse
import html
import io
import re
import sys
import unicodedata
from pathlib import Path

import httpx

BASE = "https://legisladocexterno.curitiba.pr.gov.br/"
URL = BASE + "AtosConsultaExterna.aspx"
PREFIXO = "ctl00$cphMasterPrincipal$"
UA = {"User-Agent": "Mozilla/5.0 (pesquisa academica AgroIA-RMC/UEPG)"}
SIGLAS = {"SMSAN": "SECRETARIA MUNICIPAL DE SEGURANCA ALIMENTAR E NUTRICIONAL"}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").upper()


def _ocultos(h: str) -> dict:
    return dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', h))


def _opcoes(h: str, campo: str) -> list[tuple[str, str]]:
    m = re.search(r'<select[^>]*name="[^"]*%s"[^>]*>(.*?)</select>' % campo, h, re.S)
    return [(v, html.unescape(t).strip())
            for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', m.group(1) if m else "")]


def _escolher(opcoes, termo: str | None, nome: str) -> str:
    """Valor da opção cujo texto (sem acento) é igual ao termo; senão, a única que o contém."""
    if not termo:
        return ""
    t = _sem_acento(SIGLAS.get(_sem_acento(termo), termo))
    exatas = [v for v, txt in opcoes if _sem_acento(txt) == t]
    if exatas:
        return exatas[0]
    parciais = [(v, txt) for v, txt in opcoes if t in _sem_acento(txt)]
    if len(parciais) == 1:
        return parciais[0][0]
    candidatos = ", ".join(txt for _, txt in parciais[:12]) or "nenhuma"
    sys.exit(f"{nome} '{termo}' ambíguo ou inexistente. Opções que contêm o termo: {candidatos}")


def buscar(client: httpx.Client, tipo=None, numero=None, ano=None, orgao=None, texto=None) -> list[dict]:
    h = client.get(URL).text
    filtros = {
        PREFIXO + "ddlTipoAto": _escolher(_opcoes(h, "ddlTipoAto"), tipo, "Tipo de ato"),
        PREFIXO + "txtNrAto": str(numero or ""),
        PREFIXO + "txtNrAtoFinal": "",
        PREFIXO + "txtAno": str(ano or ""),
        PREFIXO + "ddlOrigem": _escolher(_opcoes(h, "ddlOrigem"), orgao, "Órgão"),
        PREFIXO + "txtTextoBuscado": texto or "",
    }
    r = client.post(URL, data={**_ocultos(h), **filtros,
                               "__EVENTTARGET": PREFIXO + "lnbPesquisar", "__EVENTARGUMENT": ""})
    r.raise_for_status()
    total = re.search(r"Encontrados\s+(\d+)\s+registros", html.unescape(re.sub(r"<[^>]+>", " ", r.text)))
    atos = []
    for linha in re.findall(r'<tr class="grid_(?:Row|AlternatingRow)">(.*?)</tr>', r.text, re.S):
        def campo(nome):
            m = re.search(r'lblGrid%s">(.*?)</span>' % nome, linha, re.S)
            return html.unescape(re.sub(r"<br\s*/?>", " ", m.group(1))).strip() if m else ""
        fid = re.search(r"downloadFile\(&quot;(\d+)&quot;", linha)
        numero_data = campo("NumeroOficial").split()
        atos.append({
            "tipo": campo("Tipo"), "numero": numero_data[0] if numero_data else "",
            "data": numero_data[1] if len(numero_data) > 1 else "",
            "orgao": campo("Orgao"), "status": campo("Status"), "diario_oficial": campo("DiarioOficial"),
            "sumula": campo("Sumula"), "situacao": campo("Situacao"), "id": fid.group(1) if fid else None,
        })
    if total and int(total.group(1)) > len(atos):
        print(f"AVISO: {total.group(1)} registros no portal; só a 1ª página ({len(atos)}) foi lida. "
              "Refine a busca.", file=sys.stderr)
    return atos


def baixar_pdf(client: httpx.Client, ato_id: str) -> bytes:
    """PDF original de um ato: desembrulha o envelope de assinatura digital (PKCS#7)."""
    bruto = client.get(BASE + f"AtosConsultaExternaDownload.aspx?Id={ato_id}&tipo=ass").content
    if bruto[:4] == b"%PDF":
        return bruto
    try:
        from asn1crypto import cms
        return cms.ContentInfo.load(bruto)["content"]["encap_content_info"]["content"].native
    except Exception:
        ini, fim = bruto.find(b"%PDF"), bruto.rfind(b"%%EOF")
        if ini < 0:
            raise RuntimeError(f"ato {ato_id}: download não contém PDF")
        return bruto[ini:fim + 5] if fim > ini else bruto[ini:]


def texto_do_pdf(pdf: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tipo", help="ex.: PORTARIA, DECRETO, RESOLUCAO")
    ap.add_argument("--numero", type=int)
    ap.add_argument("--ano", type=int)
    ap.add_argument("--orgao", help='trecho do nome do órgão, ex.: "SEGURANCA ALIMENTAR"')
    ap.add_argument("--texto", help="texto buscado no ato (mínimo de 3 caracteres)")
    ap.add_argument("--baixar", type=Path, help="pasta onde salvar PDF e texto de cada ato encontrado")
    a = ap.parse_args()
    if not any([a.tipo, a.numero, a.ano, a.orgao, a.texto]):
        ap.error("informe ao menos um filtro")

    with httpx.Client(headers=UA, timeout=120, follow_redirects=True) as client:
        atos = buscar(client, a.tipo, a.numero, a.ano, a.orgao, a.texto)
        print(f"{len(atos)} ato(s) encontrado(s)")
        for ato in atos:
            print(f"- {ato['tipo']} nº {ato['numero']} de {ato['data']} | {ato['orgao']} | DOM {ato['diario_oficial']} "
                  f"| {ato['status']} | {ato['situacao']} | id {ato['id']}\n  {ato['sumula']}")
            if a.baixar and ato["id"]:
                a.baixar.mkdir(parents=True, exist_ok=True)
                base = (f"{_sem_acento(ato['tipo']).lower().replace(' ', '_')}_{ato['orgao'].lower()}_"
                        f"{ato['numero']}_{ato['data'].replace('/', '-')}_DOM{ato['diario_oficial']}")
                pdf = baixar_pdf(client, ato["id"])
                (a.baixar / f"{base}.pdf").write_bytes(pdf)
                (a.baixar / f"{base}.txt").write_text(texto_do_pdf(pdf), encoding="utf-8")
                print(f"  salvo: {a.baixar / base}.pdf e .txt")


if __name__ == "__main__":
    main()
