"""
Coleta de cotações da CEASA/PR POR VARIEDADE (tabela ceasa_pr_cotacoes).

Complementa o PROHORT/CONAB (chat/prohort_collector.py), que só traz ~48 produtos
genéricos. A CEASA/PR publica produto + variedade + classificação + embalagem
(ex.: "TANGERINA PONKAN MEDIA cx 20 kg", "TANGERINA MONTEN/BERGAM cx 20 kg") com o
"preço mais comum" do dia em cada unidade atacadista do Paraná.

Fonte oficial:
  CEASA/PR — Evolução dos Preços de Hortigranjeiros
  https://celepar7.pr.gov.br/ceasa/cotprod_evolucao.asp  (form POST → result_evolucao_precos.asp)

Formato (confirmado por inspeção):
  - HTML windows-1252; tabela com colunas: Data | Unidade(=descrição+embalagem) |
    Curitiba | Maringá | Londrina | Foz do Iguaçu | Cascavel   ("-" = sem cotação).
  - Preço em R$ por EMBALAGEM, decimal com vírgula.
  - "(Todos os Produtos)" (cmbProdutos=-1) exige janela curta: a fonte recomenda 2 a 5 dias.
  - POST precisa ir direto em https (o http responde 302 e o redirect vira GET → erro 500).

Uso:
    python -m chat.ceasa_pr_collector          # últimos 7 dias
    python -m chat.ceasa_pr_collector 90       # backfill de 90 dias
"""

import re
import sys
import time
import logging
import unicodedata
from datetime import date, datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://celepar7.pr.gov.br/ceasa"
FORM_URL = f"{BASE_URL}/cotprod_evolucao.asp"
RESULT_URL = f"{BASE_URL}/result_evolucao_precos.asp"

JANELA_DIAS = 3        # dias por requisição "Todos os Produtos" (fonte recomenda 2–5)
PAUSA_SEG = 1.5        # cortesia entre requisições ao servidor público
LOTE_UPSERT = 500

# Cabeçalho da tabela (sem acento, minúsculo) → chave guardada em `unidade`.
UNIDADES = {
    "curitiba": "CURITIBA",
    "maringa": "MARINGA",
    "londrina": "LONDRINA",
    "foz do iguacu": "FOZ DO IGUACU",
    "cascavel": "CASCAVEL",
}

_RE_DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
# Embalagem com peso no fim: "cx 20 kg", "bj 200 g", "un 1,8 kg", "mç 250 g"
_RE_EMB_PESO = re.compile(r"^(?P<nome>.*?)\s+(?P<emb>[^\s\d]{1,4})\s+(?P<num>\d+(?:,\d+)?)\s*(?P<un>kg|g)$", re.I)


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _limpar(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("&nbsp;", " ")).strip()


def _preco(valor: str) -> float | None:
    s = valor.strip()
    if not s or s == "-":
        return None
    try:
        return round(float(s.replace(".", "").replace(",", ".")), 2)
    except ValueError:
        return None


def parse_descricao(descricao: str) -> dict:
    """
    Separa "TANGERINA PONKAN MEDIA cx 20 kg" em
    produto='tangerina', variedade='ponkan media', embalagem='cx 20 kg', peso_kg=20.0.

    O nome vem em MAIÚSCULAS e a embalagem em minúsculas; quando não há peso reconhecível
    (ex.: "cx c/ 30 dz"), a embalagem começa no primeiro token com letra minúscula.
    """
    d = _limpar(descricao)
    nome, embalagem, peso = d, None, None

    m = _RE_EMB_PESO.match(d)
    if m and not m.group("emb").isupper():
        nome = m.group("nome")
        num = float(m.group("num").replace(",", "."))
        un = m.group("un").lower()
        embalagem = f"{m.group('emb')} {m.group('num')} {un}"
        peso = num if un == "kg" else num / 1000
    elif d.endswith(" kg") and d[:-3].isupper():
        nome, embalagem, peso = d[:-3], "kg", 1.0
    else:
        tokens = d.split(" ")
        for i, t in enumerate(tokens):
            if i > 0 and any(ch.islower() for ch in t):
                nome, embalagem = " ".join(tokens[:i]), " ".join(tokens[i:])
                break

    nome_norm = sem_acento(nome).lower().strip()
    produto, _, variedade = nome_norm.partition(" ")
    return {
        "produto": produto,
        "variedade": variedade.strip() or None,
        "embalagem": embalagem,
        "peso_kg": round(peso, 3) if peso else None,
    }


