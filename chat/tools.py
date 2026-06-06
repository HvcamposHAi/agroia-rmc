import json
import logging
import re
import time
import unicodedata
from typing import Any
from chat.db import get_supabase_client

logger = logging.getLogger(__name__)

# Categorias que NUNCA devem ser exibidas em respostas
CATEGORIAS_EXCLUIR = {"PROCESSADOS_AF", "GRAOS_CEREAIS", "LATICINIOS", "NAO_CLASSIFICADO", "OUTRO"}

_st_model = None
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 3600

def get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _st_model

def normalize_pergunta(pergunta: str) -> str:
    pergunta = pergunta.lower().strip()
    pergunta = ''.join(c for c in unicodedata.normalize('NFD', pergunta) if unicodedata.category(c) != 'Mn')
    return pergunta

def get_cached(pergunta: str) -> str | None:
    chave = normalize_pergunta(pergunta)
    if chave in _cache:
        resposta, timestamp = _cache[chave]
        if time.time() - timestamp < CACHE_TTL:
            logger.debug(f"Cache hit: {pergunta[:50]}")
            return resposta
        else:
            del _cache[chave]
    return None

def set_cache(pergunta: str, resposta: str):
    chave = normalize_pergunta(pergunta)
    _cache[chave] = (resposta, time.time())
    logger.debug(f"Cache set: {pergunta[:50]}")

def sanitizar_string(valor: str, max_length: int = 100) -> str:
    """Sanitiza strings para prevenir SQL injection básico."""
    if not valor:
        return ""
    valor = str(valor).strip()
    if len(valor) > max_length:
        valor = valor[:max_length]
    # Rejeitar patterns suspeitos (muito básico, não substitui parameterização)
    if re.search(r"[;'\"\\]", valor):
        logger.warning(f"Potentially malicious input detected: {valor[:50]}")
        raise ValueError(f"Invalid characters in input")
    return valor

def query_itens_agro(
    cultura: str | None = None,
    categoria: str | None = None,
    canal: str | None = None,
    ano: int | None = None,
    agregacao: str = "detalhado"
) -> list[dict]:
    """
    Consulta itens agrícolas de vw_itens_agro (filtrados por relevante_agro=true).
    Agregações: detalhado, por_cultura, por_canal, por_ano, por_categoria
    """
    sb = get_supabase_client()

    if agregacao == "detalhado":
        query = sb.from_("vw_itens_agro").select("*").eq("relevante_agro", True)
        if cultura:
            cultura = sanitizar_string(cultura)
            query = query.ilike("cultura", f"%{cultura}%")
        if categoria:
            categoria = sanitizar_string(categoria, 50)
            query = query.eq("categoria_v2", categoria)
        if canal:
            canal = sanitizar_string(canal, 50)
            query = query.eq("canal", canal)
        result = query.limit(50).execute()
        return result.data if result.data else []

    if agregacao == "por_cultura":
        # Otimizado: uma única query com agregação
        # Garante que está filtrando apenas items agrícolas
        items_all = sb.from_("vw_itens_agro").select(
            "cultura, categoria_v2, valor_total, valor_unitario"
        ).eq("relevante_agro", True).limit(10000).execute().data or []

        culturas_dict = {}
        for item in items_all:
            cult = item.get("cultura", "")
            cat = item.get("categoria_v2", "")
            # Excluir categorias não-agrícolas puras
            if cat in CATEGORIAS_EXCLUIR:
                continue
            if not cult:
                continue

            if cult not in culturas_dict:
                culturas_dict[cult] = {
                    "categoria_v2": item.get("categoria_v2", ""),
                    "qtd_itens": 0,
                    "valor_total": 0.0
                }

            culturas_dict[cult]["qtd_itens"] += 1
            culturas_dict[cult]["valor_total"] += float(item.get("valor_total", 0))

        resultado = []
        for cult, data in culturas_dict.items():
            qtd = data["qtd_itens"]
            resultado.append({
                "cultura": cult,
                "categoria_v2": data["categoria_v2"],
                "qtd_itens": qtd,
                "valor_total_R$": round(data["valor_total"], 2),
                "preco_medio_unit": round(data["valor_total"] / qtd if qtd > 0 else 0, 2)
            })

        return sorted(resultado, key=lambda x: x["valor_total_R$"], reverse=True)[:20]

    if agregacao == "por_canal":
        # Otimizado: uma única query
        items_all = sb.from_("vw_itens_agro").select(
            "canal, licitacao_id, valor_total"
        ).eq("relevante_agro", True).limit(10000).execute().data or []

        canais_dict = {}
        for item in items_all:
            canal = item.get("canal", "")
            if not canal:
                continue

            if canal not in canais_dict:
                canais_dict[canal] = {
                    "qtd_items": 0,
                    "licitacoes": set(),
                    "valor_total": 0.0
                }

            canais_dict[canal]["qtd_items"] += 1
            canais_dict[canal]["licitacoes"].add(item.get("licitacao_id"))
            canais_dict[canal]["valor_total"] += float(item.get("valor_total", 0))

        resultado = [
            {
                "canal": canal,
                "qtd_licitacoes": len(data["licitacoes"]),
                "qtd_itens": data["qtd_items"],
                "valor_total_R$": round(data["valor_total"], 2)
            }
            for canal, data in canais_dict.items()
        ]

        return sorted(resultado, key=lambda x: x["valor_total_R$"], reverse=True)

    if agregacao == "por_ano":
        items = sb.from_("vw_itens_agro").select(
            "dt_abertura, licitacao_id, valor_total"
        ).eq("relevante_agro", True).limit(10000).execute().data or []

        anos_dict = {}
        for item in items:
            data = item.get("dt_abertura", "")
            ano = int(data[:4]) if data else 0
            if ano not in anos_dict:
                anos_dict[ano] = {"licitacoes": set(), "itens": 0, "valor": 0}
            anos_dict[ano]["licitacoes"].add(item.get("licitacao_id"))
            anos_dict[ano]["itens"] += 1
            anos_dict[ano]["valor"] += float(item.get("valor_total", 0))

        resultado = [
            {
                "ano": ano,
                "qtd_licitacoes": len(data["licitacoes"]),
                "qtd_itens": data["itens"],
                "valor_total_R$": round(data["valor"], 2)
            }
            for ano, data in sorted(anos_dict.items(), reverse=True)
        ]
        return resultado

    if agregacao == "por_categoria":
        items = sb.from_("vw_itens_agro").select(
            "categoria_v2, licitacao_id, valor_total"
        ).eq("relevante_agro", True).limit(10000).execute().data or []

        categorias_dict = {}
        for item in items:
            cat = item.get("categoria_v2", "SEM_CATEGORIA")
            # Excluir categorias não-agrícolas puras
            if cat in CATEGORIAS_EXCLUIR:
                continue
            if cat not in categorias_dict:
                categorias_dict[cat] = {"licitacoes": set(), "itens": 0, "valor": 0}
            categorias_dict[cat]["licitacoes"].add(item.get("licitacao_id"))
            categorias_dict[cat]["itens"] += 1
            categorias_dict[cat]["valor"] += float(item.get("valor_total", 0))

        resultado = [
            {
                "categoria_v2": cat,
                "qtd_itens": data["itens"],
                "qtd_licitacoes": len(data["licitacoes"]),
                "valor_total_R$": round(data["valor"], 2)
            }
            for cat, data in sorted(categorias_dict.items(), key=lambda x: x[1]["valor"], reverse=True)
        ]
        return resultado

    return []

