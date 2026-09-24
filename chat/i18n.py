"""Idioma das respostas dos agentes (pt/en/es).

O frontend envia `idioma` em cada chamada. Os system prompts continuam em
português (e cacheados); a diretiva de idioma vai num bloco separado, depois
do breakpoint de cache, para não invalidar o cache do prompt principal.
"""

IDIOMAS = ("pt", "en", "es")
IDIOMA_PADRAO = "pt"

_NOMES = {"pt": "português do Brasil", "en": "English", "es": "español"}


def normalizar_idioma(valor: str | None) -> str:
    """'en-US' → 'en'; desconhecido/vazio → 'pt'."""
    codigo = (valor or "").strip().lower()[:2]
    return codigo if codigo in IDIOMAS else IDIOMA_PADRAO


def diretiva_idioma(idioma: str | None) -> str:
    """Instrução de idioma de saída para anexar ao system prompt."""
    idioma = normalizar_idioma(idioma)
    if idioma == "pt":
        return "IDIOMA DA RESPOSTA: responda sempre em português do Brasil."
    nome = _NOMES[idioma]
    return (
        f"RESPONSE LANGUAGE — MANDATORY: write your ENTIRE answer in {nome}, "
        "including headings, table headers, bullet points, suggestions and follow-up "
        "questions, even though the instructions above are in Portuguese and the data "
        "returned by the tools is in Portuguese. Translate product/crop names and "
        "category labels naturally (e.g. ALFACE → lettuce/lechuga), but keep proper "
        "names, bidding process numbers, program acronyms (PNAE, PAA, SMSAN, FAAC, "
        "CEASA, CONAB) and currency values (R$) unchanged. When calling tools, keep "
        "using the Portuguese parameter values the tools expect."
    )


def com_diretiva(system_prompt: str, idioma: str | None) -> str:
    """System prompt + diretiva de idioma num único texto (motores não-Claude)."""
    return f"{system_prompt}\n\n{diretiva_idioma(idioma)}"


_MSGS: dict[str, dict[str, str]] = {
    "pergunta_invalida": {
        "pt": "Por favor, faça uma pergunta válida.",
        "en": "Please ask a valid question.",
        "es": "Por favor, haga una pregunta válida.",
    },
    "erro_assistente": {
        "pt": "⚠️ Desculpe, houve um erro ao consultar o assistente. Tente novamente.",
        "en": "⚠️ Sorry, there was an error contacting the assistant. Please try again.",
        "es": "⚠️ Lo sentimos, hubo un error al consultar el asistente. Inténtelo de nuevo.",
    },
    "erro_inesperado": {
        "pt": "Desculpe, ocorreu um erro inesperado. Tente novamente.",
        "en": "Sorry, an unexpected error occurred. Please try again.",
        "es": "Lo sentimos, ocurrió un error inesperado. Inténtelo de nuevo.",
    },
    "sem_resposta": {
        "pt": "Não consegui gerar uma resposta. Tente reformular sua pergunta.",
        "en": "I couldn't generate an answer. Try rephrasing your question.",
        "es": "No pude generar una respuesta. Intente reformular su pregunta.",
    },
    "muito_complexa": {
        "pt": "Sua pergunta é muito complexa. Tente dividir em perguntas menores ou mais específicas.",
        "en": "Your question is too complex. Try splitting it into smaller, more specific questions.",
        "es": "Su pregunta es demasiado compleja. Intente dividirla en preguntas más pequeñas o específicas.",
    },
    "status_analisando": {
        "pt": "🔍 Analisando sua pergunta...",
        "en": "🔍 Analyzing your question...",
        "es": "🔍 Analizando su pregunta...",
    },
    "status_banco": {
        "pt": "📊 Consultando o banco de dados...",
        "en": "📊 Querying the database...",
        "es": "📊 Consultando la base de datos...",
    },
    "status_motor": {
        "pt": "🔄 Consultando {motor}...",
        "en": "🔄 Querying {motor}...",
        "es": "🔄 Consultando {motor}...",
    },
    "erro_processar": {
        "pt": "⚠️ Erro ao processar sua pergunta. Tente novamente.",
        "en": "⚠️ Error processing your question. Please try again.",
        "es": "⚠️ Error al procesar su pregunta. Inténtelo de nuevo.",
    },
    "erro_precos": {
        "pt": "⚠️ Erro ao consultar preços. Tente novamente.",
        "en": "⚠️ Error fetching prices. Please try again.",
        "es": "⚠️ Error al consultar precios. Inténtelo de nuevo.",
    },
    "erro_oferta": {
        "pt": "⚠️ Erro ao registrar sua oferta. Tente novamente.",
        "en": "⚠️ Error registering your offer. Please try again.",
        "es": "⚠️ Error al registrar su oferta. Inténtelo de nuevo.",
    },
    "muitas_mensagens": {
        "pt": "Muitas mensagens. Aguarde alguns minutos.",
        "en": "Too many messages. Please wait a few minutes.",
        "es": "Demasiados mensajes. Espere unos minutos.",
    },
    "status_cache": {
        "pt": "📦 Carregando cache...",
        "en": "📦 Loading cache...",
        "es": "📦 Cargando caché...",
    },
    "status_agregando": {
        "pt": "🔍 Agregando dados...",
        "en": "🔍 Aggregating data...",
        "es": "🔍 Agregando datos...",
    },
    "status_ia": {
        "pt": "💡 Analisando com IA...",
        "en": "💡 Analyzing with AI...",
        "es": "💡 Analizando con IA...",
    },
    "erro_alertas": {
        "pt": "Erro ao analisar alertas",
        "en": "Error analyzing alerts",
        "es": "Error al analizar alertas",
    },
    "status_carregando_lics": {
        "pt": "📊 Carregando dados de licitações...",
        "en": "📊 Loading bidding data...",
        "es": "📊 Cargando datos de licitaciones...",
    },
    "status_inconsistencias": {
        "pt": "🔍 Analisando inconsistências...",
        "en": "🔍 Analyzing inconsistencies...",
        "es": "🔍 Analizando inconsistencias...",
    },
    "erro_auditoria": {
        "pt": "Erro ao executar auditoria",
        "en": "Error running audit",
        "es": "Error al ejecutar la auditoría",
    },
    "alerta_critico": {
        "pt": "CRÍTICO: Licitação {processo} com empenho(s) mas SEM documentação",
        "en": "CRITICAL: Bidding {processo} has commitment(s) but NO documentation",
        "es": "CRÍTICO: Licitación {processo} con compromiso(s) pero SIN documentación",
    },
    "alerta_grave": {
        "pt": "GRAVE: Licitação {processo} finalizada SEM documentação",
        "en": "SEVERE: Bidding {processo} completed WITHOUT documentation",
        "es": "GRAVE: Licitación {processo} finalizada SIN documentación",
    },
}


def msg(chave: str, idioma: str | None = None, **kwargs) -> str:
    """Mensagem fixa (status/erro) no idioma pedido, com fallback para pt."""
    textos = _MSGS[chave]
    texto = textos.get(normalizar_idioma(idioma), textos[IDIOMA_PADRAO])
    return texto.format(**kwargs) if kwargs else texto
