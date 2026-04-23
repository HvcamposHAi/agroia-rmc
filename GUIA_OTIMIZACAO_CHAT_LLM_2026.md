# Guia de Otimização para Aplicações de Chat com LLM (2026)

## 1. ESTRATÉGIAS DE CACHING

### 1.1 Prompt Caching (Anthropic Claude)

#### Como Funciona
O prompt caching reutiliza o processamento de prefixos estáticos do prompt, reduzindo cálculos redundantes. Você estrutura o prompt com conteúdo estático (instruções, exemplos, contexto) no início e conteúdo dinâmico (mensagens do usuário) no final.

#### Estrutura Recomendada
```python
from anthropic import Anthropic

client = Anthropic()

# Estratégia 1: Cache no system prompt + contexto
def chat_with_caching(user_message, conversation_history=[]):
    """
    Estrutura: [STATIC SYSTEM] [STATIC CONTEXT] [DYNAMIC USER MESSAGES]
    """
    system_prompt = """Você é um assistente especializado em agricultura.
    
[EXEMPLOS DE RESPOSTAS...]
    
[CONTEXTO AGRÍCOLA ESTÁVEL...]"""
    
    messages = [
        *conversation_history,
        {"role": "user", "content": user_message}
    ]
    
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}  # TTL: 5 min
            }
        ],
        messages=messages
    )
    
    return response.content[0].text


# Estratégia 2: Cache com múltiplos breakpoints (até 4)
def advanced_caching_strategy(documents, user_query):
    """
    Aproveita 4 breakpoints permitidos por request
    """
    system = """You are a document QA expert."""
    
    # Documento grande que será reutilizado
    large_context = """
    [DOCUMENTO COMPLETO - 10K+ TOKENS]
    """
    
    # Ferramentas/definições que não mudam
    tools_definition = """
    Available tools: search_db, retrieve_docs, analyze_trends
    """
    
    messages = [
        {
            "type": "text",
            "text": f"Documents:\n{large_context}",
            "cache_control": {"type": "ephemeral"}
        },
        {
            "type": "text",
            "text": f"Tools:\n{tools_definition}",
            "cache_control": {"type": "ephemeral"}
        },
        {
            "type": "text",
            "text": f"User query: {user_query}"
            # Sem cache_control - conteúdo dinâmico
        }
    ]
    
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        messages=messages
    )
    
    return response.content[0].text
```

#### Configuração de TTL
```python
# TTL Options (Janeiro 2026+)
# 5 minutos (padrão): 1.25x custo de input
# 1 hora (premium): 2x custo de input

# Cache reads: 0.1x custo de input (90% desconto)

# Recomendação: Use 1 hora para documentos estáticos
# que são acessados frequentemente

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "Static system prompt",
            "cache_control": {"type": "ephemeral", "max_age_seconds": 3600}
        }
    ],
    messages=messages
)
```

#### Métricas de Cache Hit
```python
def track_cache_performance(response):
    """Monitora economia com cache"""
    usage = response.usage
    
    cache_write_tokens = getattr(usage, 'cache_creation_input_tokens', 0)
    cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0)
    regular_input = usage.input_tokens
    
    # Economia: cache reads custam 90% menos
    cache_savings = cache_read_tokens * 0.9
    
    print(f"Input tokens: {regular_input}")
    print(f"Cache written: {cache_write_tokens}")
    print(f"Cache read: {cache_read_tokens}")
    print(f"Estimated savings: {cache_savings} tokens")
    
    return {
        "cache_hit": cache_read_tokens > 0,
        "savings_percent": (cache_read_tokens / regular_input * 0.9 * 100) 
                          if regular_input > 0 else 0
    }
```

#### Boas Práticas
- **Conteúdo estável em cima**: Instruções, exemplos, contexto grande
- **Conteúdo dinâmico em baixo**: Mensagens do usuário, timestamps
- **Evite rotação**: Não mude o system prompt por requisição
- **Aproveite 4 breakpoints**: Use todos para máxima reutilização
- **TTL apropriado**: 5 min para mudanças frequentes, 1h para contextos estáticos

---

### 1.2 Response Caching (Aplicação)

#### Cache de Respostas Completas
```python
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class ResponseCache:
    """Cache de respostas LLM com invalidação inteligente"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
    
    def _get_cache_key(self, user_message: str, context: str = "") -> str:
        """Gera chave determinística do cache"""
        combined = f"{user_message}|{context}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, user_message: str, context: str = "") -> Optional[str]:
        """Recupera resposta em cache"""
        key = self._get_cache_key(user_message, context)
        
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() < entry['expires_at']:
                entry['hits'] += 1
                return entry['response']
            else:
                del self.cache[key]
        
        return None
    
    def set(self, user_message: str, response: str, context: str = ""):
        """Armazena resposta em cache"""
        key = self._get_cache_key(user_message, context)
        self.cache[key] = {
            'response': response,
            'expires_at': datetime.now() + timedelta(seconds=self.ttl),
            'created_at': datetime.now(),
            'hits': 0
        }
    
    def invalidate_pattern(self, pattern: str):
        """Invalida cache com pattern matching"""
        # Útil para documentos atualizados
        keys_to_delete = [
            k for k in self.cache 
            if pattern.lower() in k.lower()
        ]
        for k in keys_to_delete:
            del self.cache[k]
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        total_hits = sum(e['hits'] for e in self.cache.values())
        return {
            'cached_entries': len(self.cache),
            'total_hits': total_hits,
            'avg_hits_per_entry': total_hits / len(self.cache) 
                                  if self.cache else 0
        }

# Uso em aplicação
cache = ResponseCache(ttl_seconds=1800)

def get_chat_response(user_message: str, context: str = "") -> str:
    """Recupera resposta com fallback para LLM"""
    
    # 1. Tenta cache
    cached = cache.get(user_message, context)
    if cached:
        print("Cache hit!")
        return cached
    
    # 2. Fallback para LLM
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": user_message}]
    ).content[0].text
    
    # 3. Armazena em cache
    cache.set(user_message, response, context)
    return response
```