def query_fornecedores(
    tipo: str | None = None,
    canal: str | None = None,
    ano: int | None = None
) -> list[dict]:
    """
    Consulta fornecedores (cooperativas, associações) que participaram de licitações agrícolas.
    """
    sb = get_supabase_client()

    licitacoes = sb.from_("licitacoes").select(
        "id, canal, dt_abertura"
    ).neq("canal", "OUTRO").execute().data or []

    if tipo:
        licitacoes_filtradas = [l for l in licitacoes]
    else:
        licitacoes_filtradas = licitacoes

    if canal:
        licitacoes_filtradas = [l for l in licitacoes_filtradas if l.get("canal") == canal]

    if ano:
        licitacoes_filtradas = [
            l for l in licitacoes_filtradas
            if l.get("dt_abertura", "")[:4] == str(ano)
        ]

    licitacao_ids = [l["id"] for l in licitacoes_filtradas]
    if not licitacao_ids:
        return []

    fornecedores = sb.from_("fornecedores").select("*").execute().data or []
    if tipo:
        fornecedores = [f for f in fornecedores if f.get("tipo") == tipo]

    participacoes = sb.from_("participacoes").select(
        "fornecedor_id, licitacao_id"
    ).in_("licitacao_id", licitacao_ids).execute().data or []

    resultado_dict = {}
    for p in participacoes:
        forn_id = p.get("fornecedor_id")
        forn = next((f for f in fornecedores if f.get("id") == forn_id), None)
        if not forn:
            continue

        chave = forn_id
        if chave not in resultado_dict:
            resultado_dict[chave] = {
                "cpf_cnpj": forn.get("cpf_cnpj"),
                "razao_social": forn.get("razao_social"),
                "tipo": forn.get("tipo"),
                "licitacoes": set(),
                "canais": set()
            }

        lic_id = p.get("licitacao_id")
        resultado_dict[chave]["licitacoes"].add(lic_id)

        lic = next((l for l in licitacoes_filtradas if l["id"] == lic_id), None)
        if lic:
            resultado_dict[chave]["canais"].add(lic.get("canal", ""))

    resultado = [
        {
            "cpf_cnpj": v["cpf_cnpj"],
            "razao_social": v["razao_social"],
            "tipo": v["tipo"],
            "qtd_licitacoes": len(v["licitacoes"]),
            "canais": list(v["canais"])
        }
        for v in resultado_dict.values()
    ]

    return sorted(resultado, key=lambda x: x["qtd_licitacoes"], reverse=True)[:50]

def query_licitacoes(
    processo: str | None = None,
    canal: str | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None
) -> list[dict]:
    """
    Consulta licitações que possuem itens agrícolas relevantes.
    """
    sb = get_supabase_client()

    query = sb.from_("licitacoes").select(
        "id, processo, tipo_processo, canal, dt_abertura, situacao, objeto"
    )

    query = query.neq("canal", "OUTRO")

    if processo:
        processo = sanitizar_string(processo, 100)
        query = query.ilike("processo", f"%{processo}%")
    if canal:
        canal = sanitizar_string(canal, 50)
        query = query.eq("canal", canal)
    if ano_inicio:
        # Validar ano como inteiro
        try:
            ano_inicio = int(ano_inicio)
            if not 1900 <= ano_inicio <= 2100:
                logger.warning(f"Invalid year: {ano_inicio}")
                ano_inicio = None
            else:
                query = query.gte("dt_abertura", f"{ano_inicio}-01-01")
        except (ValueError, TypeError):
            logger.warning(f"Invalid ano_inicio: {ano_inicio}")
    if ano_fim:
        try:
            ano_fim = int(ano_fim)
            if not 1900 <= ano_fim <= 2100:
                logger.warning(f"Invalid year: {ano_fim}")
                ano_fim = None
            else:
                query = query.lte("dt_abertura", f"{ano_fim}-12-31")
        except (ValueError, TypeError):
            logger.warning(f"Invalid ano_fim: {ano_fim}")

    query = query.order("dt_abertura", desc=True).limit(50)
    result = query.execute()
    return result.data if result.data else []

