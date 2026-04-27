import uuid
import os
import json
import logging
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from dotenv import load_dotenv
from chat.agent import chat, chat_stream
from chat.tools import get_cached, set_cache
from chat.db import get_supabase_client
from api.coleta import (
    iniciar_coleta, cancelar_coleta, get_status as get_coleta_status,
    get_stats_classificacao, configurar_agendamento, get_config, salvar_config
)
import asyncio

load_dotenv()

# Validar variáveis críticas no startup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing required env vars: SUPABASE_URL, SUPABASE_KEY")
if not ANTHROPIC_KEY:
    raise RuntimeError("Missing required env var: ANTHROPIC_API_KEY")
if not API_SECRET_KEY:
    raise RuntimeError("Missing required env var: API_SECRET_KEY")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AgroIA-RMC Chat",
    description="Agente de chat RAG para licitações agrícolas da RMC",
    version="1.0.0"
)

# SEC-001: Configure CORS with explicit allowed origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# ─── Evento de Startup ────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Configura agendamento e outras tarefas ao iniciar."""
    configurar_agendamento(app)
    logger.info("Agendamento configurado com sucesso")

# SEC-002: API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key

class ChatRequest(BaseModel):
    pergunta: str
    historico: list[dict] = []
    session_id: str | None = None

class ChatResponse(BaseModel):
    resposta: str
    tools_usadas: list[str]
    session_id: str

class AuditoriaAlerta(BaseModel):
    tipo: str
    severidade: str
    mensagem: str
    processo: str | None = None
    qtd_empenhos: int | None = None

class AuditoriaMetricas(BaseModel):
    total_licitacoes_agro: int
    lics_com_docs: int
    taxa_cobertura_pct: float
    total_empenhos: int
    lics_com_empenhos: int
    empenhos_sem_docs: int
    lics_concluidas_sem_docs: int
    alertas_criticos: int
    alertas_graves: int

class AuditoriaResultado(BaseModel):
    metricas: AuditoriaMetricas
    alertas: list[AuditoriaAlerta]
    executado_em: str

class AuditoriaChatRequest(BaseModel):
    pergunta: str
    contexto: AuditoriaResultado

class ConsistenciaVerificacao(BaseModel):
    nome: str
    status: str  # 'OK', 'AVISO', 'CRITICO'
    detalhe: str

class ConsistenciaResultado(BaseModel):
    gerado_em: str
    status_geral: str
    verificacoes: list[ConsistenciaVerificacao]

@app.get("/health")
def health():
    """Verifica conectividade com Supabase."""
    try:
        sb = get_supabase_client()
        result = sb.table("licitacoes").select("id").limit(1).execute()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("Health check failed", exc_info=True)
        return {"status": "error", "database": "unavailable"}

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
def chat_endpoint(request_http: Request, request: ChatRequest, _: str = Depends(verify_api_key)) -> ChatResponse:
    """Endpoint de chat com persistência de histórico."""
    session_id = request.session_id or str(uuid.uuid4())
    try:
        logger.info(f"[{session_id}] Chat request recebido (len={len(request.pergunta)})")
        historico = request.historico or carregar_historico(session_id)
        resultado = chat(request.pergunta, historico)

        # Validar resposta
        if not resultado or not isinstance(resultado, dict):
            logger.error(f"[{session_id}] chat() returned invalid type: {type(resultado)}")
            raise HTTPException(status_code=500, detail="Agent returned invalid response")

        if "resposta" not in resultado:
            logger.error(f"[{session_id}] chat() missing 'resposta' field: {resultado.keys()}")
            raise HTTPException(status_code=500, detail="Agent returned empty response")

        resposta = resultado.get("resposta", "").strip()
        if not resposta:
            logger.error(f"[{session_id}] chat() returned empty resposta field")
            raise HTTPException(status_code=500, detail="Agent returned empty response")

        tools_usadas = resultado.get("tools_usadas", [])

        salvar_turno(session_id, "user", request.pergunta)
        salvar_turno(session_id, "assistant", resposta, tools_usadas)
        logger.info(f"[{session_id}] Chat response successful ({len(tools_usadas)} tools used)")

        return ChatResponse(
            resposta=resposta,
            tools_usadas=tools_usadas,
            session_id=session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{session_id}] Chat error", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat error: {str(e)[:100]}"
        )