#### Cache com Redis (Produção)
```python
import redis
import json
from typing import Optional

class RedisResponseCache:
    """Cache distribuído com Redis para aplicações em escala"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.ttl = 1800  # 30 minutos
    
    def get(self, user_message: str, context_id: str = "global") -> Optional[str]:
        """Recupera do Redis"""
        key = f"chat_response:{context_id}:{hashlib.md5(user_message.encode()).hexdigest()}"
        value = self.redis.get(key)
        return value.decode() if value else None
    
    def set(self, user_message: str, response: str, context_id: str = "global"):
        """Armazena no Redis com TTL"""
        key = f"chat_response:{context_id}:{hashlib.md5(user_message.encode()).hexdigest()}"
        self.redis.setex(key, self.ttl, response)
    
    def invalidate_context(self, context_id: str):
        """Invalida todas respostas de um contexto"""
        pattern = f"chat_response:{context_id}:*"
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)

# Configuração em aplicação FastAPI
from fastapi import FastAPI

app = FastAPI()
cache = RedisResponseCache()

@app.post("/chat")
async def chat(message: str, user_id: str):
    # Tenta cache por usuário
    cached = cache.get(message, context_id=f"user:{user_id}")
    if cached:
        return {"response": cached, "source": "cache"}
    
    # Chama LLM
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": message}]
    ).content[0].text
    
    # Armazena cache
    cache.set(message, response, context_id=f"user:{user_id}")
    
    return {"response": response, "source": "llm"}
```

---

### 1.3 Query Result Caching (Banco de Dados)

#### Query Caching para Supabase
```python
from supabase import create_client
import hashlib
import time

class DatabaseQueryCache:
    """Cache de queries com invalidação por tabelas"""
    
    def __init__(self, supabase_client, ttl_seconds: int = 300):
        self.db = supabase_client
        self.cache = {}
        self.ttl = ttl_seconds
        
        # Rastreia qual tabelas cada query usa
        self.table_dependencies = {}
    
    def _execute_with_cache(self, query_func, query_key: str, tables: list):
        """Executa query com cache inteligente"""
        
        # Verifica se cache está válido
        if query_key in self.cache:
            cached = self.cache[query_key]
            if time.time() < cached['expires_at']:
                return cached['result']
        
        # Executa query
        result = query_func()
        
        # Armazena com metadados
        self.cache[query_key] = {
            'result': result,
            'expires_at': time.time() + self.ttl,
            'tables': tables
        }
        
        # Rastreia dependências
        for table in tables:
            if table not in self.table_dependencies:
                self.table_dependencies[table] = []
            self.table_dependencies[table].append(query_key)
        
        return result
    
    def invalidate_table(self, table_name: str):
        """Invalida todas queries que usam uma tabela"""
        if table_name in self.table_dependencies:
            for query_key in self.table_dependencies[table_name]:
                if query_key in self.cache:
                    del self.cache[query_key]

# Uso em aplicação
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
db_cache = DatabaseQueryCache(supabase, ttl_seconds=600)

def get_recent_items(category: str):
    """Recupera itens com cache"""
    
    query_key = f"items:{category}"
    
    def query_func():
        response = (
            supabase.table('itens_licitacao')
            .select('*')
            .eq('categoria_v2', category)
            .order('created_at', desc=True)
            .limit(50)
            .execute()
        )
        return response.data
    
    # Executa com cache, marca dependência na tabela
    return db_cache._execute_with_cache(
        query_func, 
        query_key, 
        tables=['itens_licitacao']
    )

def update_item(item_id: int, data: dict):
    """Atualiza item e invalida cache"""
    
    # Atualiza no banco
    supabase.table('itens_licitacao').update(data).eq('id', item_id).execute()
    
    # Invalida todas queries que usam esta tabela
    db_cache.invalidate_table('itens_licitacao')
```

---

## 2. CONSULTAS PRÉ-PROGRAMADAS

### 2.1 Query Templating

```python
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class QueryTemplate:
    """Templates de queries pré-compiladas para performance"""
    
    # Agrícola específico para seu projeto
    TEMPLATES = {
        'get_agricultural_items': """
            SELECT 
                id, descricao, categoria_v2, qt_solicitada, valor,
                relevante_agro, created_at
            FROM itens_licitacao
            WHERE relevante_agro = true
            AND categoria_v2 = $1
            AND created_at > $2
            ORDER BY created_at DESC
            LIMIT $3
        """,
        
        'get_demand_by_year': """
            SELECT 
                DATE_TRUNC('year', created_at)::DATE as ano,
                categoria_v2,
                SUM(qt_solicitada) as total_quantidade,
                SUM(valor) as total_valor,
                COUNT(*) as count_items
            FROM itens_licitacao
            WHERE relevante_agro = true
            GROUP BY DATE_TRUNC('year', created_at), categoria_v2
            ORDER BY ano DESC, total_valor DESC
        """,
        
        'get_supplier_coverage': """
            SELECT 
                f.id, f.nome,
                COUNT(DISTINCT p.id) as total_bids,
                COUNT(DISTINCT CASE WHEN il.relevante_agro THEN 1 END) 
                    as agro_bids,
                SUM(il.valor) as total_value
            FROM fornecedores f
            LEFT JOIN participacoes p ON f.id = p.fornecedor_id
            LEFT JOIN itens_licitacao il ON p.item_id = il.id
            WHERE il.relevante_agro = true
            GROUP BY f.id, f.nome
            ORDER BY agro_bids DESC
        """
    }
    
    @staticmethod
    def get_template(name: str) -> str:
        """Recupera template de query"""
        return QueryTemplate.TEMPLATES.get(name)
    
    @staticmethod
    def compile(template_name: str, params: List[Any]) -> tuple:
        """Retorna template compilado com parâmetros preparados"""
        template = QueryTemplate.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        return (template, params)


# Uso em aplicação
def get_agricultural_demand_by_category(category: str, years: int = 1):
    """Exemplo: Usar template pré-compilado"""
    
    from datetime import datetime, timedelta
    
    template, params = QueryTemplate.compile(
        'get_agricultural_items',
        [
            category,
            (datetime.now() - timedelta(days=365*years)),
            100
        ]
    )
    
    # Executa com prepared statement
    result = supabase.rpc(
        'execute_prepared_query',
        {
            'query_template': template,
            'params': params
        }
    ).execute()
    
    return result.data
```