def buscar_chunks_rag(
    pergunta: str,
    processo: str | None = None,
    limite: int = 5,
    min_similaridade: float = 0.3
) -> list[dict]:
    """
    Busca chunks de PDFs similares à pergunta usando embeddings vetoriais (RAG).
    Funciona sem RPC - calcula similaridade em Python via coseno.
    Retorna chunks ordenados por relevância com scores.
    """
    sb = get_supabase_client()

    try:
        import numpy as np

        pergunta_sanitizada = sanitizar_string(pergunta, 500)

        # Gerar embedding da pergunta
        model = get_st_model()
        query_embedding = model.encode(pergunta_sanitizada, convert_to_numpy=True).astype(np.float32)

        # Buscar chunks do banco
        query_select = sb.table("pdf_chunks").select(
            "id, documento_id, nome_doc, processo, chunk_text, embedding, chunk_index"
        )

        if processo:
            processo_sanitizado = sanitizar_string(processo, 100)
            query_select = query_select.ilike("processo", f"%{processo_sanitizado}%")

        result = query_select.limit(500).execute()

        if not result.data:
            return []

        # Calcular similaridade para cada chunk
        similaridades = []
        for chunk in result.data:
            if not chunk.get("embedding"):
                continue

            try:
                # Converter embedding para array
                emb = chunk["embedding"]
                if isinstance(emb, str):
                    emb = json.loads(emb)

                chunk_emb = np.array(emb, dtype=np.float32)

                # Similaridade coseno
                norm_q = np.linalg.norm(query_embedding)
                norm_c = np.linalg.norm(chunk_emb)

                if norm_q > 0 and norm_c > 0:
                    sim = float(np.dot(query_embedding, chunk_emb) / (norm_q * norm_c))

                    if sim >= min_similaridade:
                        similaridades.append({
                            "id": chunk["id"],
                            "documento_id": chunk["documento_id"],
                            "nome_doc": chunk["nome_doc"],
                            "processo": chunk["processo"],
                            "chunk_text": chunk["chunk_text"][:200],  # Truncar para resposta
                            "chunk_completo": chunk["chunk_text"],
                            "chunk_index": chunk["chunk_index"],
                            "similaridade": round(sim, 3)
                        })
            except Exception as e:
                logger.debug(f"Erro processando chunk: {e}")
                continue

        # Ordenar por similaridade e pegar top-k
        similaridades.sort(key=lambda x: x["similaridade"], reverse=True)
        return similaridades[:min(limite, 10)]

    except Exception as e:
        logger.error(f"Erro na busca RAG: {e}", exc_info=True)
        return [{"erro": f"Erro na busca semântica: {str(e)[:100]}"}]


# Manter função antiga para compatibilidade
def buscar_documentos_vetor(
    pergunta: str,
    processo: str | None = None,
    limite: int = 5
) -> list[dict]:
    """
    Compatibilidade: redireciona para buscar_chunks_rag
    """
    return buscar_chunks_rag(pergunta=pergunta, processo=processo, limite=limite)

# ─── Tools PROHORT (preços de atacado CEASA — CONAB) ────────────────────────

def _prohort_avaliacao(media30, media90, media24m=None) -> str:
    """
    Avalia o preço atual (média 30d) contra a base histórica.
    Usa a média de 24 meses quando disponível; senão, cai para a referência de 90 dias.
    """
    base, rotulo = (media24m, "24 meses") if media24m else (media90, "90 dias")
    if media30 and base:
        desvio = ((media30 - base) / base) * 100
        if desvio < -10:
            return f"ABAIXO da média histórica ({rotulo}) — preço relativamente baixo."
        if desvio > 10:
            return f"ACIMA da média histórica ({rotulo}) — preço relativamente alto."
        return f"NA MÉDIA histórica ({rotulo})."
    return "Histórico insuficiente para comparação."


def _prohort_preco_sugerido(media30, min30, max30, variacao, min24=None, max24=None) -> float | None:
    """
    Preço sugerido de venda (referência de negociação) para o produtor.
    Base = média de 30 dias; ajustada pela tendência semanal e limitada à faixa min/máx.
    - mercado em alta (>+5%): sugere +5% sobre a média (pode pedir um pouco mais);
    - mercado em queda (<-5%): mantém a média (não baixar além dela);
    - estável: a própria média.
    Por fim, limita à faixa observada em 24 meses (guardrail histórico) quando disponível.

    ATENÇÃO: esta fórmula é replicada IDÊNTICA no frontend em
    agroia-frontend/src/pages/Mercado.tsx :: precoSugerido — alterar as duas juntas.
    """
    if media30 is None:
        return None
    base = float(media30)
    if variacao is not None:
        if variacao > 5:
            base = base * 1.05
        elif variacao < -5:
            base = base  # mantém a média em mercado de queda
    if min30 is not None:
        base = max(base, float(min30))
    if max30 is not None:
        base = min(base, float(max30))
    if min24 is not None:
        base = max(base, float(min24))
    if max24 is not None:
        base = min(base, float(max24))
    return round(base, 2)


def _prohort_baseline_24m(ceasa, produto_norm) -> dict:
    """
    Busca a baseline de 24 meses (view companheira v_prohort_baseline_24m).
    Degrada graciosamente: retorna {} se a view não existir ou não houver dados.
    """
    if not ceasa or not produto_norm:
        return {}
    try:
        sb = get_supabase_client()
        res = (sb.table("v_prohort_baseline_24m")
               .select("media_24m, min_24m, max_24m, total_24m")
               .eq("ceasa", ceasa).eq("produto_norm", produto_norm).limit(1).execute())
        return res.data[0] if res.data else {}
    except Exception:
        return {}


def _prohort_linha_produto(r: dict) -> dict:
    """Monta o dict padronizado de um produto a partir de uma linha de v_prohort_analise."""
    media30, min30, max30 = r.get("media_30d"), r.get("min_30d"), r.get("max_30d")
    variacao = r.get("variacao_semanal_pct")
    b = _prohort_baseline_24m(r.get("ceasa"), r.get("produto_norm"))
    media24m, min24, max24 = b.get("media_24m"), b.get("min_24m"), b.get("max_24m")
    return {
        "produto": r.get("produto_norm"),
        "unidade": r.get("unidade") or "kg",
        "preco_min_30d": min30,
        "preco_medio_30d": media30,
        "preco_max_30d": max30,
        "preco_sugerido": _prohort_preco_sugerido(media30, min30, max30, variacao, min24, max24),
        "variacao_semanal_pct": variacao,
        "media_90d": r.get("media_90d"),
        "media_24m": media24m,
        "min_24m": min24,
        "max_24m": max24,
        "total_24m": b.get("total_24m"),
        "avaliacao": _prohort_avaliacao(media30, r.get("media_90d"), media24m),
        "ultima_cotacao": r.get("ultima_cotacao"),
    }


