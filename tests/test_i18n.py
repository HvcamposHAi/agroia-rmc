"""Idioma das respostas dos agentes (chat/i18n.py + integração no agent)."""
from unittest.mock import MagicMock, patch

from chat.i18n import IDIOMAS, _MSGS, com_diretiva, diretiva_idioma, msg, normalizar_idioma


def test_normalizar_idioma():
    assert normalizar_idioma("en-US") == "en"
    assert normalizar_idioma("ES") == "es"
    assert normalizar_idioma("pt-BR") == "pt"
    assert normalizar_idioma("fr") == "pt"
    assert normalizar_idioma(None) == "pt"
    assert normalizar_idioma("") == "pt"


def test_todas_as_mensagens_tem_os_tres_idiomas():
    for chave, textos in _MSGS.items():
        assert set(textos) == set(IDIOMAS), chave


def test_msg_formata_e_faz_fallback():
    assert msg("status_motor", "en", motor="GPT") == "🔄 Querying GPT..."
    assert "0123/2024" in msg("alerta_grave", "es", processo="0123/2024")
    assert msg("pergunta_invalida", "xx") == msg("pergunta_invalida", "pt")


def test_diretiva_nomeia_o_idioma():
    assert "English" in diretiva_idioma("en")
    assert "español" in diretiva_idioma("es")
    assert "português" in diretiva_idioma("pt")
    assert com_diretiva("PROMPT", "en").startswith("PROMPT\n\n")


def test_chat_stream_envia_diretiva_depois_do_cache():
    """O prompt principal segue cacheado; a diretiva vai num bloco separado."""
    from chat import agent

    final = MagicMock(stop_reason="end_turn")
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.__iter__.return_value = iter([])
    stream.get_final_message.return_value = final
    client = MagicMock()
    client.messages.stream.return_value = stream

    with patch.object(agent, "get_client", return_value=client), \
         patch("chat.motor_router.get_motor_ativo", return_value="claude"):
        eventos = list(agent.chat_stream("What did the city buy?", [], idioma="en"))

    assert eventos[0] == {"tipo": "status", "msg": msg("status_analisando", "en")}
    system = client.messages.stream.call_args.kwargs["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "English" in system[1]["text"]
    assert "cache_control" not in system[1]
