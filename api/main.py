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
        r = sb.from_('vw_itens_agro_puros').select(
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

@app.post("/auditoria/executar")
async def executar_auditoria() -> AuditoriaResultado:
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auditoria/chat")
async def auditoria_chat(request: AuditoriaChatRequest) -> dict:
    """Discute resultados da auditoria com IA."""
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
            model="claude-haiku-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'resposta': msg.content[0].text,
            'timestamp': datetime.now().isoformat()
        }
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
            "POST /auditoria/executar": "Executar auditoria sob demanda",
            "POST /auditoria/chat": "Discutir resultados da auditoria com IA",
            "GET /docs": "Documentação Swagger"
        }
    }