### 2.2 Prepared Statements com Supabase

```python
class PreparedQueries:
    """Queries otimizadas e reutilizáveis"""
    
    # Cache de prepared statements
    _prepared = {}
    
    @staticmethod
    def get_items_by_category_and_date(
        supabase_client,
        category: str,
        start_date: str,
        end_date: str,
        limit: int = 50
    ):
        """Query pré-otimizada: Itens por categoria e data"""
        
        return (
            supabase_client
            .from_('itens_licitacao')
            .select('id, descricao, categoria_v2, qt_solicitada, valor, relevante_agro')
            .eq('categoria_v2', category)
            .gte('created_at', start_date)
            .lte('created_at', end_date)
            .order('valor', desc=True)
            .limit(limit)
            .execute()
        )
    
    @staticmethod
    def get_suppliers_by_agricultural_participation(
        supabase_client,
        min_bids: int = 5
    ):
        """Query pré-otimizada: Fornecedores com bom histórico agrícola"""
        
        return supabase_client.rpc(
            'get_qualified_suppliers',  # Função PL/pgSQL no Supabase
            {'min_bids': min_bids}
        ).execute()
    
    @staticmethod
    def get_commitment_status(
        supabase_client,
        processo_id: int
    ):
        """Query: Status de empenhos (rápido com índice)"""
        
        return (
            supabase_client
            .from_('empenhos')
            .select('numero, ano, data_empenho, status')
            .eq('licitacao_id', processo_id)
            .order('data_empenho', desc=True)
            .execute()
        )

# Índices recomendados para performance
RECOMMENDED_INDEXES = """
-- Performance para chat queries
CREATE INDEX idx_itens_categoria_agro 
    ON itens_licitacao(categoria_v2, relevante_agro, created_at DESC);

CREATE INDEX idx_participacoes_fornecedor 
    ON participacoes(fornecedor_id, item_id);

CREATE INDEX idx_empenhos_licitacao 
    ON empenhos(licitacao_id, status);

-- Para busca vetorial (RAG)
CREATE INDEX idx_pdf_chunks_embedding 
    ON pdf_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""
```

### 2.3 Result Pre-computation (Materialized Views)

```python
"""
Pré-computa resultados caros para queries rápidas em tempo real
"""

# SQL a executar no Supabase
MATERIALIZED_VIEWS = """
-- View: Demanda agrícola por ano e categoria
CREATE MATERIALIZED VIEW vw_demanda_agro_ano AS
SELECT 
    DATE_TRUNC('year', il.created_at)::DATE as ano,
    il.categoria_v2,
    COUNT(*) as total_itens,
    SUM(il.qt_solicitada) as total_quantidade,
    SUM(il.valor) as total_valor,
    AVG(il.valor) as valor_medio,
    MIN(il.valor) as valor_minimo,
    MAX(il.valor) as valor_maximo
FROM itens_licitacao il
WHERE il.relevante_agro = true
GROUP BY DATE_TRUNC('year', il.created_at), il.categoria_v2
WITH DATA;

CREATE INDEX idx_vw_demanda_ano ON vw_demanda_agro_ano(ano DESC, total_valor DESC);

-- View: Cobertura de classificação
CREATE MATERIALIZED VIEW vw_cobertura_classificacao AS
SELECT 
    categoria_v2,
    COUNT(*) as total_items,
    COUNT(CASE WHEN relevante_agro THEN 1 END) as agro_items,
    ROUND(
        COUNT(CASE WHEN relevante_agro THEN 1 END)::numeric / 
        COUNT(*) * 100, 2
    ) as coverage_percent
FROM itens_licitacao
GROUP BY categoria_v2
WITH DATA;

-- View: Fornecedores com histórico agrícola
CREATE MATERIALIZED VIEW vw_suppliers_agricultural AS
SELECT 
    f.id, f.nome,
    COUNT(DISTINCT p.id) as total_participations,
    COUNT(DISTINCT CASE WHEN il.relevante_agro THEN p.id END) as agro_participations,
    ROUND(
        COUNT(DISTINCT CASE WHEN il.relevante_agro THEN p.id END)::numeric / 
        COUNT(DISTINCT p.id) * 100, 2
    ) as agro_participation_rate,
    SUM(il.valor) as total_value,
    SUM(CASE WHEN il.relevante_agro THEN il.valor END) as agro_value
FROM fornecedores f
LEFT JOIN participacoes p ON f.id = p.fornecedor_id
LEFT JOIN itens_licitacao il ON p.item_id = il.id
GROUP BY f.id, f.nome
WITH DATA;

CREATE INDEX idx_vw_suppliers_agro_rate ON vw_suppliers_agricultural(agro_participation_rate DESC);
"""

# Função para refrescar views (usar em cron job)
def refresh_materialized_views():
    """Atualiza views à noite (fora de picos)"""
    
    from supabase import create_client
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    views_to_refresh = [
        'vw_demanda_agro_ano',
        'vw_cobertura_classificacao',
        'vw_suppliers_agricultural'
    ]
    
    for view_name in views_to_refresh:
        try:
            supabase.rpc('refresh_materialized_view', {'view_name': view_name}).execute()
            print(f"Refreshed {view_name}")
        except Exception as e:
            print(f"Error refreshing {view_name}: {e}")

# Cron job (usar APScheduler)
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    refresh_materialized_views,
    'cron',
    hour=2,  # 2 AM todos os dias
    minute=0
)
scheduler.start()
```

