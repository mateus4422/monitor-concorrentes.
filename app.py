import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime
import backend as bk 

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Monitor Corp V26", page_icon="🏢", layout="wide")

# --- CSS PROFISSIONAL ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    
    /* TUTORIAL STEPS */
    .tutorial-step {
        display: flex; align-items: flex-start; margin-bottom: 20px;
        background: rgba(255,255,255,0.02); padding: 20px; border-radius: 12px;
        border-left: 5px solid #2962FF; transition: all 0.3s ease;
    }
    .tutorial-step:hover { background: rgba(255,255,255,0.04); transform: translateX(5px); }
    .step-number {
        background-color: #2962FF; color: white; width: 40px; height: 40px;
        border-radius: 50%; text-align: center; line-height: 40px; font-weight: bold; font-size: 18px; margin-right: 20px; flex-shrink: 0;
    }
    
    /* KPI BOXES */
    .kpi-box { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 20px; text-align: center; }
    .kpi-val { font-size: 2.2rem; font-weight: 800; color: #fff; }
    .kpi-lbl { font-size: 0.9rem; text-transform: uppercase; color: #888; }

    /* BOTÕES */
    div.stButton > button { width: 100%; border-radius: 8px; height: 50px; font-weight: 600; }
    div.stButton > button[kind="primary"] { background-color: #2962FF; color: white; border: none; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO ---
if "db_empresas" not in st.session_state: st.session_state.db_empresas = bk.carregar_dados(bk.DB_EMPRESAS)
if "db_historico" not in st.session_state: st.session_state.db_historico = bk.carregar_dados(bk.DB_HISTORICO)
if "dados_analise" not in st.session_state: st.session_state.dados_analise = None

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055646.png", width=60)
    st.title("Monitor Corp")
    st.markdown("---")
    menu = st.radio("Menu Principal", ["🏠 Início", "📊 Painel de Análise", "🏢 Minha Empresa", "🔎 Concorrentes", "📂 Histórico"], label_visibility="collapsed")
    st.markdown("---")
    empresa_ativa = st.session_state.db_empresas.get("minha_empresa")
    if empresa_ativa: st.success(f"Ativo: **{empresa_ativa['title']}**")
    else: st.warning("⚠️ Empresa não configurada")

# --- FUNÇÃO GRÁFICA ---
def render_grafico_comparativo(df_a, df_b):
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_a.index], x=stars_a.values, name="Você", orientation='h', marker_color='#2962FF', text=stars_a.values, textposition='auto'))
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_b.index], x=stars_b.values, name="Rival", orientation='h', marker_color='#546E7A', text=stars_b.values, textposition='auto'))
    fig.update_layout(title="Volume de Avaliações", barmode='group', height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#888'), margin=dict(l=20,r=20,t=40,b=20))
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 1. HOME (TUTORIAL)
# ==========================================
if menu == "🏠 Início":
    st.title("Bem-vindo ao Monitor Corporativo")
    st.markdown("---")
    st.subheader("📘 Guia Passo a Passo")
    st.markdown("""
    <div class="tutorial-step"><div class="step-number">1</div><div class="step-content"><h4>Configure sua Empresa</h4><p>Acesse o menu lateral <b>"Minha Empresa"</b> e defina seu negócio principal.</p></div></div>
    <div class="tutorial-step"><div class="step-number">2</div><div class="step-content"><h4>Cadastre Concorrentes</h4><p>Vá até <b>"Concorrentes"</b> e adicione as empresas rivais.</p></div></div>
    <div class="tutorial-step"><div class="step-number">3</div><div class="step-content"><h4>Gere Inteligência</h4><p>No <b>"Painel de Análise"</b>, selecione o período e processe os dados com IA.</p></div></div>
    """, unsafe_allow_html=True