@app.post("/chat/stream")
def chat_stream_endpoint(request_http: Request, request: ChatRequest, _: str = Depends(verify_api_key)):
    """Streaming chat endpoint with SSE response."""
    session_id = request.session_id or str(uuid.uuid4())

    def generate():
        try:
            logger.info(f"[{session_id}] Stream chat request recebido (len={len(request.pergunta)})")
            historico = request.historico or carregar_historico(session_id)

            cached = get_cached(request.pergunta)
            if cached:
                logger.info(f"[{session_id}] Cache hit")
                yield f"data: {json.dumps({'tipo': 'token', 'texto': cached})}\n\n"
                yield f"data: {json.dumps({'tipo': 'fim', 'tools_usadas': []})}\n\n"
                return

            resposta_completa = ""
            tools_usadas = []

            for event in chat_stream(request.pergunta, historico):
                if event.get("tipo") == "token":
                    resposta_completa += event.get("texto", "")
                if event.get("tipo") == "fim":
                    tools_usadas = event.get("tools_usadas", [])
                yield f"data: {json.dumps(event)}\n\n"

            set_cache(request.pergunta, resposta_completa)
            salvar_turno(session_id, "user", request.pergunta)
            salvar_turno(session_id, "assistant", resposta_completa, tools_usadas)
            logger.info(f"[{session_id}] Stream response successful ({len(tools_usadas)} tools used)")

        except Exception as e:
            logger.error(f"[{session_id}] Stream chat error", exc_info=True)
            yield f"data: {json.dumps({'tipo': 'token', 'texto': '⚠️ Erro ao processar sua pergunta. Tente novamente.'})}\n\n"
            yield f"data: {json.dumps({'tipo': 'fim', 'tools_usadas': []})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.get("/conversas/{session_id}")
def obter_conversa(request: Request, session_id: str, _: str = Depends(verify_api_key)) -> list[dict]:
    """Retorna histórico completo de uma conversa."""
    return carregar_historico(session_id)