### 2.4 Quando Usar Query Pré-programada vs Dinâmica

```python
# DIRETRIZ PRÁTICA

class QueryStrategy:
    """Decisão: Template vs Dynamic Query"""
    
    @staticmethod
    def should_use_template(query_characteristics: dict) -> bool:
        """
        Use TEMPLATES quando:
        - Frequência > 10x por hora (padrões conhecidos)
        - Latência crítica (< 500ms)
        - Índices estão otimizados
        - Parâmetros são previsíveis
        """
        
        criteria = {
            'high_frequency': query_characteristics.get('requests_per_hour', 0) > 10,
            'critical_latency': query_characteristics.get('required_latency_ms', 0) < 500,
            'indexed': query_characteristics.get('has_indexes', False),
            'predictable_params': query_characteristics.get('param_cardinality', 0) < 100
        }
        
        # Precisa de 3+ critérios
        return sum(criteria.values()) >= 3
    
    @staticmethod
    def should_use_materialized_view(query_characteristics: dict) -> bool:
        """
        Use MATERIALIZED VIEWS quando:
        - Dados mudam lentamente (< 1x por hora)
        - Agregações complexas
        - Múltiplas JOINs
        - Historial acumulativo (anos)
        """
        
        criteria = {
            'slow_change_rate': query_characteristics.get('change_frequency', 'hourly') != 'realtime',
            'complex_aggregation': query_characteristics.get('join_count', 0) > 2,
            'historical_data': query_characteristics.get('has_historical', False),
            'high_cardinality_results': query_characteristics.get('avg_result_rows', 0) > 1000
        }
        
        return sum(criteria.values()) >= 3
    
    @staticmethod
    def should_use_dynamic_query(query_characteristics: dict) -> bool:
        """
        Use DYNAMIC QUERIES quando:
        - Dados mudam constantemente (realtime)
        - Filtros variam muito (> 1000 combinações)
        - Exploratory queries
        - Primeira consulta de um usuário
        """
        
        criteria = {
            'realtime_data': query_characteristics.get('change_frequency') == 'realtime',
            'high_param_variation': query_characteristics.get('param_cardinality', 0) > 1000,
            'exploratory': query_characteristics.get('is_exploratory', False)
        }
        
        return sum(criteria.values()) >= 2


# Exemplos aplicados
QUERY_STRATEGIES = {
    'get_items_by_category': {  # Use TEMPLATE
        'requests_per_hour': 150,
        'required_latency_ms': 200,
        'has_indexes': True,
        'param_cardinality': 12,  # 12 categorias
    },
    'get_demand_analysis': {  # Use MATERIALIZED VIEW
        'change_frequency': 'daily',
        'join_count': 3,
        'has_historical': True,
        'avg_result_rows': 5000,
    },
    'search_suppliers_by_criteria': {  # Use DYNAMIC
        'change_frequency': 'realtime',
        'param_cardinality': 5000,
        'is_exploratory': True,
    }
}
```

---

## 3. PADRÕES ARQUITETURAIS

### 3.1 Request Batching