def prohort_consultar_preco(produto: str = "", ceasa: str = "CURITIBA") -> dict:
    """Consulta preço atual/histórico de um produto na CEASA (v_prohort_analise)."""
    produto = (produto or "").strip().lower()
    ceasa = (ceasa or "CURITIBA").strip().upper()
    if not produto:
        return {"encontrado": False, "msg": "Informe o nome do produto (ex.: tomate, alface)."}
    sb = get_supabase_client()
    res = (sb.table("v_prohort_analise").select("*")
           .ilike("produto_norm", f"%{produto}%").eq("ceasa", ceasa).execute())
    if not res.data:
        return {"encontrado": False,
                "msg": f"Sem dados de preço para '{produto}' na CEASA {ceasa}. "
                       "Tente o nome genérico (ex.: 'tomate' em vez de 'tomate italiano')."}
    return {
        "encontrado": True,
        "ceasa": ceasa,
        **_prohort_linha_produto(res.data[0]),
        "fonte": "CONAB/PROHORT (preços de atacado, referência para negociação).",
    }


def prohort_consultar_precos_lista(produtos: list = None, ceasa: str = "CURITIBA") -> dict:
    """Consulta uma LISTA de produtos de uma vez; retorna itens + não encontrados."""
    ceasa = (ceasa or "CURITIBA").strip().upper()
    if not produtos or not isinstance(produtos, list):
        return {"itens": [], "nao_encontrados": [], "msg": "Informe ao menos um produto."}
    sb = get_supabase_client()
    itens, nao_encontrados = [], []
    for p in produtos:
        termo = str(p or "").strip().lower()
        if not termo:
            continue
        res = (sb.table("v_prohort_analise").select("*")
               .ilike("produto_norm", f"%{termo}%").eq("ceasa", ceasa)
               .order("total_cotacoes", desc=True).limit(1).execute())
        if res.data:
            itens.append(_prohort_linha_produto(res.data[0]))
        else:
            nao_encontrados.append(termo)
    return {
        "ceasa": ceasa,
        "itens": itens,
        "nao_encontrados": nao_encontrados,
        "fonte": "CONAB/PROHORT (preços de atacado, referência para negociação).",
    }


def prohort_comparar_historico(produto: str = "", ceasa: str = "CURITIBA") -> dict:
    """Compara média 30d vs 90d e recomenda momento de venda."""
    produto = (produto or "").strip().lower()
    ceasa = (ceasa or "CURITIBA").strip().upper()
    if not produto:
        return {"encontrado": False, "msg": "Informe o nome do produto."}
    sb = get_supabase_client()
    res = (sb.table("v_prohort_analise")
           .select("produto_norm, media_30d, media_90d, variacao_semanal_pct, unidade, ultima_cotacao")
           .ilike("produto_norm", f"%{produto}%").eq("ceasa", ceasa).execute())
    if not res.data:
        return {"encontrado": False, "msg": f"Sem dados históricos para '{produto}' na CEASA {ceasa}."}
    r = res.data[0]
    m30, m90 = r.get("media_30d"), r.get("media_90d")
    if not m30 or not m90:
        return {"encontrado": False, "msg": "Dados históricos insuficientes para comparação."}
    desvio = round(((m30 - m90) / m90) * 100, 1)
    if desvio < -10:
        recomendacao = ("Preço atual ABAIXO da média de 90 dias. Pode não ser o melhor momento "
                        "para vender, se houver possibilidade de aguardar.")
    elif desvio > 10:
        recomendacao = ("Preço atual ACIMA da média de 90 dias. Bom momento para vender, "
                        "aproveitando o preço favorável.")
    else:
        recomendacao = "Preço dentro da faixa normal dos últimos 90 dias, sem alta ou baixa relevante."
    return {
        "encontrado": True, "produto": r.get("produto_norm"), "ceasa": ceasa,
        "unidade": r.get("unidade") or "kg", "media_30d": m30, "media_90d": m90,
        "desvio_pct": desvio, "recomendacao": recomendacao, "fonte": "CONAB/PROHORT",
    }


def prohort_ranking(limite: int = 5, ceasa: str = "CURITIBA") -> dict:
    """Top produtos por valorização semanal na CEASA."""
    limite = max(1, min(int(limite or 5), 20))
    ceasa = (ceasa or "CURITIBA").strip().upper()
    sb = get_supabase_client()
    res = (sb.table("v_prohort_analise")
           .select("produto_norm, media_30d, variacao_semanal_pct, unidade, ultima_cotacao")
           .eq("ceasa", ceasa).not_.is_("variacao_semanal_pct", "null")
           .order("variacao_semanal_pct", desc=True).limit(limite).execute())
    if not res.data:
        return {"encontrado": False,
                "msg": "Ranking indisponível (histórico semanal ainda em formação)."}
    return {
        "encontrado": True, "ceasa": ceasa,
        "ranking": [{
            "produto": r.get("produto_norm"), "preco_medio_30d": r.get("media_30d"),
            "unidade": r.get("unidade") or "kg", "variacao_semanal_pct": r.get("variacao_semanal_pct"),
        } for r in res.data],
        "fonte": "CONAB/PROHORT",
    }


# Entrepostos PROHORT coletados (mesmo contrato do coletor e do frontend).
CEASAS_BASE = [
    "SAO PAULO", "RIBEIRAO PRETO", "SAO JOSE DO RIO PRETO", "SAO JOSE DOS CAMPOS", "SOROCABA",
    "CURITIBA", "MARINGA", "FOZ DO IGUACU", "CASCAVEL", "FLORIANOPOLIS", "PORTO ALEGRE",
]


