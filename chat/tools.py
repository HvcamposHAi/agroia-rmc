import json
import logging
import re
import time
import unicodedata
from typing import Any
from chat.db import get_supabase_client

logger = logging.getLogger(__name__)

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

def buscar_documentos_vetor(
    pergunta: str,
    processo: str | None = None,
    limite: int = 5
) -> list[dict]:
    """
    Busca chunks de PDFs similares à pergunta usando embeddings vetoriais.
    Requer que pdf_chunks já esteja populada (executar indexar_pdfs.py primeiro).
    """
    sb = get_supabase_client()

    try:
        model = get_st_model()
        embedding = model.encode(pergunta)

        result = sb.rpc(
            "buscar_chunks_similares",
            {
                "query_embedding": embedding.tolist(),
                "limite": min(limite, 10),
                "processo_filtro": processo
            }
        ).execute()

        return result.data if result.data else []
    except Exception as e:
        return [{"erro": f"Erro na busca vetorial (PDFs podem não estar indexados): {str(e)}"}]

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
                    "enum": ["HORTIFRUTI", "FRUTAS", "GRAOS_CEREAIS", "LATICINIOS", "PROTEINA_ANIMAL", "PROCESSADOS_AF"],
                    "description": "Categoria agrícola"
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
        "name": "buscar_documentos_vetor",
        "description": "Busca trechos relevantes de PDFs (editais, termos de referência) usando busca semântica. Use para perguntas sobre conteúdo de documentos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "Pergunta ou tópico a buscar no conteúdo dos documentos"
                },
                "processo": {
                    "type": "string",
                    "description": "Filtrar por processo específico (opcional, ex: DE 4/2019)"
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de trechos a retornar (padrão: 5)"
                }
            },
            "required": ["pergunta"]
        }
    }
]

def executar_tool(nome: str, inputs: dict) -> Any:
    """Executa uma tool pelo nome com os inputs fornecidos."""
    if nome == "query_itens_agro":
        return query_itens_agro(**inputs)
    elif nome == "query_fornecedores":
        return query_fornecedores(**inputs)
    elif nome == "query_licitacoes":
        return query_licitacoes(**inputs)
    elif nome == "buscar_documentos_vetor":
        return buscar_documentos_vetor(**inputs)
    else:
        return {"erro": f"Tool desconhecida: {nome}"}