#### Batch API (Mais barato: 50% desconto)
```python
import json
import time
from typing import List, Dict, Any

class BatchProcessor:
    """
    Processa múltiplos requests em lote
    Custo: 50% de desconto vs API normal
    TTL: até 24 horas
    """
    
    def __init__(self, client, model: str = "claude-opus-4-5"):
        self.client = client
        self.model = model
        self.batch_queue = []
    
    def add_request(
        self,
        user_message: str,
        system_prompt: str = None,
        request_id: str = None
    ) -> str:
        """Adiciona request ao batch"""
        
        if request_id is None:
            request_id = f"req_{len(self.batch_queue)}_{int(time.time())}"
        
        request = {
            "custom_id": request_id,
            "params": {
                "model": self.model,
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": user_message}
                ]
            }
        }
        
        if system_prompt:
            request["params"]["system"] = system_prompt
        
        self.batch_queue.append(request)
        return request_id
    
    def submit_batch(self) -> Dict[str, Any]:
        """Submete batch e retorna ID para polling"""
        
        if not self.batch_queue:
            raise ValueError("No requests in batch")
        
        # Cria file para upload
        batch_file_content = "\n".join(
            json.dumps(req) for req in self.batch_queue
        )
        
        # Envia para processamento
        response = self.client.beta.messages.batches.create(
            requests=self.batch_queue
        )
        
        self.batch_queue = []  # Limpa queue
        
        return {
            "batch_id": response.id,
            "created_at": response.created_at,
            "state": response.state,
            "request_counts": response.request_counts
        }
    
    def get_batch_results(self, batch_id: str):
        """Recupera resultados do batch"""
        
        batch = self.client.beta.messages.batches.retrieve(batch_id)
        
        if batch.state == "completed":
            # Processa resultados
            results = {}
            for result in batch.result_ids:  # API v1beta
                results[result.id] = result.message
            return results
        elif batch.state == "processing":
            return {"status": "processing", "batch_id": batch_id}
        elif batch.state == "failed":
            return {"status": "failed", "errors": batch.errors}


# Exemplo de uso
def process_documents_in_batch(documents: List[str]):
    """Processa múltiplos documentos com 50% desconto"""
    
    batch = BatchProcessor(client)
    
    # Adiciona todos documentos ao batch
    request_ids = []
    for i, doc in enumerate(documents):
        req_id = batch.add_request(
            user_message=f"Classify this document:\n{doc}",
            system_prompt="You are a document classifier.",
            request_id=f"doc_{i}"
        )
        request_ids.append(req_id)
    
    # Submete batch
    batch_info = batch.submit_batch()
    print(f"Batch {batch_info['batch_id']} submitted")
    
    # Polling para completar (pode levar minutos/horas)
    batch_id = batch_info['batch_id']
    max_attempts = 120  # 2 horas com 1 min de polling
    
    for attempt in range(max_attempts):
        results = batch.get_batch_results(batch_id)
        
        if results.get('status') == 'completed':
            print(f"Batch completed after {attempt} minutes")
            return results
        
        if results.get('status') == 'failed':
            print(f"Batch failed: {results.get('errors')}")
            return None
        
        print(f"Batch still processing... ({attempt + 1}/{max_attempts})")
        time.sleep(60)  # Polling a cada 1 min
    
    return None
```

#### Continuous Batching (Realtime)
```python
from asyncio import Queue
import asyncio
from datetime import datetime

class ContinuousBatcher:
    """
    Agrupa requests em tempo real
    Trade-off: latência aumenta 50-200ms para economizar custos
    """
    
    def __init__(
        self,
        client,
        batch_size: int = 10,
        batch_timeout_ms: int = 200,
        max_queue_size: int = 1000
    ):
        self.client = client
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms / 1000
        self.request_queue: Queue = Queue(maxsize=max_queue_size)
        self.results = {}
    
    async def add_request(self, request: Dict) -> str:
        """Adiciona request à fila (retorna future para resultado)"""
        request_id = f"req_{int(time.time() * 1000)}"
        request['id'] = request_id
        
        await self.request_queue.put(request)
        return request_id
    
    async def process_batches(self):
        """Processa batches contínuos"""
        
        while True:
            batch = []
            deadline = time.time() + self.batch_timeout_ms
            
            # Coleta requests até batch_size ou timeout
            while len(batch) < self.batch_size and time.time() < deadline:
                try:
                    # Timeout = remaining time before deadline
                    wait_time = max(0.001, deadline - time.time())
                    request = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=wait_time
                    )
                    batch.append(request)
                except asyncio.TimeoutError:
                    break
            
            if batch:
                # Processa batch
                responses = await self._process_batch(batch)
                for req_id, response in zip([r['id'] for r in batch], responses):
                    self.results[req_id] = response
    
    async def _process_batch(self, batch: List[Dict]):
        """Executa batch de requests"""
        
        # Aqui você chamaria a API em paralelo
        # Para Anthropic, seria um request com múltiplas mensagens
        
        responses = []
        for request in batch:
            response = await asyncio.to_thread(
                self._call_api,
                request
            )
            responses.append(response)
        
        return responses
    
    def _call_api(self, request: Dict):
        """Chamada individual à API"""
        return self.client.messages.create(**request)
    
    async def get_result(self, request_id: str, timeout_seconds: int = 30):
        """Aguarda resultado específico"""
        
        deadline = time.time() + timeout_seconds
        
        while time.time() < deadline:
            if request_id in self.results:
                return self.results.pop(request_id)
            
            await asyncio.sleep(0.01)  # Poll a cada 10ms
        
        raise TimeoutError(f"Request {request_id} timed out")


# Exemplo FastAPI
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()
batcher = ContinuousBatcher(client, batch_size=32, batch_timeout_ms=150)

@app.on_event("startup")
async def startup():
    asyncio.create_task(batcher.process_batches())

@app.post("/chat")
async def chat(message: str):
    request = {
        "model": "claude-opus-4-5",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": message}]
    }
    
    request_id = await batcher.add_request(request)
    response = await batcher.get_result(request_id, timeout_seconds=5)
    
    return JSONResponse({"response": response.content[0].text})
```

### 3.2 Streaming vs Buffering

#### Streaming com Server-Sent Events (SSE)
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(message: str):
    """Streaming resposta para melhor UX"""
    
    async def generate():
        """Generator para SSE"""
        
        # Envia "pensando..."
        yield "data: " + json.dumps({
            "type": "thinking",
            "content": "Processando sua mensagem..."
        }) + "\n\n"
        
        # Cria stream de resposta
        with client.messages.stream(
            model="claude-opus-4-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": message}]
        ) as stream:
            for text in stream.text_stream:
                # Envia token por token
                yield "data: " + json.dumps({
                    "type": "content",
                    "content": text
                }) + "\n\n"
                
                await asyncio.sleep(0.001)  # Pequeno delay
        
        # Envia final
        yield "data: " + json.dumps({
            "type": "done"
        }) + "\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# Cliente JavaScript/TypeScript
