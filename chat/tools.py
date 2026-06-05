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

def _prohort_avaliacao(media30, media90) -> str:
    """Compara média 30d vs 90d e retorna texto de avaliação do preço atual."""
    if media30 and media90:
        desvio = ((media30 - media90) / media90) * 100
        if desvio < -10:
            return "ABAIXO da média histórica (90 dias) — preço relativamente baixo."
        if desvio > 10:
            return "ACIMA da média histórica (90 dias) — preço relativamente alto."
        return "NA MÉDIA histórica (90 dias)."
    return "Histórico insuficiente para comparação."


def _prohort_preco_sugerido(media30, min30, max30, variacao) -> float | None:
    """
    Preço sugerido de venda (referência de negociação) para o produtor.
    Base = média de 30 dias; ajustada pela tendência semanal e limitada à faixa min/máx.
    - mercado em alta (>+5%): sugere +5% sobre a média (pode pedir um pouco mais);
    - mercado em queda (<-5%): mantém a média (não baixar além dela);
    - estável: a própria média.
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
    return round(base, 2)


def _prohort_linha_produto(r: dict) -> dict:
    """Monta o dict padronizado de um produto a partir de uma linha de v_prohort_analise."""
    media30, min30, max30 = r.get("media_30d"), r.get("min_30d"), r.get("max_30d")
    variacao = r.get("variacao_semanal_pct")
    return {
        "produto": r.get("produto_norm"),
        "unidade": r.get("unidade") or "kg",
        "preco_min_30d": min30,
        "preco_medio_30d": media30,
        "preco_max_30d": max30,
        "preco_sugerido": _prohort_preco_sugerido(media30, min30, max30, variacao),
        "variacao_semanal_pct": variacao,
        "media_90d": r.get("media_90d"),
        "avaliacao": _prohort_avaliacao(media30, r.get("media_90d")),
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
    else:
        return {"erro": f"Tool desconhecida: {nome}"}