def prohort_comparar_ceasas(produto: str = "", ceasas: list = None) -> dict:
    """Compara o preço de um produto entre VÁRIAS CEASAs (todas da base, por padrão)."""
    produto = (produto or "").strip().lower()
    if not produto:
        return {"encontrado": False, "msg": "Informe o produto."}
    alvo = [str(c).strip().upper() for c in ceasas] if ceasas else CEASAS_BASE
    sb = get_supabase_client()
    res = (sb.table("v_prohort_analise").select("*")
           .ilike("produto_norm", f"%{produto}%").in_("ceasa", alvo).execute())
    if not res.data:
        return {"encontrado": False, "msg": f"Sem dados de '{produto}' nas CEASAs consultadas."}
    # uma linha por CEASA (a com mais cotações)
    por_ceasa: dict = {}
    for r in res.data:
        c = r.get("ceasa")
        if c not in por_ceasa or (r.get("total_cotacoes") or 0) > (por_ceasa[c].get("total_cotacoes") or 0):
            por_ceasa[c] = r
    itens = [{"ceasa": c, **_prohort_linha_produto(por_ceasa[c])} for c in alvo if c in por_ceasa]
    return {"encontrado": True, "produto": produto, "ceasas": itens, "fonte": "CONAB/PROHORT"}


def prohort_cruzar_prefeitura(produtos: list = None, ceasa: str = None) -> dict:
    """Cruza o preço que a prefeitura pagou nas licitações com o atacado da CEASA."""
    if not produtos or not isinstance(produtos, list):
        return {"itens": [], "msg": "Informe ao menos um produto."}
    sb = get_supabase_client()
    itens, nao_encontrados = [], []
    for p in produtos:
        termo = str(p or "").strip().lower()
        if not termo:
            continue
        q = sb.table("vw_cruzamento_precos_ceasa").select("*").ilike("produto_norm", f"%{termo}%")
        if ceasa:
            q = q.eq("ceasa", str(ceasa).strip().upper())
        try:
            res = q.execute()
        except Exception as e:
            return {"itens": [], "erro": f"View de cruzamento indisponível: {e}"}
        if not res.data:
            nao_encontrados.append(termo)
            continue
        for r in res.data:
            itens.append({
                "produto": r.get("produto_norm"),
                "ceasa": r.get("ceasa"),
                "prefeitura_rs_kg": r.get("preco_kg_prefeitura"),
                "ceasa_medio": r.get("preco_ceasa_medio"),
                "unidade_ceasa": r.get("unidade_ceasa"),
                "unidades_compativeis": r.get("unidades_compativeis"),
                "diferenca_pct": r.get("diferenca_pct"),
                "periodo_prefeitura": f"{r.get('ano_min')}-{r.get('ano_max')}",
                "n_itens_licitacao": r.get("n_itens"),
            })
    return {
        "itens": itens,
        "nao_encontrados": nao_encontrados,
        "observacao": (
            "diferenca_pct (prefeitura vs atacado) só é calculada quando as unidades são compatíveis "
            "(kg). O preço da prefeitura é a mediana histórica das licitações (período informado)."
        ),
        "fonte": "Prefeitura (licitações) × CONAB/PROHORT",
    }


# ─── PRODUTORES: cadastro de ofertas (escrita) e consulta ───────────────────

def _validar_cpf(cpf: str) -> bool:
    cpf = re.sub(r"\D", "", cpf or "")
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(cpf[n]) * ((i + 1) - n) for n in range(i))
        dig = (soma * 10) % 11
        dig = 0 if dig == 10 else dig
        if dig != int(cpf[i]):
            return False
    return True


def _validar_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r"\D", "", cnpj or "")
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(pos))
        resto = soma % 11
        dig = 0 if resto < 2 else 11 - resto
        if dig != int(cnpj[pos]):
            return False
    return True


def validar_cpf_cnpj(valor: str) -> str | None:
    """Retorna o documento só com dígitos se for CPF/CNPJ válido, senão None."""
    doc = re.sub(r"\D", "", valor or "")
    if len(doc) == 11 and _validar_cpf(doc):
        return doc
    if len(doc) == 14 and _validar_cnpj(doc):
        return doc
    return None