function subscribeToChat(message: string): void {
    const eventSource = new EventSource(`/chat/stream?message=${encodeURIComponent(message)}`);
    
    const messageDiv = document.getElementById('message');
    let isThinking = true;
    
    eventSource.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'thinking') {
            messageDiv.innerHTML = `<em>${data.content}</em>`;
        } else if (data.type === 'content') {
            if (isThinking) {
                messageDiv.innerHTML = '';
                isThinking = false;
            }
            
            // Buffer tokens para smooth rendering
            messageDiv.innerHTML += escapeHtml(data.content);
            
            // Scroll to bottom
            messageDiv.scrollTop = messageDiv.scrollHeight;
        } else if (data.type === 'done') {
            eventSource.close();
        }
    };
}
```

#### Buffering com Batcher (Economia)
```python
class BufferedStreamBatcher:
    """
    Estratégia híbrida: buffer tokens, stream em groups
    Melhora economia sem perder UX
    """
    
    def __init__(self, buffer_size: int = 5, buffer_timeout_ms: int = 100):
        self.buffer_size = buffer_size
        self.buffer_timeout_ms = buffer_timeout_ms / 1000
        self.token_buffer = []
        self.last_send = time.time()
    
    async def stream_with_buffering(self, message: str):
        """Stream com buffer inteligente"""
        
        async def generate():
            with client.messages.stream(
                model="claude-opus-4-5",
                max_tokens=2048,
                messages=[{"role": "user", "content": message}]
            ) as stream:
                for text in stream.text_stream:
                    self.token_buffer.append(text)
                    
                    # Envia quando buffer cheio OU timeout
                    should_send = (
                        len(self.token_buffer) >= self.buffer_size or
                        (time.time() - self.last_send) >= self.buffer_timeout_ms
                    )
                    
                    if should_send and self.token_buffer:
                        buffered_text = ''.join(self.token_buffer)
                        yield f"data: {json.dumps({'content': buffered_text})}\n\n"
                        self.token_buffer = []
                        self.last_send = time.time()
                
                # Envia restante
                if self.token_buffer:
                    buffered_text = ''.join(self.token_buffer)
                    yield f"data: {json.dumps({'content': buffered_text})}\n\n"
                
                yield "data: {\"done\": true}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/chat/buffered")
async def chat_buffered(message: str):
    batcher = BufferedStreamBatcher(buffer_size=10, buffer_timeout_ms=150)
    return await batcher.stream_with_buffering(message)
```

### 3.3 Rate Limiting Estratégico

```python
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

class SmartRateLimiter:
    """
    Rate limiting inteligente que respeita:
    - Quotas do usuário (request/hora)
    - Limites da API (5000 RPM)
    - Prioridade (usuarios premium vs gratuitos)
    """
    
    def __init__(self):
        self.user_counters: Dict[str, list] = {}
        self.api_window = []
        self.api_max_rpm = 5000
        self.user_limits = {
            'premium': 1000,  # requests/hora
            'standard': 100,
            'free': 20
        }
    
    def get_user_tier(self, user_id: str) -> str:
        """Obtém tier do usuário"""
        # Implementar lógica de autenticação
        return 'standard'
    
    async def acquire(self, user_id: str) -> bool:
        """Tenta adquirir rate limit token"""
        
        now = datetime.now()
        user_tier = self.get_user_tier(user_id)
        user_limit = self.user_limits[user_tier]
        
        # Limpa janela antiga (< 1 min)
        hour_ago = now - timedelta(hours=1)
        if user_id not in self.user_counters:
            self.user_counters[user_id] = []
        
        self.user_counters[user_id] = [
            t for t in self.user_counters[user_id] if t > hour_ago
        ]
        
        # Verifica limite do usuário
        if len(self.user_counters[user_id]) >= user_limit:
            return False
        
        # Verifica limite global da API
        minute_ago = now - timedelta(minutes=1)
        self.api_window = [t for t in self.api_window if t > minute_ago]
        
        if len(self.api_window) >= self.api_max_rpm:
            # Fila para próximo minuto
            wait_time = (self.api_window[0] + timedelta(minutes=1) - now).total_seconds()
            await asyncio.sleep(max(0, wait_time + 0.1))
            return await self.acquire(user_id)
        
        # Concede token
        self.user_counters[user_id].append(now)
        self.api_window.append(now)
        
        return True
    
    def get_quota_info(self, user_id: str) -> Dict:
        """Retorna info de quota para cliente"""
        
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        user_tier = self.get_user_tier(user_id)
        
        used = len([
            t for t in self.user_counters.get(user_id, [])
            if t > hour_ago
        ])
        limit = self.user_limits[user_tier]
        
        return {
            "tier": user_tier,
            "used": used,
            "limit": limit,
            "remaining": limit - used,
            "reset_at": (now + timedelta(hours=1)).isoformat()
        }


# Middleware FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()
rate_limiter = SmartRateLimiter()

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    if request.url.path.startswith("/chat"):
        user_id = request.headers.get("x-user-id", "anonymous")
        
        if not await rate_limiter.acquire(user_id):
            quota = rate_limiter.get_quota_info(user_id)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "quota": quota
                }
            )
    
    response = await call_next(request)
    return response
```

---

## 4. OTIMIZAÇÕES DE BANCO DE DADOS

### 4.1 Query Optimization Pattern

```python
"""
Analisar e otimizar queries no Supabase
"""

