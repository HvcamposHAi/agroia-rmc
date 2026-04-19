#!/usr/bin/env python3
"""
Interface Streamlit para o agente AgroIA-RMC.
Oferece chat, dashboard de dados e histórico de conversas.
"""

import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Configuração
st.set_page_config(
    page_title="AgroIA-RMC Chat",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos
st.markdown("""
<style>
    .chat-message-user {
        background-color: #e3f2fd;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        margin-left: 20%;
        text-align: right;
    }
    .chat-message-assistant {
        background-color: #f5f5f5;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        margin-right: 20%;
    }
</style>
""", unsafe_allow_html=True)

API_URL = "http://localhost:8000"

def carregar_dados_dashboard():
    """Carrega dados para o dashboard."""
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    # Top culturas
    items = sb.from_("vw_itens_agro").select(
        "cultura, valor_total"
    ).execute().data or []

    culturas = {}
    for item in items:
        cult = item.get("cultura", "")
        val = float(item.get("valor_total", 0))
        if cult not in culturas:
            culturas[cult] = 0
        culturas[cult] += val

    top_culturas = sorted(culturas.items(), key=lambda x: x[1], reverse=True)[:10]

    # Demanda por ano
    itens_ano = sb.from_("vw_itens_agro").select(
        "dt_abertura, valor_total"
    ).execute().data or []

    anos = {}
    for item in itens_ano:
        data = item.get("dt_abertura", "")
        ano = int(data[:4]) if data else 0
        val = float(item.get("valor_total", 0))
        if ano not in anos:
            anos[ano] = 0
        anos[ano] += val

    return {
        "culturas": top_culturas,
        "anos": sorted(anos.items())
    }

def main():
    # Sidebar
    with st.sidebar:
        st.title("🌾 AgroIA-RMC")
        st.markdown("**Assistente de Licitações Agrícolas**")

        page = st.radio(
            "Navegação:",
            ["💬 Chat", "📊 Dashboard", "📋 Conversas"],
            label_visibility="collapsed"
        )

        st.markdown("---")
        session_id = st.text_input(
            "ID da Sessão:",
            value=st.session_state.get("session_id", ""),
            help="Deixe em branco para nova sessão"
        )
        if session_id:
            st.session_state["session_id"] = session_id

        st.markdown("---")
        st.markdown(
            "**Base de dados:** Supabase\n"
            "**Escopo:** vw_itens_agro (743 itens agrícolas)"
        )

    # PÁGINA 1: CHAT
    if page == "💬 Chat":
        st.title("💬 Chat com AgroIA")

        # Histórico
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Exibir histórico
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("tools"):
                    st.caption(f"🔧 Tools: {', '.join(msg['tools'])}")

        # Input
        if prompt := st.chat_input("Faça uma pergunta sobre as licitações..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    try:
                        response = requests.post(
                            f"{API_URL}/chat",
                            json={
                                "pergunta": prompt,
                                "historico": st.session_state.messages[:-1],
                                "session_id": st.session_state.get("session_id", "")
                            },
                            timeout=60
                        )
                        resultado = response.json()

                        st.markdown(resultado["resposta"])
                        st.caption(f"🔧 Tools usadas: {', '.join(resultado['tools_usadas'])}")

                        if "session_id" in resultado:
                            st.session_state["session_id"] = resultado["session_id"]

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": resultado["resposta"],
                            "tools": resultado["tools_usadas"]
                        })

                    except Exception as e:
                        st.error(f"Erro na API: {e}")

    # PÁGINA 2: DASHBOARD
    elif page == "📊 Dashboard":
        st.title("📊 Dashboard de Dados")

        try:
            dados = carregar_dados_dashboard()

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Top-10 Culturas por Valor")
                culturas_df = {
                    "Cultura": [c[0] for c in dados["culturas"]],
                    "Valor (R$)": [c[1] for c in dados["culturas"]]
                }
                fig = px.bar(
                    culturas_df,
                    x="Cultura",
                    y="Valor (R$)",
                    title="Demanda por Cultura"
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("Demanda por Ano")
                anos_df = {
                    "Ano": [str(a[0]) for a in dados["anos"]],
                    "Valor (R$)": [a[1] for a in dados["anos"]]
                }
                fig = px.line(
                    anos_df,
                    x="Ano",
                    y="Valor (R$)",
                    title="Evolução Temporal",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            total_valor = sum(c[1] for c in dados["culturas"])
            st.metric("Valor Total em Dados", f"R$ {total_valor:,.2f}")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    # PÁGINA 3: CONVERSAS
    elif page == "📋 Conversas":
        st.title("📋 Histórico de Conversas")

        if not st.session_state.get("session_id"):
            st.warning("Nenhuma sessão ativa. Inicie uma conversa no Chat.")
        else:
            try:
                response = requests.get(
                    f"{API_URL}/conversas/{st.session_state['session_id']}",
                    timeout=10
                )
                conversa = response.json()

                if not conversa:
                    st.info("Nenhuma mensagem nesta sessão ainda.")
                else:
                    st.subheader(f"Sessão: {st.session_state['session_id']}")

                    for msg in conversa:
                        with st.chat_message(msg.get("role", "user")):
                            st.markdown(msg.get("content", ""))

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Limpar Histórico"):
                            requests.delete(
                                f"{API_URL}/conversas/{st.session_state['session_id']}"
                            )
                            st.success("Histórico deletado!")
                            st.rerun()

            except Exception as e:
                st.error(f"Erro ao carregar conversas: {e}")

    # Footer
    st.markdown("---")
    st.caption(f"AgroIA-RMC v1.0 | Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
