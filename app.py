import streamlit as st
import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
import google.generativeai as genai
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 🔐 SUAS CHAVES
# ==========================================
try:
    MY_APIFY_TOKEN = st.secrets["MY_APIFY_TOKEN"]
    MY_GEMINI_KEY = st.secrets["MY_GEMINI_KEY"]
except:
    MY_APIFY_TOKEN = ""
    MY_GEMINI_KEY = ""

st.set_page_config(page_title="Monitor V19", page_icon="🔢", layout="wide", initial_sidebar_state="collapsed")

# --- CSS (VISUAL LIMPO E NÚMEROS GRANDES) ---
st.markdown("""
<style>
    /* Estilo dos Botões do Menu */
    .stButton > button {
        width: 100%; height: 70px; font-size: 18px; font-weight: 600; border-radius: 12px; margin-bottom: 8px;
    }
    .btn-voltar > button { height: 40px !important; background: #f0f2f6; color: #333; border: none; }

    /* PLACAR (SCOREBOARD) */
    .score-container {
        display: flex; justify-content: space-around; align-items: center;
        background-color: #ffffff; padding: 20px; border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    .score-box { text-align: center; width: 45%; }
    .score-val { font-size: 3.5rem; font-weight: 800; line-height: 1; }
    .score-lbl { font-size: 1rem; color: #666; font-weight: 600; margin-top: 5px; }
    
    .vs-text { font-size: 1.5rem; font-weight: 900; color: #ccc; }
    
    /* Cores */
    .blue-text { color: #2962FF; }
    .red-text { color: #D50000; }
    .green-bg { background-color: #E8F5E9; color: #2E7D32; padding: 5px 10px; border-radius: 5px; font-weight: bold; }
    .red-bg { background-color: #FFEBEE; color: #C62828; padding: 5px 10px; border-radius: 5px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"

def carregar_json(arquivo):
    if not os.path.exists(arquivo): return {} if arquivo == DB_EMPRESAS else []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {} if arquivo == DB_EMPRESAS else []

def salvar_json(arquivo, dados):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False, default=str)

if "db_empresas" not in st.session_state: st.session_state.db_empresas = carregar_json(DB_EMPRESAS)
if "db_historico" not in st.session_state: st.session_state.db_historico = carregar_json(DB_HISTORICO)

# NAVEGAÇÃO
if "tela_atual" not in st.session_state: st.session_state.tela_atual = "menu_principal"
if "dados_analise_atual" not in st.session_state: st.session_state.dados_analise_atual = None

def navegar_para(tela):
    st.session_state.tela_atual = tela
    st.rerun()

# --- ÚNICO GRÁFICO (ESTRELAS) ---
def criar_grafico_estrelas_horizontal(df_a, df_b, nome_a, nome_b):
    # Prepara contagem 1 a 5
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    
    fig = go.Figure()
    
    # Você (Azul)
    fig.add_trace(go.Bar(
        y=[f"{i} ⭐" for i in stars_a.index], 
        x=stars_a.values, 
        name="Você", 
        orientation='h',
        marker_color='#2962FF',
        text=stars_a.values,
        textposition='auto'
    ))
    
    # Rival (Vermelho)
    fig.add_trace(go.Bar(
        y=[f"{i} ⭐" for i in stars_b.index], 
        x=stars_b.values, 
        name="Rival", 
        orientation='h',
        marker_color='#D50000',
        text=stars_b.values,
        textposition='auto'
    ))

    fig.update_layout(
        title="Comparativo de Estrelas",
        barmode='group',
        height=300,
        margin=dict(l=50, r=20, t=40, b=20),
        xaxis=dict(showgrid=False, showticklabels=False), # Remove grade fundo
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- TRATAMENTO ---
def tratar_data_google(texto):
    if not isinstance(texto, str): return pd.NaT
    texto = texto.lower().strip()
    agora = datetime.now()
    if "atrás" in texto or "ago" in texto:
        try:
            val = 1 if "um" in texto or "uma" in texto else int(texto.split()[0])
            if "segundo" in texto: return agora - timedelta(seconds=val)
            if "minuto" in texto: return agora - timedelta(minutes=val)
            if "hora" in texto: return agora - timedelta(hours=val)
            if "dia" in texto: return agora - timedelta(days=val)
            if "semana" in texto: return agora - timedelta(weeks=val)
            if "mês" in texto or "mes" in texto: return agora - timedelta(days=val*30)
            if "ano" in texto: return agora - timedelta(days=val*365)
        except: pass
    try: return pd.to_datetime(texto)
    except: return pd.NaT

# --- API ---
def buscar_locais_apify(termo):
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [termo], "maxCrawledPlacesPerSearch": 5, "language": "pt-BR", "maxReviews": 0
        })
        return client.dataset(run['defaultDatasetId']).list_items().items
    except: return []

def baixar_reviews_apify(url, max_reviews=100, sort_order="newest"):
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "startUrls": [{"url": url}], "language": "pt-BR", "maxReviews": max_reviews, "reviewsSort": sort_order
        })
        items = client.dataset(run['defaultDatasetId']).list_items().items
        return items[0] if items else None
    except: return None

# --- IA ---
def configurar_gemini():
    if not MY_GEMINI_KEY: return None
    genai.configure(api_key=MY_GEMINI_KEY)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                return genai.GenerativeModel(m.name)
    except: pass
    return genai.GenerativeModel('gemini-pro')

model = configurar_gemini()

def analisar_ia(texto_a, texto_b, nome_a, nome_b):
    prompt = f"""
    Comparativo Rápido: {nome_a} vs {nome_b}.
    REVIEWS A: {texto_a[:3500]}
    REVIEWS B: {texto_b[:3500]}
    
    Responda em Markdown:
    ### 🏆 Veredito
    (1 frase sobre quem ganha)
    
    ### 💎 Pontos Fortes ({nome_a})
    * (Item)
    * (Item)
    
    ### ⚠️ Pontos Fracos ({nome_a})
    * (Item)
    * (Item)

    ### 🚀 Plano de Ação
    (Sugestão prática)
    """
    try:
        return model.generate_content(prompt).text
    except: return "Erro na IA."

# --- UTIL ---
@st.cache_data(ttl=3600)
def get_ibge(tipo, uf=None):
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
        if tipo == "cidades": url += f"/{uf}/municipios"
        r = requests.get(url)
        return sorted([x['sigla' if tipo=='estados' else 'nome'] for x in r.json()])
    except: return []

# ==========================================
# FLUXO DO APP
# ==========================================

# 1. MENU
if st.session_state.tela_atual == "menu_principal":
    st.title("Monitor Corp")
    st.markdown("Bem-vindo! Escolha uma opção:")
    
    if st.button("⚡ DASHBOARD (Analisar)"): navegar_para("dashboard")
    if st.button("🏠 MINHA EMPRESA"): navegar_para("minha_empresa")
    if st.button("🥊 MEUS CONCORRENTES"): navegar_para("concorrentes")
    if st.button("📂 HISTÓRICO"): navegar_para("historico")

# 2. TELAS DE CADASTRO (IGUAIS)
elif st.session_state.tela_atual == "minha_empresa":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Menu"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    st.header("🏠 Minha Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        st.success(f"**{dados['title']}**")
        if st.button("Trocar"):
            del st.session_state.db_empresas["minha_empresa"]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    else:
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", get_ibge("estados"), index=25)
        city = c1.selectbox("Cidade", get_ibge("cidades", uf))
        nome = st.text_input("Nome")
        if st.button("Buscar"):
            with st.spinner("Procurando..."):
                res = buscar_locais_apify(f"{nome}, {city} - {uf}")
                if res: st.session_state.busca_minha = res
        if "busca_minha" in st.session_state:
            opts = {f"{x['title']}": x for x in st.session_state.busca_minha}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.button("Salvar"):
                st.session_state.db_empresas["minha_empresa"] = opts[esc]
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

elif st.session_state.tela_atual == "concorrentes":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Menu"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    st.header("🥊 Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    if conc:
        st.dataframe(pd.DataFrame(conc)[['title', 'address']], use_container_width=True)
        to_del = st.selectbox("Excluir:", [c['title'] for c in conc], index=None)
        if to_del and st.button("Confirmar Exclusão"):
            st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != to_del]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    st.subheader("Novo Concorrente")
    c1, c2 = st.columns(2)
    uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
    city = c1.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
    nome = st.text_input("Nome Rival")
    if st.button("Buscar"):
        with st.spinner("Buscando..."):
            res = buscar_locais_apify(f"{nome}, {city} - {uf}")
            if res: st.session_state.busca_rival = res
    if "busca_rival" in st.session_state:
        opts = {f"{x['title']}": x for x in st.session_state.busca_rival}
        esc = st.radio("Selecione:", list(opts.keys()), key='rr')
        if st.button("Salvar Rival"):
            if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
            st.session_state.db_empresas["concorrentes"].append(opts[esc])
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()

# 3. DASHBOARD (ANÁLISE)
elif st.session_state.tela_atual == "dashboard":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)

    # FORMULÁRIO DE CONFIGURAÇÃO
    if st.session_state.dados_analise_atual is None:
        st.title("Nova Análise")
        
        c1, c2, c3 = st.columns(3)
        dt_ini = c1.date_input("Início", date.today().replace(day=1))
        dt_fim = c2.date_input("Fim", date.today())
        qtd_limite = c3.slider("Qtd Reviews", 10, 100, 30)
        
        opts_a = []
        if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
        for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🥊 {c['title']}")
        
        c_sel_a, c_sel_b = st.columns(2)
        sel_a = c_sel_a.selectbox("Você", opts_a)
        sel_b = c_sel_b.selectbox("Rival", [x for x in opts_a if x != sel_a])

        def get_obj(txt):
            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
            nome = txt.replace("🥊 ", "")
            for c in st.session_state.db_empresas.get("concorrentes", []):
                if c['title'] == nome: return c
            return None

        if st.button("🚀 GERAR PLACAR", type="primary"):
            obj_a = get_obj(sel_a)
            obj_b = get_obj(sel_b)
            
            if obj_a and obj_b:
                with st.spinner("Processando números..."):
                    raw_a = baixar_reviews_apify(obj_a['url'], 150)
                    raw_b = baixar_reviews_apify(obj_b['url'], 150)
                    
                    if raw_a and raw_b:
                        df_a = pd.DataFrame(raw_a.get('reviews', []))
                        df_b = pd.DataFrame(raw_b.get('reviews', []))
                        
                        for df in [df_a, df_b]:
                            if not df.empty and 'publishAt' in df.columns:
                                df['data_obj'] = df['publishAt'].apply(tratar_data_google)
                                df.dropna(subset=['data_obj'], inplace=True)
                                df['data'] = df['data_obj'].dt.date
                                df['stars'] = pd.to_numeric(df['stars'])
                        
                        df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)].head(qtd_limite)
                        df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)].head(qtd_limite)
                        
                        if not df_a.empty and not df_b.empty:
                            txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                            txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                            analise = analisar_ia(txt_a, txt_b, obj_a['title'], obj_b['title'])
                            
                            st.session_state.dados_analise_atual = {
                                "df_a": df_a, "df_b": df_b,
                                "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                "analise": analise, "periodo": f"{dt_ini.strftime('%d/%m')} - {dt_fim.strftime('%d/%m')}"
                            }
                            
                            rel = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                                "data_geracao": datetime.now().strftime("%d/%m %H:%M"),
                                "empresa_a": obj_a['title'], "empresa_b": obj_b['title'],
                                "nota_a_corte": float(df_a['stars'].mean()),
                                "nota_b_corte": float(df_b['stars'].mean()),
                                "analise_ia": analise
                            }
                            st.session_state.db_historico.insert(0, rel)
                            salvar_json(DB_HISTORICO, st.session_state.db_historico)
                            st.rerun()
                        else: st.warning("Sem dados.")

    # TELA DE RESULTADOS (CLEAN NUMBERS)
    else:
        dados = st.session_state.dados_analise_atual
        if st.button("🔄 Nova Análise"):
            st.session_state.dados_analise_atual = None
            st.rerun()
            
        # Cálculos
        nota_a = dados['df_a']['stars'].mean()
        nota_b = dados['df_b']['stars'].mean()
        gap = nota_a - nota_b
        
        # HTML SCOREBOARD (PLACAR)
        st.markdown(f"""
        <div class="score-container">
            <div class="score-box">
                <div class="score-lbl blue-text">VOCÊ</div>
                <div class="score-val blue-text">{nota_a:.1f}</div>
                <div class="score-lbl">{len(dados['df_a'])} reviews</div>
            </div>
            <div class="score-box" style="width: 10%;">
                <div class="vs-text">VS</div>
            </div>
            <div class="score-box">
                <div class="score-lbl red-text">RIVAL</div>
                <div class="score-val red-text">{nota_b:.1f}</div>
                <div class="score-lbl">{len(dados['df_b'])} reviews</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # GAP INDICATOR
        if gap > 0: st.success(f"🏆 Você está **{gap:+.1f} pontos** acima do concorrente!")
        elif gap < 0: st.error(f"🚨 Você está **{gap:+.1f} pontos** abaixo do concorrente!")
        else: st.info("🤝 Empate técnico.")

        # GRÁFICO ÚNICO (ESTRELAS)
        st.subheader("Distribuição de Notas")
        st.plotly_chart(criar_grafico_estrelas_horizontal(dados['df_a'], dados['df_b'], "Você", "Rival"), use_container_width=True)
        
        # NÚMEROS DE SENTIMENTO (CARDS SIMPLES)
        st.subheader("Raio-X")
        
        # Conta Elogios (5) e Problemas (1-2)
        elogios_a = len(dados['df_a'][dados['df_a']['stars'] == 5])
        probs_a = len(dados['df_a'][dados['df_a']['stars'] <= 2])
        
        elogios_b = len(dados['df_b'][dados['df_b']['stars'] == 5])
        probs_b = len(dados['df_b'][dados['df_b']['stars'] <= 2])
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Você:**")
            st.markdown(f"💎 **{elogios_a}** Elogios (5★)")
            st.markdown(f"🤬 **{probs_a}** Reclamações (1-2★)")
        with c2:
            st.markdown(f"**Rival:**")
            st.markdown(f"💎 **{elogios_b}** Elogios (5★)")
            st.markdown(f"🤬 **{probs_b}** Reclamações (1-2★)")
            
        st.markdown("---")
        if st.button("📄 VER DETALHES IA", type="primary"):
            navegar_para("relatorio_detalhado")

# 4. RELATÓRIO DETALHADO
elif st.session_state.tela_atual == "relatorio_detalhado" and st.session_state.dados_analise_atual:
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
    
    dados = st.session_state.dados_analise_atual
    st.header("Análise IA")
    with st.container(border=True):
        st.markdown(dados['analise'])
    
    t1, t2 = st.tabs(["Seus Reviews", "Reviews Rival"])
    with t1: st.dataframe(dados['df_a'][['stars', 'text', 'data']], use_container_width=True)
    with t2: st.dataframe(dados['df_b'][['stars', 'text', 'data']], use_container_width=True)

# 5. HISTÓRICO
elif st.session_state.tela_atual == "historico":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Menu"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("Histórico")
    if not st.session_state.db_historico: st.info("Vazio.")
    else:
        opcoes = [f"{r['data_geracao']} | {r['empresa_a']} vs {r['empresa_b']}" for r in st.session_state.db_historico]
        escolha = st.selectbox("Selecione:", opcoes)
        idx = opcoes.index(escolha)
        rel = st.session_state.db_historico[idx]
        
        with st.container(border=True):
            st.metric("Sua Nota", f"{rel['nota_a_corte']:.2f}")
            st.markdown(rel['analise_ia'])
            if st.button("🗑️ Excluir"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