def registrar_oferta_produtor(
    nome: str = "",
    cpf_cnpj: str = "",
    descricao: str = "",
    quantidade: float | None = None,
    unidade: str = "kg",
    disponibilidade: str | None = None,
    preco_pretendido: float | None = None,
    municipio: str | None = None,
    contato: str | None = None,
    tipo: str = "PRODUTOR_INDIVIDUAL",
    observacoes: str | None = None,
    origem: str = "CHAT",
) -> dict:
    """
    Cadastra (upsert do produtor + insert da oferta) uma oferta de fornecimento da agricultura
    familiar. Valida CPF/CNPJ e campos obrigatórios antes de gravar.

    origem: canal de cadastro ("CHAT", "PLANILHA", ...). Default "CHAT" preserva o comportamento atual.
    """
    # Validação de obrigatórios
    faltando = [c for c, v in (("nome", nome), ("cpf_cnpj", cpf_cnpj), ("descricao", descricao)) if not (v and str(v).strip())]
    if quantidade is None or float(quantidade) <= 0:
        faltando.append("quantidade")
    if faltando:
        return {"ok": False, "erro": f"Campos obrigatórios faltando ou inválidos: {', '.join(faltando)}"}

    doc = validar_cpf_cnpj(cpf_cnpj)
    if not doc:
        return {"ok": False, "erro": "CPF/CNPJ inválido. Confira os números e tente novamente."}

    if preco_pretendido is not None and float(preco_pretendido) < 0:
        return {"ok": False, "erro": "Preço pretendido não pode ser negativo."}

    tipo = tipo if tipo in ("PRODUTOR_INDIVIDUAL", "COOPERATIVA", "ASSOCIACAO") else "PRODUTOR_INDIVIDUAL"

    sb = get_supabase_client()
    try:
        sb.table("produtores").upsert(
            {
                "cpf_cnpj": doc,
                "nome": str(nome).strip()[:200],
                "tipo": tipo,
                "municipio": (str(municipio).strip()[:120] if municipio else None),
                "contato": (str(contato).strip()[:200] if contato else None),
                "atualizado_em": "now()",
            },
            on_conflict="cpf_cnpj",
        ).execute()

        prod = sb.table("produtores").select("id, nome").eq("cpf_cnpj", doc).limit(1).execute()
        if not prod.data:
            return {"ok": False, "erro": "Não foi possível registrar o produtor."}
        produtor_id = prod.data[0]["id"]

        oferta = sb.table("ofertas_produtores").insert(
            {
                "produtor_id": produtor_id,
                "cultura": None,
                "descricao": str(descricao).strip()[:300],
                "quantidade": float(quantidade),
                "unidade": (str(unidade).strip()[:20] if unidade else "kg"),
                "disponibilidade": (str(disponibilidade).strip()[:200] if disponibilidade else None),
                "preco_pretendido": (float(preco_pretendido) if preco_pretendido is not None else None),
                "observacoes": (str(observacoes).strip()[:500] if observacoes else None),
                "status": "ATIVA",
                "origem": (str(origem).strip().upper()[:20] if origem else "CHAT"),
            }
        ).execute()

        oferta_id = oferta.data[0]["id"] if oferta.data else None
        resumo = f"{quantidade} {unidade} de {descricao}" + (f" ({disponibilidade})" if disponibilidade else "")
        return {"ok": True, "oferta_id": oferta_id, "produtor_id": produtor_id, "resumo": resumo}
    except Exception as e:
        logger.error(f"Erro ao registrar oferta: {e}", exc_info=True)
        return {"ok": False, "erro": "Erro ao gravar a oferta. Tente novamente."}


def query_ofertas_produtores(
    cultura: str | None = None,
    municipio: str | None = None,
    status: str = "ATIVA",
    limite: int = 50,
) -> list[dict]:
    """Consulta ofertas de produtores (vw_ofertas_produtores) para a prefeitura."""
    sb = get_supabase_client()
    query = sb.from_("vw_ofertas_produtores").select("*")
    if status:
        query = query.eq("status", sanitizar_string(status, 20))
    if cultura:
        query = query.ilike("descricao", f"%{sanitizar_string(cultura)}%")
    if municipio:
        query = query.ilike("municipio", f"%{sanitizar_string(municipio)}%")
    limite = max(1, min(int(limite or 50), 200))
    result = query.order("criado_em", desc=True).limit(limite).execute()
    return result.data or []


# Colunas aceitas na planilha de carga em lote (mapeiam 1:1 para registrar_oferta_produtor)
PLANILHA_COLUNAS = (
    "nome", "cpf_cnpj", "descricao", "quantidade", "unidade",
    "disponibilidade", "preco_pretendido", "municipio", "contato", "tipo",
)
PLANILHA_OBRIGATORIAS = ("nome", "cpf_cnpj", "descricao", "quantidade")
PLANILHA_MAX_LINHAS = 500