class QueryAnalyzer:
    """Identifica queries lentas e sugere índices"""
    
    def __init__(self, supabase_client):
        self.db = supabase_client
        self.slow_query_threshold_ms = 500
    
    def analyze_query_plan(self, query: str) -> Dict:
        """Obtém plano de execução (EXPLAIN)"""
        
        # Use pg_stat_statements view
        result = self.db.rpc('get_query_plan', {'query': query}).execute()
        
        return {
            'sequential_scan': 'Seq Scan' in result.data,
            'bitmap_scan': 'Bitmap Scan' in result.data,
            'index_scan': 'Index Scan' in result.data,
            'join_type': self._extract_join(result.data),
            'estimated_rows': self._extract_estimate(result.data)
        }
    
    def suggest_indexes(self) -> List[str]:
        """Sugere índices baseado em queries frequentes"""
        
        # Query pg_stat_statements
        result = self.db.rpc('get_missing_indexes').execute()
        
        suggestions = []
        for row in result.data:
            if row['scan_count'] > 100 and row['sequential_scan_pct'] > 80:
                # Sugere índice
                suggestions.append({
                    'table': row['table_name'],
                    'columns': row['frequently_filtered'],
                    'reason': f"{row['scan_count']} scans, {row['sequential_scan_pct']}% sequential"
                })
        
        return suggestions


# Índices recomendados para seu projeto
CRITICAL_INDEXES = """
-- Busca por item
CREATE INDEX CONCURRENTLY idx_itens_categoria_data 
ON itens_licitacao(categoria_v2, created_at DESC)
WHERE relevante_agro = true;

-- Busca por fornecedor
CREATE INDEX CONCURRENTLY idx_participacoes_fornecedor_item
ON participacoes(fornecedor_id, item_id, licitacao_id);

-- Busca por processo
CREATE INDEX CONCURRENTLY idx_empenhos_licitacao_status
ON empenhos(licitacao_id, status, data_empenho DESC);

-- Busca vetorial (RAG)
CREATE INDEX CONCURRENTLY idx_pdf_chunks_embedding
ON pdf_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Busca por texto
CREATE INDEX idx_pdf_chunks_text_search 
ON pdf_chunks USING gin (to_tsvector('portuguese', chunk_text));
"""
```

### 4.2 Connection Pooling

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
import os

# Configuração otimizada para aplicação com múltiplas threads
engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
    poolclass=QueuePool,
    pool_size=20,  # Connections mantidas no pool
    max_overflow=10,  # Connections adicionais quando necessário
    pool_recycle=3600,  # Recicla connection a cada hora
    pool_pre_ping=True,  # Testa connection antes de usar
    echo=False,  # Set True para debug
    connect_args={
        "connect_timeout": 10,
        "application_name": "agroia-rmc-chat"
    }
)

# Uso com FastAPI
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/chat")
async def chat(message: str, db: Session = Depends(get_db)):
    # db já está em pool, reusável
    items = db.query(Item).filter(...).all()
    return {"response": process_with_items(items, message)}
```

### 4.3 Materialized Views (Pré-computadas)

```sql
-- Atualizar diariamente à noite (baixo tráfego)
CREATE OR REPLACE FUNCTION refresh_all_views() RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_demanda_agro_ano;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_cobertura_classificacao;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_suppliers_agricultural;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_empenhos_status;
END;
$$ LANGUAGE plpgsql;

-- Criar trigger para refresh automático (opcional)
CREATE TRIGGER refresh_views_after_update
AFTER INSERT OR UPDATE OR DELETE ON itens_licitacao
FOR EACH STATEMENT
EXECUTE FUNCTION schedule_view_refresh();
```

---

## 5. UX & FEEDBACK

### 5.1 Skeleton Loading & Progressive Disclosure

```tsx
// React component com skeleton loading
import React, { useState, useEffect } from 'react';

const ChatMessage: React.FC<{ message: string }> = ({ message }) => {
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [thinking, setThinking] = useState(true);

  useEffect(() => {
    const eventSource = new EventSource(`/chat/stream?msg=${encodeURIComponent(message)}`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'thinking') {
        setThinking(true);
        setContent('');
      } else if (data.type === 'content') {
        setThinking(false);
        setContent(prev => prev + data.content);
      } else if (data.type === 'done') {
        setIsLoading(false);
        eventSource.close();
      }
    };

    return () => eventSource.close();
  }, [message]);

  return (
    <div className="message">
      {thinking && <LoadingSkeleton />}
      {!thinking && <Markdown content={content} />}
    </div>
  );
};

const LoadingSkeleton: React.FC = () => (
  <div className="skeleton">
    <div className="skeleton-line" />
    <div className="skeleton-line" style={{ width: '80%' }} />
    <div className="skeleton-line" style={{ width: '60%' }} />
  </div>
);

// CSS para animação de loading
const styles = `
.skeleton {
  animation: skeleton-loading 1s linear infinite alternate;
}

.skeleton-line {
  height: 12px;
  background: #e0e0e0;
  margin: 8px 0;
  border-radius: 4px;
}

@keyframes skeleton-loading {
  0% { opacity: 1; }
  100% { opacity: 0.5; }
}
`;
```

### 5.2 Progressive Disclosure Pattern

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProgressiveResponse:
    """Resposta estruturada em níveis de detalhe"""
    
    summary: str  # Resposta rápida (< 100 tokens)
    details: Optional[str] = None  # Detalhes (< 500 tokens)
    examples: Optional[List[str]] = None  # Exemplos
    sources: Optional[List[str]] = None  # Referências
    
    def to_json(self, level: str = 'summary'):
        """Retorna resposta por nível"""
        
        if level == 'summary':
            return {'content': self.summary, 'has_details': self.details is not None}
        elif level == 'details':
            return {
                'content': self.details,
                'has_examples': len(self.examples) > 0 if self.examples else False
            }
        elif level == 'full':
            return {
                'summary': self.summary,
                'details': self.details,
                'examples': self.examples,
                'sources': self.sources
            }