def parse_html(html: str) -> list[dict]:
    """Extrai as linhas de cotação (uma por data × descrição × unidade com preço)."""
    colunas: list[str | None] | None = None
    registros: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S | re.I):
        celulas = [_limpar(re.sub(r"<[^>]+>", " ", c))
                   for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)]
        if not celulas:
            continue
        chaves = [UNIDADES.get(sem_acento(c).lower()) for c in celulas]
        if sum(1 for k in chaves if k) >= 2:
            # Cabeçalho das unidades. Pode vir sem as colunas Data/Unidade (linha própria):
            # os preços são sempre as ÚLTIMAS colunas, então alinha pela direita.
            colunas = [k for k in chaves if k]
            continue
        if colunas is None or not _RE_DATA.match(celulas[0]) or len(celulas) < 2 + len(colunas):
            continue
        data_iso = datetime.strptime(celulas[0], "%d/%m/%Y").date().isoformat()
        descricao = celulas[1]
        partes = parse_descricao(descricao)
        for unidade, valor in zip(colunas, celulas[-len(colunas):]):
            preco = _preco(valor)
            if preco is None:
                continue
            peso = partes["peso_kg"]
            registros.append({
                "data_coleta": data_iso,
                "unidade": unidade,
                "descricao": descricao,
                **partes,
                "preco": preco,
                "preco_kg": round(preco / peso, 2) if peso else None,
            })
    return registros


def _buscar_janela(client: httpx.Client, ini: date, fim: date) -> str:
    resp = client.post(RESULT_URL, data={
        "dataIni": ini.strftime("%d/%m/%Y"),
        "dataFim": fim.strftime("%d/%m/%Y"),
        "cmbProdutos": "-1",               # (Todos os Produtos)
        "btPesquisar": "Pesquisar",
    }, headers={"Referer": FORM_URL})
    resp.raise_for_status()
    return resp.content.decode("cp1252", errors="replace")


def _upsert_lotes(supabase, registros: list[dict]) -> int:
    inseridos = 0
    for i in range(0, len(registros), LOTE_UPSERT):
        lote = registros[i: i + LOTE_UPSERT]
        try:
            supabase.table("ceasa_pr_cotacoes").upsert(
                lote, on_conflict="data_coleta,unidade,descricao"
            ).execute()
            inseridos += len(lote)
        except Exception as e:
            logger.error(f"Erro no upsert CEASA/PR lote {i}: {e}")
    return inseridos


def _registrar_status(supabase, **campos) -> None:
    """Best-effort: falha aqui nunca derruba a coleta (mesma filosofia do PROHORT)."""
    try:
        supabase.table("ceasa_pr_status").upsert({"id": 1, **campos}, on_conflict="id").execute()
    except Exception as e:
        logger.warning(f"Não foi possível gravar ceasa_pr_status (ignorado): {e}")


def coletar_ceasa_pr(dias: int = 7) -> dict:
    """Coleta os últimos `dias` dias (todas as variedades, 5 unidades) e faz upsert idempotente."""
    from chat.db import get_supabase_client

    supabase = get_supabase_client()
    agora = lambda: datetime.now(timezone.utc).isoformat()
    hoje = date.today()
    inicio = hoje - timedelta(days=dias - 1)

    total, data_max, falhas = 0, None, []
    with httpx.Client(timeout=120, follow_redirects=False) as client:
        client.get(FORM_URL)   # abre sessão ASP (cookie) antes do POST
        ini = inicio
        while ini <= hoje:
            fim = min(ini + timedelta(days=JANELA_DIAS - 1), hoje)
            try:
                registros = parse_html(_buscar_janela(client, ini, fim))
            except Exception as e:
                logger.error(f"CEASA/PR {ini}–{fim}: {e}")
                falhas.append(f"{ini}:{str(e)[:80]}")
                registros = []
            # dedup do payload (mesma chave repetida derruba o upsert do PostgREST)
            unicos = {(r["data_coleta"], r["unidade"], r["descricao"]): r for r in registros}
            if unicos:
                total += _upsert_lotes(supabase, list(unicos.values()))
                maior = max(r["data_coleta"] for r in unicos.values())
                data_max = max(data_max or maior, maior)
            logger.info(f"CEASA/PR {ini}–{fim}: {len(unicos)} cotações")
            ini = fim + timedelta(days=1)
            time.sleep(PAUSA_SEG)

    status = "ok" if total else ("erro" if falhas else "sem_dados")
    _registrar_status(supabase, finalizado_em=agora(), data_max=data_max, linhas_inseridas=total,
                      status=status, erro="; ".join(falhas)[:500] or None)
    return {"linhas_inseridas": total, "data_max": data_max, "falhas": falhas, "status": status}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    resultado = coletar_ceasa_pr(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
    print(resultado)
    if resultado["status"] == "erro":
        sys.exit(1)
