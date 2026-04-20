import uuid
import os
import json
from collections import defaultdict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from chat.agent import chat
from chat.db import get_supabase_client

load_dotenv()

app = FastAPI(
    title="AgroIA-RMC Chat",
    description="Agente de chat RAG para licitações agrícolas da RMC",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    pergunta: str
    historico: list[dict] = []
    session_id: str | None = None

class ChatResponse(BaseModel):
    resposta: str
    tools_usadas: list[str]
    session_id: str

@app.get("/health")
def health():
    """Verifica conectividade com Supabase."""
    try:
        sb = get_supabase_client()
        result = sb.table("licitacoes").select("id").limit(1).execute()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}

def carregar_historico(session_id: str) -> list[dict]:
    """Carrega histórico de conversa do Supabase."""
    try:
        sb = get_supabase_client()
        result = sb.table("conversas").select(
            "role, content"
        ).eq("session_id", session_id).order("criado_em").execute()
        return [
            {"role": row["role"], "content": row["content"]}
            for row in (result.data or [])
        ]
    except Exception:
        return []

def salvar_turno(session_id: str, role: str, content: str, tools_usadas: list[str] = None) -> None:
    """Salva um turno de conversa no Supabase."""
    try:
        sb = get_supabase_client()
        sb.table("conversas").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
            "tools_usadas": tools_usadas or []
        }).execute()
    except Exception as e:
        print(f"Aviso: não consegui salvar histórico: {e}")

@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Endpoint de chat com persistência de histórico."""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        historico = request.historico or carregar_historico(session_id)
        resultado = chat(request.pergunta, historico)
        salvar_turno(session_id, "user", request.pergunta)
        salvar_turno(session_id, "assistant", resultado["resposta"], resultado["tools_usadas"])
        return ChatResponse(
            resposta=resultado["resposta"],
            tools_usadas=resultado["tools_usadas"],
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversas/{session_id}")
def obter_conversa(session_id: str) -> list[dict]:
    """Retorna histórico completo de uma conversa."""
    return carregar_historico(session_id)

@app.delete("/conversas/{session_id}")
def deletar_conversa(session_id: str) -> dict:
    """Deleta histórico de uma conversa."""
    try:
        sb = get_supabase_client()
        sb.table("conversas").delete().eq("session_id", session_id).execute()
        return {"status": "deletado", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alertas")
async def gerar_alertas():
    """Analisa dados históricos e gera alertas com IA."""
    import anthropic as ant

    try:
        sb = get_supabase_client()

        # Busca dados da view
        r = sb.from_('vw_itens_agro').select(
            'cultura, valor_total, qt_solicitada, dt_abertura'
        ).not_.is_('cultura', 'null').gt('qt_solicitada', 0).gt('valor_total', 0).execute()

        dados_raw = r.data or []
        IGNORAR = {'OUTRO', 'SERVIÇO', 'LOCAÇÃO', 'LIMPEZA', 'INFORMÁTICA',
                   'EQUIPAMENTO', 'SACOLA', 'EMBALAGEM', 'BANDEJA', 'ETIQUETA'}

        # Agrega por cultura e ano
        agg: dict = defaultdict(lambda: defaultdict(list))
        for row in dados_raw:
            cultura = row.get('cultura', '')
            if not cultura or cultura in IGNORAR:
                continue
            ano = (row.get('dt_abertura') or '')[:4]
            if not ano:
                continue
            preco = row['valor_total'] / row['qt_solicitada']
            agg[cultura][ano].append({'preco': preco, 'ultima': row['dt_abertura']})

        dados = []
        for cultura, anos_data in agg.items():
            for ano, items in sorted(anos_data.items()):
                precos = [i['preco'] for i in items]
                dados.append({
                    'cultura': cultura,
                    'ano': int(ano),
                    'preco_medio_kg': round(sum(precos) / len(precos), 2),
                    'qtd_itens': len(items),
                    'ultima_compra': max(i['ultima'] for i in items)
                })

        client = ant.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

        prompt = f"""Você é um sistema de análise de inteligência de abastecimento para a SMSAN/FAAC de Curitiba.

Analise os dados históricos de licitações de alimentos abaixo e identifique alertas em três categorias:

1. ALTA_PRECO: culturas com aumento de preço/kg acima de 20% entre anos consecutivos
2. DESABASTECIMENTO: culturas sem compras nos últimos 12 meses (ultima_compra antes de 2025)
3. SUPERFATURAMENTO: itens com preço/kg muito acima da média histórica da mesma cultura (desvio acima de 50%)

Dados (cultura, ano, preco_medio_kg, qtd_itens, ultima_compra):
{str(dados[:300])}

Responda APENAS em JSON válido, sem markdown, no formato:
{{
  "alertas": [
    {{
      "tipo": "ALTA_PRECO" | "DESABASTECIMENTO" | "SUPERFATURAMENTO",
      "severidade": "ALTA" | "MEDIA" | "BAIXA",
      "cultura": "nome da cultura",
      "titulo": "título curto do alerta",
      "descricao": "descrição detalhada com números específicos",
      "recomendacao": "ação sugerida para gestores"
    }}
  ],
  "resumo": "parágrafo resumindo os principais riscos encontrados"
}}

Gere no máximo 15 alertas, priorizando os mais críticos."""

        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        texto = msg.content[0].text.strip()
        if texto.startswith('```'):
            texto = texto.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        return json.loads(texto)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    """Documentação da API."""
    return {
        "nome": "AgroIA-RMC Chat API",
        "endpoints": {
            "GET /health": "Status do banco de dados",
            "POST /chat": "Enviar pergunta e receber resposta",
            "POST /alertas": "Gerar alertas inteligentes com IA",
            "GET /docs": "Documentação Swagger"
        }
    }
