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
    # Coloque suas chaves aqui para teste local
    MY_APIFY_TOKEN = ""
    MY_GEMINI_KEY = ""

st.set_page_config(page_title="Monitor V17", page_icon="📱", layout="wide")

# --- CSS RESPONSIVO ---
st.markdown("""
<style>
    /* Ajustes para Mobile */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    
    /* Container VS */
    .vs-container { 
        text-align: center; 
        font-size: 2rem; 
        font-weight: 900; 
        color: #FF4B4B; 
        margin-top: 20px;
        margin-bottom: 20px;
    }
    
    /* Botões grandes para dedo (touch) */
    div.stButton > button:first-child {
        height: 3em;
        font-weight: bold;
    }
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
# Estado para controlar a navegação Dashboard <-> Relatório
if "modo_visualizacao" not in st.session_state: st.session_state.modo_visualizacao = "dashboard"
if "dados_analise_atual" not in st.session_state: st.session_state.dados_analise_atual = None

# --- GRÁFICOS RESPONSIVOS ---
def criar_gauge(valor, titulo, cor):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor,
        title = {'text': titulo, 'font': {'size': 16}},
        gauge = {
            'axis': {'range': [0, 5]},
            'bar': {'color': cor},
            'bgcolor': "white",
            'borderwidth': 1,
            'bordercolor': "#eee",
            'steps': [
                {'range': [0, 3], 'color': '#fff5f5'},
                {'range': [3, 4], 'color': '#fffdf5'},
                {'range': [4, 5], 'color': '#f0fff4'}],
        }
    ))
    # Margens menores para caber no celular
    fig.update_layout(height=180, margin=dict(l=10, r=10, t=30, b=10))
    return fig

def criar_barras_mobile(df_a, df_b, nome_a, nome_b):
    # Agrupa sentimentos
    def classificar(s):
        if s >= 4: return "Positivo"
        if s == 3: return "Neutro"
        return "Negativo"
    
    df_a['tipo'] = df_a['stars'].apply(classificar)
    df_b['tipo'] = df_b['stars'].apply(classificar)
    
    # Cria dataframe agrupado para o Plotly
    cont_a = df_a['tipo'].value_counts().reset_index()
    cont_a['Empresa'] = nome_a
    
    cont_b = df_b['tipo'].value_counts().reset_index()
    cont_b['Empresa'] = nome_b
    
    full = pd.concat([cont_a, cont_b])
    
    fig = px.bar(full, x='tipo', y='count', color='Empresa', barmode='group',
                 color_discrete_map={nome_a: '#4A90E2', nome_b: '#E24A4A'},
                 category_orders={"tipo": ["Positivo", "Neutro", "Negativo"]})
    
    fig.update_layout(
        title="Comparativo de Sentimento",
        xaxis_title=None,
        yaxis_title="Qtd",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=300,
        margin=dict(l=10, r=10, t=50, b=10)
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

def analisar_ia(texto_a, texto_b, nome_a, nome_b, criterio):
    prompt = f"""
    Comparativo: {nome_a} vs {nome_b}. Foco: {criterio}.
    REVIEWS A: {texto_a[:3500]}
    REVIEWS B: {texto_b[:3500]}
    
    Gere um relatório Executivo DETALHADO em Markdown:

    # ⚔️ Relatório de Batalha

    ### 🏆 Veredito
    (Parágrafo curto e direto sobre quem venceu)

    ---
    ### 🛡️ Análise de {nome_a}
    **Pontos Fortes:**
    * (Item)
    * (Item)
    
    **Pontos Fracos:**
    * (Item)
    * (Item)

    ---
    ### 🥊 Análise de {nome_b} (Concorrente)
    **Onde ele ganha:**
    * (Item)
    
    **Onde ele perde:**
    * (Item)
    
    ---
    ### 🚀 Plano de Ação (Consultoria)
    (3 passos práticos para {nome_a} superar o concorrente amanhã)
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
# INTERFACE
# ==========================================
with st.sidebar:
    st.title("📱 Monitor V17")
    st.caption("Mobile Ready")
    menu = st.radio("Menu", ["🏠 Minha Empresa", "🥊 Meus Concorrentes", "⚡ Dashboard", "📂 Histórico"])

# CADASTRO MINHA EMPRESA
if menu == "🏠 Minha Empresa":
    st.header("🏠 Minha Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        st.success(f"**{dados['title']}**")
        st.caption(f"{dados.get('address', '')}")
        if st.button("Trocar Empresa"):
            del st.session_state.db_empresas["minha_empresa"]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    else:
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", get_ibge("estados"), index=25)
        city = c1.selectbox("Cidade", get_ibge("cidades", uf))
        nome = c2.text_input("Nome")
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

# CADASTRO RIVAL
elif menu == "🥊 Meus Concorrentes":
    st.header("🥊 Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    if conc:
        st.dataframe(pd.DataFrame(conc)[['title', 'address']], use_container_width=True)
        to_del = st.selectbox("Excluir:", [c['title'] for c in conc], index=None)
        if to_del and st.button("Confirmar Exclusão"):
            st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != to_del]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    st.markdown("---")
    st.subheader("Adicionar Novo")
    c1, c2 = st.columns(2)
    uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
    city = c1.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
    nome = c2.text_input("Nome Rival")
    if st.button("Buscar Rival"):
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

# --- ÁREA PRINCIPAL: DASHBOARD & RELATÓRIO ---
elif menu == "⚡ Dashboard":
    
    # 1. TELA DE CONFIGURAÇÃO (Sempre visível se não tiver dados)
    if st.session_state.modo_visualizacao == "dashboard" and st.session_state.dados_analise_atual is None:
        st.title("⚡ Nova Análise")
        
        c1, c2 = st.columns(2)
        dt_ini = c1.date_input("De:", date.today().replace(day=1))
        dt_fim = c2.date_input("Até:", date.today())
        qtd_limite = st.slider("Qtd Reviews", 10, 100, 30)
        
        opts_a = []
        if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
        for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🥊 {c['title']}")
        
        col_sel1, col_sel2 = st.columns(2)
        sel_a = col_sel1.selectbox("Você", opts_a)
        sel_b = col_sel2.selectbox("Rival", [x for x in opts_a if x != sel_a])

        def get_obj(txt):
            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
            nome = txt.replace("🥊 ", "")
            for c in st.session_state.db_empresas.get("concorrentes", []):
                if c['title'] == nome: return c
            return None

        if st.button("🚀 GERAR RELATÓRIO", type="primary", use_container_width=True):
            obj_a = get_obj(sel_a)
            obj_b = get_obj(sel_b)
            
            if obj_a and obj_b:
                with st.spinner("Conectando satélites... (Isso leva uns segundos)"):
                    raw_a = baixar_reviews_apify(obj_a['url'], 150)
                    raw_b = baixar_reviews_apify(obj_b['url'], 150)
                    
                    if raw_a and raw_b:
                        df_a = pd.DataFrame(raw_a.get('reviews', []))
                        df_b = pd.DataFrame(raw_b.get('reviews', []))
                        
                        # Processamento
                        for df in [df_a, df_b]:
                            if not df.empty and 'publishAt' in df.columns:
                                df['data_obj'] = df['publishAt'].apply(tratar_data_google)
                                df.dropna(subset=['data_obj'], inplace=True)
                                df['data'] = df['data_obj'].dt.date
                                df['stars'] = pd.to_numeric(df['stars'])
                        
                        # Filtros
                        df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)].head(qtd_limite)
                        df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)].head(qtd_limite)
                        
                        if not df_a.empty and not df_b.empty:
                            # IA
                            txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                            txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                            analise = analisar_ia(txt_a, txt_b, obj_a['title'], obj_b['title'], "Geral")
                            
                            # SALVAR NO ESTADO (PARA NÃO PERDER)
                            st.session_state.dados_analise_atual = {
                                "df_a": df_a, "df_b": df_b,
                                "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                "analise": analise, "periodo": f"{dt_ini.strftime('%d/%m')} - {dt_fim.strftime('%d/%m')}"
                            }
                            
                            # Salva histórico
                            relatorio = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                                "data_geracao": datetime.now().strftime("%d/%m %H:%M"),
                                "empresa_a": obj_a['title'], "empresa_b": obj_b['title'],
                                "nota_a_corte": float(df_a['stars'].mean()),
                                "nota_b_corte": float(df_b['stars'].mean()),
                                "analise_ia": analise
                            }
                            st.session_state.db_historico.insert(0, relatorio)
                            salvar_json(DB_HISTORICO, st.session_state.db_historico)
                            
                            st.rerun() # Recarrega para mostrar o dashboard
                        else:
                            st.warning("Sem dados suficientes no período.")

    # 2. TELA DE DASHBOARD VISUAL
    elif st.session_state.modo_visualizacao == "dashboard" and st.session_state.dados_analise_atual:
        dados = st.session_state.dados_analise_atual
        
        # Botão Voltar para Nova Análise
        if st.button("⬅️ Nova Pesquisa"):
            st.session_state.dados_analise_atual = None
            st.rerun()
            
        st.divider()
        
        # GAUGES (Lado a Lado no Desktop, Empilhado no Mobile se ficar pequeno)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(criar_gauge(dados['df_a']['stars'].mean(), f"Você: {dados['nome_a'][:15]}...", "#4A90E2"), use_container_width=True)
        with c2:
            st.plotly_chart(criar_gauge(dados['df_b']['stars'].mean(), f"Rival: {dados['nome_b'][:15]}...", "#E24A4A"), use_container_width=True)
            
        # PLACAR GAP
        gap = dados['df_a']['stars'].mean() - dados['df_b']['stars'].mean()
        cor_gap = "green" if gap > 0 else "red"
        st.markdown(f"<h3 style='text-align: center; color: {cor_gap}'>Diferença: {gap:+.1f} pontos</h3>", unsafe_allow_html=True)
        
        # GRÁFICO BARRAS RESPONSIVO
        st.plotly_chart(criar_barras_mobile(dados['df_a'], dados['df_b'], "Você", "Rival"), use_container_width=True)
        
        st.info("💡 Dica: Clique no botão abaixo para ler o que a IA descobriu.")
        
        # --- BOTÃO PARA IR PARA O RELATÓRIO COMPLETO ---
        if st.button("📄 VER RELATÓRIO COMPLETO DETALHADO", type="primary", use_container_width=True):
            st.session_state.modo_visualizacao = "relatorio"
            st.rerun()

    # 3. TELA DE RELATÓRIO DETALHADO (TEXTO)
    elif st.session_state.modo_visualizacao == "relatorio" and st.session_state.dados_analise_atual:
        dados = st.session_state.dados_analise_atual
        
        if st.button("⬅️ Voltar para Gráficos", use_container_width=True):
            st.session_state.modo_visualizacao = "dashboard"
            st.rerun()
            
        st.markdown("---")
        st.header("📑 Dossiê Completo")
        st.caption(f"Período: {dados['periodo']}")
        
        # Exibe o texto da IA formatado
        with st.container(border=True):
            st.markdown(dados['analise'])
        
        st.subheader("🔎 Dados Brutos")
        t1, t2 = st.tabs(["Seus Reviews", "Reviews Rival"])
        with t1: st.dataframe(dados['df_a'][['stars', 'text', 'data']], use_container_width=True)
        with t2: st.dataframe(dados['df_b'][['stars', 'text', 'data']], use_container_width=True)


# --- HISTÓRICO ---
elif menu == "📂 Histórico":
    st.header("📂 Arquivo")
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