def _to_float(v) -> float | None:
    """Converte célula de planilha (ex.: '4,50', 'R$ 4.50', '') em float ou None."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none", "-"):
        return None
    s = re.sub(r"[^\d,.-]", "", s)
    # Vírgula decimal BR: se há vírgula, ela é o separador decimal
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm_cabecalho(col: str) -> str:
    """Normaliza nome de coluna do cabeçalho (sem acento, minúsculo, sem espaços extras)."""
    c = unicodedata.normalize("NFD", str(col or "")).encode("ascii", "ignore").decode().strip().lower()
    return re.sub(r"\s+", "_", c)


def processar_planilha_ofertas(linhas: list[dict], origem: str = "PLANILHA") -> dict:
    """
    Processa em lote linhas (já lidas de CSV/XLSX) de ofertas de produtores.
    Cada linha é gravada de forma independente reutilizando registrar_oferta_produtor:
    uma linha inválida vai para `erros` e NÃO interrompe as demais.

    Retorna: {"total": N, "inseridas": M, "erros": [{"linha": i, "motivo": "..."}]}
    """
    linhas = linhas or []
    if len(linhas) > PLANILHA_MAX_LINHAS:
        return {"total": len(linhas), "inseridas": 0,
                "erros": [{"linha": 0, "motivo": f"Planilha excede o limite de {PLANILHA_MAX_LINHAS} linhas."}]}

    inseridas, erros = 0, []
    for i, raw in enumerate(linhas, start=1):
        # Normaliza chaves do dicionário (tolera cabeçalhos com acento/maiúsculas)
        row = {_norm_cabecalho(k): v for k, v in (raw or {}).items()}
        try:
            res = registrar_oferta_produtor(
                nome=str(row.get("nome", "") or "").strip(),
                cpf_cnpj=str(row.get("cpf_cnpj", "") or "").strip(),
                descricao=str(row.get("descricao", "") or "").strip(),
                quantidade=_to_float(row.get("quantidade")),
                unidade=(str(row.get("unidade", "") or "kg").strip() or "kg"),
                disponibilidade=(str(row.get("disponibilidade", "") or "").strip() or None),
                preco_pretendido=_to_float(row.get("preco_pretendido")),
                municipio=(str(row.get("municipio", "") or "").strip() or None),
                contato=(str(row.get("contato", "") or "").strip() or None),
                tipo=(str(row.get("tipo", "") or "PRODUTOR_INDIVIDUAL").strip().upper() or "PRODUTOR_INDIVIDUAL"),
                origem=origem,
            )
        except Exception as e:
            logger.error(f"Erro inesperado na linha {i} da planilha: {e}", exc_info=True)
            erros.append({"linha": i, "motivo": "Erro inesperado ao processar a linha."})
            continue
        if res.get("ok"):
            inseridas += 1
        else:
            erros.append({"linha": i, "motivo": res.get("erro", "Erro desconhecido.")})

    return {"total": len(linhas), "inseridas": inseridas, "erros": erros}


TOOLS_SCHEMA = [
    {
        "name": "query_itens_agro",
        "description": "Consulta itens agrícolas de licitações da vw_itens_agro (já filtrados por relevante_agro=true). Use para perguntas sobre volumes, valores, culturas, categorias, sazonalidade.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cultura": {
                    "type": "string",
                    "description": "Nome da cultura (ex: alface, tomate, arroz)"
                },
                "categoria": {
                    "type": "string",
                    "enum": ["HORTIFRUTI", "FRUTAS", "PROTEINA_ANIMAL"],
                    "description": "Apenas categorias agrícolas puras: hortaliças/frutas/proteína animal fresca"
                },
                "canal": {
                    "type": "string",
                    "enum": ["PNAE", "PAA", "ARMAZEM_FAMILIA", "BANCO_ALIMENTOS", "MESA_SOLIDARIA"],
                    "description": "Canal institucional de compra"
                },
                "ano": {
                    "type": "integer",
                    "description": "Ano de abertura da licitação (ex: 2023)"
                },
                "agregacao": {
                    "type": "string",
                    "enum": ["detalhado", "por_cultura", "por_canal", "por_ano", "por_categoria"],
                    "description": "Nível de agregação dos resultados"
                }
            },
            "required": ["agregacao"]
        }
    },
    {
        "name": "query_fornecedores",
        "description": "Consulta fornecedores (cooperativas, associações, empresas) que participaram de licitações agrícolas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["COOPERATIVA", "ASSOCIACAO", "EMPRESA", "PESSOA_FISICA"],
                    "description": "Tipo de fornecedor"
                },
                "canal": {
                    "type": "string",
                    "enum": ["PNAE", "PAA", "ARMAZEM_FAMILIA", "BANCO_ALIMENTOS", "MESA_SOLIDARIA"],
                    "description": "Canal de licitação"
                },
                "ano": {
                    "type": "integer",
                    "description": "Ano de participação"
                }
            }
        }
    },
    {
        "name": "query_licitacoes",
        "description": "Busca licitações por processo, canal, ou período. Retorna apenas licitações com itens agrícolas relevantes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "processo": {
                    "type": "string",
                    "description": "Número do processo (ex: DE 4/2019, PNAE 5/2023)"
                },
                "canal": {
                    "type": "string",
                    "enum": ["PNAE", "PAA", "ARMAZEM_FAMILIA", "BANCO_ALIMENTOS", "MESA_SOLIDARIA"],
                    "description": "Canal institucional"
                },
                "ano_inicio": {
                    "type": "integer",
                    "description": "Ano inicial do período (ex: 2020)"
                },
                "ano_fim": {
                    "type": "integer",
                    "description": "Ano final do período (ex: 2023)"
                }
            }
        }
    },
    {
        "name": "buscar_chunks_rag",
        "description": "Busca trechos relevantes de PDFs agrícolas usando busca semântica (RAG com embeddings). Use para perguntas sobre conteúdo específico em documentos de licitações, termos de referência, ou informações sobre produtos/fornecedores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "Pergunta ou tópico a buscar (ex: 'Leite para merenda escolar', 'Fornecedores de tomate')"
                },
                "processo": {
                    "type": "string",
                    "description": "Filtrar por processo específico (opcional, ex: 'DE 4/2019' ou 'PE 6/2021')"
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de chunks a retornar (1-10, padrão: 5)"
                },
                "min_similaridade": {
                    "type": "number",
                    "description": "Mínimo score de similaridade (0-1, padrão: 0.3)"
                }
            },
            "required": ["pergunta"]
        }
    },
    {
        "name": "consultar_preco_produto",
        "description": (
            "Consulta o preço atual e histórico de um produto hortigranjeiro na CEASA "
            "(padrão Curitiba/RMC), com base nos dados oficiais do PROHORT/CONAB. Retorna preço "
            "mínimo, médio e máximo dos últimos 30 dias, variação semanal e avaliação se o preço "
            "está alto/médio/baixo. Use quando perguntarem sobre preço de mercado de um produto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "produto": {"type": "string", "description": "Nome do produto (ex: tomate, alface, cenoura)"},
                "ceasa": {"type": "string",
                          "description": "CEASA de referência. Use CURITIBA para a RMC."},
            },
            "required": ["produto"],
        },
    },
    {
        "name": "comparar_preco_historico",
        "description": (
            "Compara o preço médio atual (30 dias) com a média de 90 dias na CEASA e indica se é "
            "bom momento para vender. Use quando perguntarem 'vale a pena vender agora' ou "
            "'como está o preço comparado com antes'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "produto": {"type": "string", "description": "Nome do produto"},
                "ceasa": {"type": "string",
                          "description": "CEASA de referência (padrão CURITIBA)."},
            },
            "required": ["produto"],
        },
    },
    {
        "name": "ranking_melhores_precos",
        "description": (
            "Retorna as culturas com maior valorização de preço na última semana na CEASA. "
            "Use quando perguntarem 'qual produto está com bom preço' ou 'o que vale a pena "
            "plantar pensando no preço'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Quantidade de produtos (padrão 5)"},
                "ceasa": {"type": "string",
                          "description": "CEASA de referência (padrão CURITIBA)."},
            },
        },
    },
    {
        "name": "consultar_precos_lista",
        "description": (
            "Consulta o preço de VÁRIOS produtos de uma vez na CEASA (preço mínimo, médio, máximo, "
            "sugerido de venda e tendência semanal por produto). Use SEMPRE que o produtor trouxer "
            "uma lista de produtos (ex.: 'tomate, alface e cenoura') ou perguntar sobre mais de um "
            "produto. Retorna também os produtos não encontrados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "produtos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de nomes de produtos (ex: ['tomate','alface','cenoura'])",
                },
                "ceasa": {"type": "string",
                          "description": "CEASA de referência (padrão CURITIBA)."},
            },
            "required": ["produtos"],
        },
    },
    {
        "name": "comparar_ceasas",
        "description": (
            "Compara o preço de um produto entre VÁRIAS/TODAS as CEASAs da base (Curitiba, Maringá, "
            "São Paulo). Use quando o produtor quiser ver em qual CEASA o produto está melhor, ou "
            "pedir uma análise considerando todas as CEASAs. Retorna preço médio/mín/máx/sugerido "
            "por CEASA."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "produto": {"type": "string", "description": "Nome do produto (ex: tomate)"},
                "ceasas": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Opcional. CEASAs a comparar; vazio = todas da base.",
                },
            },
            "required": ["produto"],
        },
    },
    {
        "name": "cruzar_preco_prefeitura",
        "description": (
            "Cruza o preço de atacado da CEASA com o que a PREFEITURA pagou nas licitações de "
            "agricultura familiar (R$/kg), por produto. Indica se a prefeitura paga acima ou abaixo "
            "do atacado (prêmio da AF). Use quando perguntarem 'a prefeitura paga acima/abaixo do "
            "mercado', 'comparar com o que a prefeitura paga', ou citarem licitação + preço. "
            "Atenção às ressalvas de unidade (kg) e de tempo (preço da prefeitura é histórico)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "produtos": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Lista de produtos (ex: ['tomate','batata','mandioca'])",
                },
                "ceasa": {"type": "string",
                          "description": "Opcional. CEASA de referência; vazio = todas."},
            },
            "required": ["produtos"],
        },
    },
]

# Schemas das tools de produtor (definidos à parte para controle de exposição)
_QUERY_OFERTAS_SCHEMA = {
    "name": "query_ofertas_produtores",
    "description": (
        "Consulta as ofertas de fornecimento cadastradas pelos produtores da agricultura familiar "
        "(o que têm disponível para vender). Use quando a prefeitura perguntar quem tem determinado "
        "produto, ofertas por município, ou disponibilidade de fornecedores."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cultura": {"type": "string", "description": "Produto/cultura a buscar (ex: tomate, alface)"},
            "municipio": {"type": "string", "description": "Filtrar por município do produtor"},
            "status": {"type": "string", "enum": ["ATIVA", "INATIVA", "ATENDIDA"],
                       "description": "Status da oferta (padrão ATIVA)"},
            "limite": {"type": "integer", "description": "Máximo de resultados (1-200, padrão 50)"},
        },
    },
}

_REGISTRAR_OFERTA_SCHEMA = {
    "name": "registrar_oferta_produtor",
    "description": (
        "Cadastra uma oferta de fornecimento da agricultura familiar (produto que o produtor tem "
        "para vender). Faz upsert do produtor (por CPF/CNPJ) e grava a oferta. Só chame após "
        "confirmar os dados com o produtor. Valida CPF/CNPJ e campos obrigatórios."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nome": {"type": "string", "description": "Nome do produtor/cooperativa/associação"},
            "cpf_cnpj": {"type": "string", "description": "CPF (11 díg.) ou CNPJ (14 díg.)"},
            "descricao": {"type": "string", "description": "Produto ofertado (ex: alface crespa)"},
            "quantidade": {"type": "number", "description": "Quantidade disponível (> 0)"},
            "unidade": {"type": "string", "description": "Unidade (padrão kg; ex: kg, dz, un, maço)"},
            "disponibilidade": {"type": "string", "description": "Época/safra (ex: jan-mar/2026, o ano todo)"},
            "preco_pretendido": {"type": "number", "description": "Preço pretendido por unidade em R$ (opcional)"},
            "municipio": {"type": "string", "description": "Município do produtor"},
            "contato": {"type": "string", "description": "Telefone/WhatsApp ou e-mail"},
            "tipo": {"type": "string", "enum": ["PRODUTOR_INDIVIDUAL", "COOPERATIVA", "ASSOCIACAO"],
                     "description": "Tipo de produtor (padrão PRODUTOR_INDIVIDUAL)"},
            "observacoes": {"type": "string", "description": "Detalhes extras (orgânico, embalagem etc.)"},
        },
        "required": ["nome", "cpf_cnpj", "descricao", "quantidade"],
    },
}

# A consulta de ofertas fica disponível para o assistente geral (prefeitura).
TOOLS_SCHEMA.append(_QUERY_OFERTAS_SCHEMA)

# A tool de ESCRITA fica restrita ao endpoint do produtor (não exposta ao assistente geral).
PRODUTOR_TOOLS_SCHEMA = [_REGISTRAR_OFERTA_SCHEMA, _QUERY_OFERTAS_SCHEMA]


def executar_tool(nome: str, inputs: dict) -> Any:
    """Executa uma tool pelo nome com os inputs fornecidos."""
    if nome == "query_itens_agro":
        return query_itens_agro(**inputs)
    elif nome == "query_fornecedores":
        return query_fornecedores(**inputs)
    elif nome == "query_licitacoes":
        return query_licitacoes(**inputs)
    elif nome == "buscar_chunks_rag":
        return buscar_chunks_rag(**inputs)
    elif nome == "buscar_documentos_vetor":
        # Compatibilidade com nome antigo
        return buscar_chunks_rag(**inputs)
    elif nome == "consultar_preco_produto":
        return prohort_consultar_preco(**inputs)
    elif nome == "comparar_preco_historico":
        return prohort_comparar_historico(**inputs)
    elif nome == "ranking_melhores_precos":
        return prohort_ranking(**inputs)
    elif nome == "consultar_precos_lista":
        return prohort_consultar_precos_lista(**inputs)
    elif nome == "comparar_ceasas":
        return prohort_comparar_ceasas(**inputs)
    elif nome == "cruzar_preco_prefeitura":
        return prohort_cruzar_prefeitura(**inputs)
    elif nome == "registrar_oferta_produtor":
        return registrar_oferta_produtor(**inputs)
    elif nome == "query_ofertas_produtores":
        return query_ofertas_produtores(**inputs)
    else:
        return {"erro": f"Tool desconhecida: {nome}"}