def generate_progressive_response(message: str) -> ProgressiveResponse:
    """Gera resposta com múltiplos níveis"""
    
    system = """You are a helpful agriculture assistant.
    
    Respond in JSON with:
    - "summary": Brief answer (1-2 sentences)
    - "details": More information if needed
    - "examples": Practical examples
    - "sources": References
    """
    
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": message}]
    )
    
    try:
        import json
        data = json.loads(response.content[0].text)
        return ProgressiveResponse(**data)
    except:
        # Fallback
        return ProgressiveResponse(
            summary=response.content[0].text,
            details=None
        )


# API endpoint com progressive disclosure
@app.post("/chat/progressive")
async def chat_progressive(message: str, detail_level: str = 'summary'):
    """
    detail_level: 'summary' | 'details' | 'full'
    """
    
    response = generate_progressive_response(message)
    return response.to_json(detail_level)
```

### 5.3 User Expectations & Feedback Loop

```python
from enum import Enum
from datetime import datetime

class ResponseQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"

class UserFeedback:
    """Captura feedback para melhorar experiência"""
    
    def __init__(self, supabase_client):
        self.db = supabase_client
    
    def record_feedback(
        self,
        message_id: str,
        response_time_ms: int,
        quality: ResponseQuality,
        user_id: str,
        notes: Optional[str] = None
    ):
        """Registra feedback do usuário"""
        
        self.db.table('feedback_responses').insert({
            'message_id': message_id,
            'user_id': user_id,
            'response_time_ms': response_time_ms,
            'quality': quality.value,
            'notes': notes,
            'created_at': datetime.now().isoformat()
        }).execute()
    
    def get_satisfaction_metrics(self, timeframe_days: int = 7) -> Dict:
        """Analisa satisfação do usuário"""
        
        result = self.db.rpc('get_satisfaction_metrics', {
            'days': timeframe_days
        }).execute()
        
        return {
            'avg_response_time_ms': result.data[0]['avg_response_time'],
            'quality_distribution': result.data[0]['quality_scores'],
            'satisfaction_rate': result.data[0]['satisfaction_percent'],
            'trending': result.data[0]['trend']  # up/down/stable
        }


# FastAPI endpoint com feedback
@app.post("/chat")
async def chat_with_feedback(message: str, user_id: str):
    """Chat com captura automática de metrics"""
    
    import time
    import uuid
    
    message_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Streaming response
        response_text = ""
        with client.messages.stream(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": message}]
        ) as stream:
            for text in stream.text_stream:
                response_text += text
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "id": message_id,
            "response": response_text,
            "response_time_ms": response_time_ms,
            "feedback_url": f"/feedback/{message_id}"
        }
    
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        print(f"Error: {e}, Response time: {response_time_ms}ms")
        raise

@app.post("/feedback/{message_id}")
async def submit_feedback(
    message_id: str,
    quality: ResponseQuality,
    user_id: str,
    notes: Optional[str] = None
):
    """Submete feedback do usuário"""
    
    feedback = UserFeedback(supabase)
    
    # Recupera response time original
    # (você teria armazenado isso em cache anteriormente)
    response_time_ms = get_cached_response_time(message_id)
    
    feedback.record_feedback(
        message_id=message_id,
        response_time_ms=response_time_ms,
        quality=quality,
        user_id=user_id,
        notes=notes
    )
    
    # Agradecer feedback
    return {
        "message": "Obrigado pelo feedback! Estamos melhorando.",
        "status": "recorded"
    }
```

---

## 6. CHECKLIST DE IMPLEMENTAÇÃO

### Para seu Projeto (AgroIA-RMC)

- [ ] **Prompt Caching**
  - [ ] Sistema prompt como cache_control tipo "ephemeral" (5 min)
  - [ ] Contexto agrícola (classificações, categorias) em cache estável
  - [ ] Rastrear cache hits/misses via `response.usage`

- [ ] **Response Caching**
  - [ ] Cache Redis para respostas de classificação
  - [ ] TTL de 30 minutos para queries por categoria
  - [ ] Invalidação ao atualizar documentos

- [ ] **Query Optimization**
  - [ ] Índices em `(categoria_v2, created_at DESC)` para itens
  - [ ] Índices em `(fornecedor_id, licitacao_id)` para participações
  - [ ] Materialized view para demanda anual

- [ ] **Batch Processing**
  - [ ] Suportar batch API para análise de múltiplos documentos (50% desconto)
  - [ ] Usar para processamento de PDFs (fase 3)

- [ ] **Streaming**
  - [ ] SSE para responses LLM em tempo real
  - [ ] Skeleton loading enquanto "Pensando..."
  - [ ] Alvo: TTFT < 500ms

- [ ] **UX Feedback**
  - [ ] Capturar tempo de resposta
  - [ ] Permitir feedback de qualidade
  - [ ] Monitorar satisfação semanal

---

## 7. REFERÊNCIAS E FONTES

Consulte os seguintes recursos para atualizar-se:

- [Prompt Caching Guide (2026)](https://sureprompts.com/blog/prompt-caching-guide-2026)
- [Claude API Documentation - Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Token Optimization Strategies](https://dasroot.net/posts/2026/04/token-optimization-llm-costs-prompt-engineering/)
- [Database Optimization 2026](https://theclaymedia.com/database-optimization-2026/)
- [Streaming LLM Responses Guide](https://dev.to/pockit_tools/the-complete-guide-to-streaming-llm-responses-in-web-applications-from-sse-to-real-time-ui-3534)
- [Batch Processing Patterns](https://redis.io/blog/large-language-model-operations-guide/)
- [Anthropic Claude Pricing](https://www.anthropic.com/pricing)

---

Última atualização: Abril 2026
Gerado para AgroIA-RMC Project