@app.delete("/conversas/{session_id}")
def deletar_conversa(request: Request, session_id: str, _: str = Depends(verify_api_key)) -> dict:
    """Deleta histórico de uma conversa."""
    try:
        sb = get_supabase_client()
        sb.table("conversas").delete().eq("session_id", session_id).execute()
        return {"status": "deletado", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alertas")
async def gerar_alertas(request: Request, _: str = Depends(verify_api_key)):
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

        from datetime import datetime, timedelta

        limiar_desabastecimento = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        prompt = f"""Você é um sistema de análise de inteligência de abastecimento para a SMSAN/FAAC de Curitiba.

Analise os dados históricos de licitações de alimentos abaixo e identifique alertas em três categorias:

1. ALTA_PRECO: culturas com aumento de preço/kg acima de 20% entre anos consecutivos
2. DESABASTECIMENTO: culturas sem compras nos últimos 12 meses (ultima_compra antes de {limiar_desabastecimento})
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

Gere no máximo 10 alertas, priorizando os mais críticos."""

        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        texto = msg.content[0].text.strip()

        # Remove markdown code blocks se presentes
        if '```json' in texto:
            texto = texto.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in texto:
            texto = texto.split('```', 1)[1].split('```', 1)[0].strip()

        # Extrai apenas o objeto JSON (do primeiro { ao último })
        inicio = texto.find('{')
        fim = texto.rfind('}')
        if inicio != -1 and fim != -1:
            texto = texto[inicio:fim+1]

        return json.loads(texto)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

_alertas_cache = {'data': None, 'timestamp': 0}

@app.post("/alertas/stream")
def gerar_alertas_stream(request: Request, _: str = Depends(verify_api_key)):
    """Streaming version of alertas endpoint com cache."""
    from datetime import datetime, timedelta

    def generate():
        try:
            import time
            import anthropic as ant

            sb = get_supabase_client()

            # Verificar cache (válido por 30 min)
            agora = time.time()
            if _alertas_cache['data'] and (agora - _alertas_cache['timestamp']) < 1800:
                yield f"data: {json.dumps({'tipo': 'status', 'msg': '📦 Carregando cache...'})}\n\n"
                yield f"data: {json.dumps({'tipo': 'resultado', 'dados': _alertas_cache['data']})}\n\n"
                yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"
                return

            yield f"data: {json.dumps({'tipo': 'status', 'msg': '🔍 Agregando dados...'})}\n\n"

            # Query otimizada: apenas últimos 3 anos, com agregação SQL
            limiar_desabastecimento = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            r = sb.from_('vw_itens_agro').select(
                'cultura, valor_total, qt_solicitada, dt_abertura'
            ).not_.is_('cultura', 'null').gt('qt_solicitada', 0).gt('valor_total', 0).limit(2000).execute()

            dados_raw = r.data or []
            IGNORAR = {'OUTRO', 'SERVIÇO', 'LOCAÇÃO', 'LIMPEZA', 'INFORMÁTICA',
                       'EQUIPAMENTO', 'SACOLA', 'EMBALAGEM', 'BANDEJA', 'ETIQUETA'}

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

            yield f"data: {json.dumps({'tipo': 'status', 'msg': '💡 Analisando com IA...'})}\n\n"

            client = ant.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

            # Prompt otimizado: reduz de 300+ para 50 registros
            prompt = f"""Analise dados de licitações agrícolas SMSAN/FAAC e identifique 3-5 alertas críticos:

1. ALTA_PRECO: aumento >20% entre anos
2. DESABASTECIMENTO: sem compras desde {limiar_desabastecimento}
3. SUPERFATURAMENTO: preço >50% acima da média

Dados resumidos (apenas últimos 2-3 anos):
{json.dumps(dados[-50:], ensure_ascii=False)}

Responda APENAS em JSON (sem markdown):
{{"alertas": [{{"tipo": "ALTA_PRECO|DESABASTECIMENTO|SUPERFATURAMENTO", "severidade": "ALTA|MEDIA|BAIXA", "cultura": "", "titulo": "", "descricao": "", "recomendacao": ""}}], "resumo": ""}}

Máximo 5 alertas."""

            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            texto = msg.content[0].text.strip()
            if '```json' in texto:
                texto = texto.split('```json', 1)[1].split('```', 1)[0].strip()
            elif '```' in texto:
                texto = texto.split('```', 1)[1].split('```', 1)[0].strip()

            inicio = texto.find('{')
            fim = texto.rfind('}')
            if inicio != -1 and fim != -1:
                texto = texto[inicio:fim+1]

            resultado = json.loads(texto)
            _alertas_cache['data'] = resultado
            _alertas_cache['timestamp'] = time.time()

            yield f"data: {json.dumps({'tipo': 'resultado', 'dados': resultado})}\n\n"
            yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"

        except Exception as e:
            logger.error(f"Alertas stream error: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro ao analisar alertas'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.post("/auditoria/executar")
async def executar_auditoria(request: Request, _: str = Depends(verify_api_key)) -> AuditoriaResultado:
    """Executa auditoria de qualidade dos dados e licitações agrícolas."""
    from datetime import datetime
    try:
        sb = get_supabase_client()
        alertas = []

        # Trazer dados em bulk
        itens_agro = sb.from_('itens_licitacao').select('id, licitacao_id').eq('relevante_agro', True).execute()
        documentos = sb.from_('documentos_licitacao').select('licitacao_id').execute()
        empenhos = sb.from_('empenhos').select('id, item_id, nr_empenho').execute()
        licitacoes = sb.from_('licitacoes').select('id, processo, situacao').execute()

        # Extrair dados
        itens_agro_data = itens_agro.data or []
        docs_data = documentos.data or []
        empenhos_data = empenhos.data or []
        lics_data = licitacoes.data or []

        # Sets de IDs
        lics_agro_ids = set(r['licitacao_id'] for r in itens_agro_data)
        lics_com_docs = set(d['licitacao_id'] for d in docs_data)
        total_lics_agro = len(lics_agro_ids)
        total_docs_agro = len(lics_com_docs & lics_agro_ids)
        taxa_cobertura = (total_docs_agro / total_lics_agro * 100) if total_lics_agro > 0 else 0

        # Mapear item → licitação
        item_to_lic = {i['id']: i['licitacao_id'] for i in itens_agro_data}

        # Licitações com empenhos
        lics_com_empenhos = set()
        for emp in empenhos_data:
            item_id = emp.get('item_id')
            if item_id and item_id in item_to_lic:
                lics_com_empenhos.add(item_to_lic[item_id])

        # Dicionário de licitações para lookup rápido
        lic_dict = {l['id']: l for l in lics_data}

        # Empenhos sem documentação (CRÍTICO)
        empenhos_sem_docs = 0
        for lic_id in lics_com_empenhos:
            if lic_id not in lics_com_docs and lic_id in lic_dict:
                empenhos_sem_docs += 1
                lic = lic_dict[lic_id]
                alertas.append(AuditoriaAlerta(
                    tipo='ERRO_BD',
                    severidade='CRITICO',
                    mensagem=f"CRÍTICO: Licitação {lic['processo']} com empenho(s) mas SEM documentação",
                    processo=lic['processo']
                ))

        # Licitações concluídas sem docs (GRAVE)
        for lic in lics_data:
            if lic['id'] in lics_agro_ids and lic['id'] not in lics_com_docs and lic['situacao'] == 'Concluído':
                alertas.append(AuditoriaAlerta(
                    tipo='ERRO_BD',
                    severidade='GRAVE',
                    mensagem=f"GRAVE: Licitação {lic['processo']} finalizada SEM documentação",
                    processo=lic['processo']
                ))

        alertas_criticos = sum(1 for a in alertas if a.severidade == 'CRITICO')
        alertas_graves = sum(1 for a in alertas if a.severidade == 'GRAVE')

        metricas = AuditoriaMetricas(
            total_licitacoes_agro=total_lics_agro,
            lics_com_docs=total_docs_agro,
            taxa_cobertura_pct=round(taxa_cobertura, 1),
            total_empenhos=len(empenhos_data),
            lics_com_empenhos=len(lics_com_empenhos),
            empenhos_sem_docs=empenhos_sem_docs,
            lics_concluidas_sem_docs=alertas_graves,
            alertas_criticos=alertas_criticos,
            alertas_graves=alertas_graves
        )

        return AuditoriaResultado(
            metricas=metricas,
            alertas=alertas[:50],
            executado_em=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error("Auditoria error", exc_info=True)
        raise HTTPException(status_code=500, detail="Auditoria execution failed")

@app.post("/auditoria/executar/stream")
def executar_auditoria_stream(request: Request, _: str = Depends(verify_api_key)):
    """Streaming version of auditoria executar."""
    from datetime import datetime

    def generate():
        try:
            yield f"data: {json.dumps({'tipo': 'status', 'msg': '📊 Carregando dados de licitações...'})}\n\n"
            sb = get_supabase_client()
            alertas = []

            itens_agro = sb.from_('itens_licitacao').select('id, licitacao_id').eq('relevante_agro', True).execute()
            documentos = sb.from_('documentos_licitacao').select('licitacao_id').execute()
            empenhos = sb.from_('empenhos').select('id, item_id, nr_empenho').execute()
            licitacoes = sb.from_('licitacoes').select('id, processo, situacao').execute()

            yield f"data: {json.dumps({'tipo': 'status', 'msg': '🔍 Analisando inconsistências...'})}\n\n"

            itens_agro_data = itens_agro.data or []
            docs_data = documentos.data or []
            empenhos_data = empenhos.data or []
            lics_data = licitacoes.data or []

            lics_agro_ids = set(r['licitacao_id'] for r in itens_agro_data)
            lics_com_docs = set(d['licitacao_id'] for d in docs_data)
            total_lics_agro = len(lics_agro_ids)
            total_docs_agro = len(lics_com_docs & lics_agro_ids)
            taxa_cobertura = (total_docs_agro / total_lics_agro * 100) if total_lics_agro > 0 else 0

            item_to_lic = {i['id']: i['licitacao_id'] for i in itens_agro_data}
            lics_com_empenhos = set()
            for emp in empenhos_data:
                item_id = emp.get('item_id')
                if item_id and item_id in item_to_lic:
                    lics_com_empenhos.add(item_to_lic[item_id])

            lic_dict = {l['id']: l for l in lics_data}
            empenhos_sem_docs = 0
            for lic_id in lics_com_empenhos:
                if lic_id not in lics_com_docs and lic_id in lic_dict:
                    empenhos_sem_docs += 1
                    lic = lic_dict[lic_id]
                    alertas.append(AuditoriaAlerta(
                        tipo='ERRO_BD',
                        severidade='CRITICO',
                        mensagem=f"CRÍTICO: Licitação {lic['processo']} com empenho(s) mas SEM documentação",
                        processo=lic['processo']
                    ))

            for lic in lics_data:
                if lic['id'] in lics_agro_ids and lic['id'] not in lics_com_docs and lic['situacao'] == 'Concluído':
                    alertas.append(AuditoriaAlerta(
                        tipo='ERRO_BD',
                        severidade='GRAVE',
                        mensagem=f"GRAVE: Licitação {lic['processo']} finalizada SEM documentação",
                        processo=lic['processo']
                    ))

            alertas_criticos = sum(1 for a in alertas if a.severidade == 'CRITICO')
            alertas_graves = sum(1 for a in alertas if a.severidade == 'GRAVE')

            metricas = AuditoriaMetricas(
                total_licitacoes_agro=total_lics_agro,
                lics_com_docs=total_docs_agro,
                taxa_cobertura_pct=round(taxa_cobertura, 1),
                total_empenhos=len(empenhos_data),
                lics_com_empenhos=len(lics_com_empenhos),
                empenhos_sem_docs=empenhos_sem_docs,
                lics_concluidas_sem_docs=alertas_graves,
                alertas_criticos=alertas_criticos,
                alertas_graves=alertas_graves
            )

            resultado = AuditoriaResultado(
                metricas=metricas,
                alertas=alertas[:50],
                executado_em=datetime.now().isoformat()
            )

            yield f"data: {json.dumps({'tipo': 'resultado', 'dados': resultado.model_dump()})}\n\n"
            yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"

        except Exception as e:
            logger.error(f"Auditoria stream error: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'tipo': 'erro', 'msg': 'Erro ao executar auditoria'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.post("/auditoria/chat")
async def auditoria_chat(request_obj: Request, request: AuditoriaChatRequest, _: str = Depends(verify_api_key)) -> dict:
    """Discute resultados da auditoria com IA."""
    from datetime import datetime
    import anthropic as ant

    try:
        client = ant.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

        contexto_str = json.dumps({
            'metricas': request.contexto.metricas.model_dump(),
            'alertas_amostra': [a.model_dump() for a in request.contexto.alertas[:10]]
        }, ensure_ascii=False, indent=2)

        prompt = f"""Você é um assistente especializado em auditoria de licitações públicas para agricultura familiar.

Um gestor da SMSAN/FAAC de Curitiba fez uma auditoria de qualidade dos dados de licitações agrícolas.

CONTEXTO DA AUDITORIA:
{contexto_str}

PERGUNTA DO GESTOR:
{request.pergunta}

Responda em português de forma clara, direta e executiva. Se a pergunta se refere aos dados da auditoria, cite números específicos."""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'resposta': msg.content[0].text,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Auditoria chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auditoria/consistencia")
async def validar_consistencia(request: Request, _: str = Depends(verify_api_key)) -> ConsistenciaResultado:
    """Valida consistência entre Supabase e frontend."""
    from datetime import datetime
    verificacoes = []

    try:
        sb = get_supabase_client()

        # 1. Cobertura temporal
        try:
            resp_lic = sb.from_('licitacoes').select('dt_abertura').execute()
            lic_dates = [row['dt_abertura'] for row in (resp_lic.data or []) if row['dt_abertura']]
            lic_min, lic_max = (min(lic_dates), max(lic_dates)) if lic_dates else (None, None)

            resp_puros = sb.from_('vw_itens_agro').select('dt_abertura').limit(10000).execute()
            puros_dates = [row['dt_abertura'] for row in (resp_puros.data or []) if row['dt_abertura']]
            puros_min, puros_max = (min(puros_dates), max(puros_dates)) if puros_dates else (None, None)

            detalhe = f"licitacoes: {lic_min} a {lic_max} | vw_itens_agro: {puros_min} a {puros_max}"
            status = 'CRITICO' if puros_max and puros_max < '2025' else 'OK'
            verificacoes.append(ConsistenciaVerificacao(nome='cobertura_temporal', status=status, detalhe=detalhe))
        except Exception as e:
            verificacoes.append(ConsistenciaVerificacao(nome='cobertura_temporal', status='CRITICO', detalhe=f"Erro: {str(e)[:50]}"))

        # 2. Simulação Dashboard (sem ORDER, sem LIMIT explícito)
        try:
            resp = sb.from_('vw_itens_agro').select('cultura, canal, valor_total, dt_abertura, qt_solicitada, categoria_v2').execute()
            rows_returned = len(resp.data) if resp.data else 0

            resp_total = sb.from_('vw_itens_agro').select('id').execute()
            total_real = len(resp_total.data) if resp_total.data else 0

            status = 'AVISO' if (rows_returned == 1000 and total_real > 1000) else 'OK'
            detalhe = f"Dashboard retorna {rows_returned} de {total_real} rows (limitado por PostgREST)"
            if status == 'AVISO':
                detalhe += " | ⚠️ Dados de 2025-2026 podem estar fora"
            verificacoes.append(ConsistenciaVerificacao(nome='simulacao_dashboard', status=status, detalhe=detalhe))
        except Exception as e:
            verificacoes.append(ConsistenciaVerificacao(nome='simulacao_dashboard', status='CRITICO', detalhe=f"Erro: {str(e)[:50]}"))

        # 3. Row counts
        try:
            counts = {}
            for table in ['licitacoes', 'itens_licitacao', 'fornecedores', 'participacoes']:
                resp = sb.from_(table).select('id', count='exact').limit(0).execute()
                counts[table] = resp.count if resp.count is not None else -1

            detalhe = ' | '.join([f"{k}={v}" for k, v in counts.items()])
            status = 'CRITICO' if any(v == 0 for v in counts.values()) else 'OK'
            verificacoes.append(ConsistenciaVerificacao(nome='row_counts', status=status, detalhe=detalhe))
        except Exception as e:
            verificacoes.append(ConsistenciaVerificacao(nome='row_counts', status='AVISO', detalhe=f"Erro: {str(e)[:50]}"))

        # 4. Views funcionam
        try:
            status_views = {}
            for view in ['vw_itens_agro', 'vw_itens_agro']:
                resp = sb.from_(view).select('*').limit(1).execute()
                status_views[view] = 'OK' if resp.data else 'VAZIA'

            detalhe = ' | '.join([f"{k}={v}" for k, v in status_views.items()])
            status = 'CRITICO' if any(v == 'VAZIA' for v in status_views.values()) else 'OK'
            verificacoes.append(ConsistenciaVerificacao(nome='views_funcionam', status=status, detalhe=detalhe))
        except Exception as e:
            verificacoes.append(ConsistenciaVerificacao(nome='views_funcionam', status='CRITICO', detalhe=f"Erro: {str(e)[:50]}"))

        # 5. Threshold alertas
        try:
            resp = sb.from_('vw_itens_agro').select('dt_abertura').limit(10000).execute()
            dates = [row['dt_abertura'] for row in (resp.data or []) if row['dt_abertura']]
            max_date = max(dates) if dates else None

            status = 'AVISO' if max_date and max_date >= '2025' else 'OK'
            detalhe = f"Ano máximo: {max_date[:4] if max_date else '?'}"
            if status == 'AVISO':
                detalhe += " | ⚠️ /alertas usa threshold rolling de 12 meses (OK)"
            verificacoes.append(ConsistenciaVerificacao(nome='threshold_alertas', status=status, detalhe=detalhe))
        except Exception as e:
            verificacoes.append(ConsistenciaVerificacao(nome='threshold_alertas', status='AVISO', detalhe=f"Erro: {str(e)[:50]}"))

    except Exception as e:
        logger.error("Validação consistência error", exc_info=True)
        raise HTTPException(status_code=500, detail="Consistência validation failed")

    # Status geral
    status_geral = 'CRITICO' if any(v.status == 'CRITICO' for v in verificacoes) else \
                   'AVISO' if any(v.status == 'AVISO' for v in verificacoes) else 'OK'

    return ConsistenciaResultado(
        gerado_em=datetime.now().isoformat(),
        status_geral=status_geral,
        verificacoes=verificacoes
    )

@app.get("/")
def root():
    """Documentação da API."""
    return {
        "nome": "AgroIA-RMC Chat API",
        "endpoints": {
            "GET /health": "Status do banco de dados",
            "POST /chat": "Enviar pergunta e receber resposta",
            "POST /alertas": "Gerar alertas inteligentes com IA",
            "POST /auditoria/executar": "Executar auditoria sob demanda",
            "POST /auditoria/chat": "Discutir resultados da auditoria com IA",
            "GET /auditoria/consistencia": "Validar consistência entre Supabase e frontend",
            "POST /coleta/iniciar": "Iniciar coleta de dados manualmente",
            "POST /coleta/cancelar": "Cancelar coleta em andamento",
            "GET /coleta/status": "Status da coleta",
            "GET /coleta/stream": "Stream do progresso em tempo real (SSE)",
            "GET /coleta/stats": "Estatísticas de classificação agrícola",
            "GET /docs": "Documentação Swagger"
        }
    }


# ─── ENDPOINTS DE COLETA ───────────────────────────────────────────────────

@app.post("/coleta/iniciar")
async def endpoint_iniciar_coleta(api_key: str = Security(api_key_header)):
    """Inicia uma coleta de dados manualmente."""
    sucesso, msg = iniciar_coleta()
    if sucesso:
        return {"sucesso": True, "mensagem": msg, "status": get_coleta_status()}
    else:
        raise HTTPException(status_code=400, detail=msg)


@app.post("/coleta/cancelar")
async def endpoint_cancelar_coleta(api_key: str = Security(api_key_header)):
    """Cancela a coleta em andamento."""
    sucesso, msg = cancelar_coleta()
    if sucesso:
        return {"sucesso": True, "mensagem": msg}
    else:
        raise HTTPException(status_code=400, detail=msg)


@app.get("/coleta/status")
async def endpoint_get_coleta_status():
    """Retorna status atual da coleta."""
    return get_coleta_status()


@app.get("/coleta/stream")
async def endpoint_coleta_stream():
    """Stream SSE do progresso da coleta (atualiza a cada 2 segundos)."""

    async def evento_generator():
        idle_count = 0
        while True:
            try:
                status = get_coleta_status()
                yield f"data: {json.dumps(status)}\n\n"

                # Se status é "idle", espera um pouco mas continua tentando
                # (pode ser que coleta foi iniciada mas ainda não atualizou status)
                if status.get("status") == "idle":
                    idle_count += 1
                    # Se ficou idle por muito tempo, encerra
                    if idle_count > 30:  # 60 segundos
                        break
                else:
                    idle_count = 0

                # Se coleta terminou, encerra o stream
                if status.get("status") in ["completed", "cancelled", "error"]:
                    break

                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Erro no stream SSE: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break

    return StreamingResponse(evento_generator(), media_type="text/event-stream")


@app.get("/coleta/stats")
async def endpoint_coleta_stats():
    """Retorna estatísticas de classificação agrícola."""
    return get_stats_classificacao()


@app.get("/coleta/config")
async def endpoint_get_config():
    """Retorna configuração de agendamento semanal."""
    return get_config()


@app.post("/coleta/config")
async def endpoint_salvar_config(config: dict, api_key: str = Security(api_key_header)):
    """Atualiza configuração de agendamento semanal."""
    try:
        # Validar valores
        dia_semana = config.get("dia_semana", 0)
        hora = config.get("hora", 6)
        minuto = config.get("minuto", 0)

        if not (0 <= dia_semana <= 6):
            raise HTTPException(status_code=400, detail="dia_semana deve estar entre 0-6")
        if not (0 <= hora <= 23):
            raise HTTPException(status_code=400, detail="hora deve estar entre 0-23")
        if not (0 <= minuto <= 59):
            raise HTTPException(status_code=400, detail="minuto deve estar entre 0-59")

        salvar_config({"dia_semana": dia_semana, "hora": hora, "minuto": minuto})

        # Reconfigurar agendamento (se scheduler estiver rodando)
        from api.coleta import scheduler
        if scheduler and scheduler.running:
            scheduler.shutdown()
            configurar_agendamento(app)

        return {"sucesso": True, "mensagem": "Configuração atualizada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao salvar config: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {str(e)}")
