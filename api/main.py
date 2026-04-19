import uuid
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

@app.get("/")
def root():
    """Documentação da API."""
    return {
        "nome": "AgroIA-RMC Chat API",
        "endpoints": {
            "GET /health": "Status do banco de dados",
            "POST /chat": "Enviar pergunta e receber resposta",
            "GET /docs": "Documentação Swagger"
        }
    }
