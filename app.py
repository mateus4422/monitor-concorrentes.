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
    MY_APIFY_TOKEN = "apify_api_yRzwwIYgcwqLjvf2aL0yWnyjss54F00ym2nK"
    MY_GEMINI_KEY = "AIzaSyBqEgzqsdvo-zMcVwjMLxM3H7ZAZJ4LosM"

st.set_page_config(page_title="Monitor Visual V16", page_icon="📊", layout="wide")

# --- CSS (Visual Limpo) ---
st.markdown("""
<style>
    .big-font { font-size: 20px !important; font-weight: bold; }
    .vs-container { text-align: center; font-size: 40px; font-weight: 900; color: #FF4B4B; padding-top: 50px; }
    div[data-testid="stMetricValue"] { font-size: 32px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE LOCAL ---
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

# --- GRÁFICOS SIMPLIFICADOS (PARA LEIGOS) ---
def criar_gauge(valor, titulo, cor):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': titulo},
        gauge = {
            'axis': {'range': [0, 5], 'tickwidth': 1},
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
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
    return fig

def criar_rosca_aprovacao(df, cor_principal):
    # Simplifica: 4 e 5 são bons (Aprovação), resto é ruim/neutro
    df['tipo'] = df['stars'].apply(lambda x: 'Aprovação' if x >= 4 else 'Outros')
    contagem = df['tipo'].value_counts()
    
    aprovados = contagem.get('Aprovação', 0)
    total = len(df)
    perc = (aprovados / total * 100) if total > 0 else 0
    
    fig = go.Figure(go.Pie(
        values=[aprovados, total - aprovados],
        labels=['Aprovação', 'Outros'],
        hole=.7,
        marker_colors=[cor_principal, '#eeeeee'],
        textinfo='none'
    ))
    
    fig.update_layout(
        showlegend=False,
        height=180,
        margin=dict(l=0, r=0, t=0, b=0),
        annotations=[dict(text=f"{int(perc)}%", x=0.5, y=0.5, font_size=28, showarrow=False, font_weight='bold')]
    )
    return fig

def criar_barras_sentimento(df_a, df_b, nome_a, nome_b):
    # Agrupa em: Positivo (4-5), Neutro (3), Negativo (1-2)
    def classificar(s):
        if s >= 4: return "Positivo (4-5★)"
        if s == 3: return "Neutro (3★)"
        return "Negativo (1-2★)"
    
    df_a['sentimento'] = df_a['stars'].apply(classificar)
    df_b['sentimento'] = df_b['stars'].apply(classificar)
    
    # Conta
    cont_a = df_a['sentimento'].value_counts().reindex(["Positivo (4-5★)", "Neutro (3★)", "Negativo (1-2★)"], fill_value=0)
    cont_b = df_b['sentimento'].value_counts().reindex(["Positivo (4-5★)", "Neutro (3★)", "Negativo (1-2★)"], fill_value=0)
    
    fig = go.Figure()
    
    # Barras lado a lado
    fig.add_trace(go.Bar(
        y=cont_a.index, x=cont_a.values, name="Você", orientation='h', 
        marker_color='#4A90E2', text=cont_a.values, textposition='auto'
    ))
    fig.add_trace(go.Bar(
        y=cont_b.index, x=cont_b.values, name="Rival", orientation='h', 
        marker_color='#E24A4A', text=cont_b.values, textposition='auto'
    ))
    
    fig.update_layout(
        title="Raio-X do Sentimento (Quem reclama mais?)",
        barmode='group',
        height=300,
        xaxis_title="Quantidade de Clientes",
        yaxis=dict(autorange="reversed") # Positivo em cima
    )
    return fig

# --- TRATAMENTO DATA ---
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
    # Prompt otimizado para ser curto e visual
    prompt = f"""
    Comparativo Rápido: {nome_a} vs {nome_b}. Foco: {criterio}.
    REVIEWS A: {texto_a[:3500]}
    REVIEWS B: {texto_b[:3500]}
    
    Responda em Markdown visual:
    ### 🏆 Veredito
    (Quem ganha e porquê, em 1 frase)

    ### 💎 O que {nome_a} tem de BOM
    * (Item 1)
    * (Item 2)

    ### ⚠️ O que {nome_a} tem de RUIM
    * (Item 1)
    * (Item 2)

    ### 💎 O que {nome_b} tem de BOM
    * (Item 1)
    * (Item 2)

    ### ⚠️ O que {nome_b} tem de RUIM
    * (Item 1)
    * (Item 2)
    
    ---
    ### 💡 Dica do Consultor
    (Sugestão prática de 1 parágrafo)
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
    st.title("📊 Monitor V16")
    st.caption("Focado no Dono do Negócio")
    menu = st.radio("Menu", ["🏠 Minha Empresa", "🥊 Meus Concorrentes", "⚡ Dashboard Visual", "📂 Histórico"])

# ... (CADASTROS IGUAIS V15) ...

if menu == "🏠 Minha Empresa":
    st.header("🏠 Configurar Minha Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        st.success(f"Atual: **{dados['title']}**")
        if st.button("🗑️ Remover"):
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
            opts = {f"{x['title']} ({x.get('address','')})": x for x in st.session_state.busca_minha}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.button("Salvar"):
                st.session_state.db_empresas["minha_empresa"] = opts[esc]
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

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
        opts = {f"{x['title']} ({x.get('address','')})": x for x in st.session_state.busca_rival}
        esc = st.radio("Selecione:", list(opts.keys()), key='rr')
        if st.button("Salvar Rival"):
            if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
            st.session_state.db_empresas["concorrentes"].append(opts[esc])
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()

# ---------------------------------------------------------
# 3. DASHBOARD VISUAL (SIMPLIFICADO)
# ---------------------------------------------------------
elif menu == "⚡ Dashboard Visual":
    st.title("⚡ Comparativo Fácil")
    
    with st.expander("⚙️ Filtros (Datas e Quantidade)", expanded=True):
        c1, c2, c3 = st.columns(3)
        dt_ini = c1.date_input("De:", date.today().replace(day=1))
        dt_fim = c2.date_input("Até:", date.today())
        qtd_limite = c3.slider("Quantidade de Reviews", 10, 100, 30)
        
        c_sel_a, c_sel_b = st.columns(2)
        opts_a = []
        if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
        for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🥊 {c['title']}")
        
        sel_a = c_sel_a.selectbox("Você", opts_a)
        sel_b = c_sel_b.selectbox("Rival", [x for x in opts_a if x != sel_a])

    def get_obj(txt):
        if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
        nome = txt.replace("🥊 ", "")
        for c in st.session_state.db_empresas.get("concorrentes", []):
            if c['title'] == nome: return c
        return None

    if st.button("🚀 COMPARAR AGORA", type="primary", use_container_width=True):
        obj_a = get_obj(sel_a)
        obj_b = get_obj(sel_b)
        
        if obj_a and obj_b:
            with st.spinner("Calculando notas e sentimentos..."):
                raw_a = baixar_reviews_apify(obj_a['url'], 150)
                raw_b = baixar_reviews_apify(obj_b['url'], 150)
                
                if raw_a and raw_b:
                    df_a = pd.DataFrame(raw_a.get('reviews', []))
                    df_b = pd.DataFrame(raw_b.get('reviews', []))
                    
                    # Trata Datas
                    for df in [df_a, df_b]:
                        if not df.empty and 'publishAt' in df.columns:
                            df['data_obj'] = df['publishAt'].apply(tratar_data_google)
                            df.dropna(subset=['data_obj'], inplace=True)
                            df['data'] = df['data_obj'].dt.date
                    
                    # Filtra Data
                    df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)]
                    df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)]
                    
                    if df_a.empty or df_b.empty:
                        st.warning("Sem reviews neste período.")
                    else:
                        df_a['stars'] = pd.to_numeric(df_a['stars'])
                        df_b['stars'] = pd.to_numeric(df_b['stars'])
                        
                        # Limita qtd
                        df_a = df_a.head(qtd_limite)
                        df_b = df_b.head(qtd_limite)
                        
                        # IA
                        txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                        txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                        analise = analisar_ia(txt_a, txt_b, obj_a['title'], obj_b['title'], "Geral")
                        
                        # Salva
                        relatorio = {
                            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                            "data_geracao": datetime.now().strftime("%d/%m %H:%M"),
                            "periodo": f"{dt_ini.strftime('%d/%m')} - {dt_fim.strftime('%d/%m')}",
                            "empresa_a": obj_a['title'],
                            "empresa_b": obj_b['title'],
                            "nota_a_corte": float(df_a['stars'].mean()),
                            "nota_b_corte": float(df_b['stars'].mean()),
                            "analise_ia": analise
                        }
                        st.session_state.db_historico.insert(0, relatorio)
                        salvar_json(DB_HISTORICO, st.session_state.db_historico)
                        
                        # === DASHBOARD V16 ===
                        st.divider()
                        
                        # 1. NOTA GERAL (GAUGE)
                        c_g1, c_vs, c_g2 = st.columns([1, 0.5, 1])
                        with c_g1:
                            st.markdown(f"<h3 style='text-align: center; color: #4A90E2'>{obj_a['title']}</h3>", unsafe_allow_html=True)
                            st.plotly_chart(criar_gauge(df_a['stars'].mean(), "Sua Nota", "#4A90E2"), use_container_width=True)
                        with c_vs:
                             st.markdown("<div class='vs-container'>VS</div>", unsafe_allow_html=True)
                        with c_g2:
                            st.markdown(f"<h3 style='text-align: center; color: #E24A4A'>{obj_b['title']}</h3>", unsafe_allow_html=True)
                            st.plotly_chart(criar_gauge(df_b['stars'].mean(), "Nota Rival", "#E24A4A"), use_container_width=True)

                        # 2. APROVAÇÃO (DONUT)
                        st.subheader("🥰 Taxa de Aprovação (Quem tem mais fãs?)")
                        col_don1, col_don2 = st.columns(2)
                        with col_don1:
                            st.markdown("**Você**")
                            st.plotly_chart(criar_rosca_aprovacao(df_a, '#4A90E2'), use_container_width=True)
                        with col_don2:
                            st.markdown("**Rival**")
                            st.plotly_chart(criar_rosca_aprovacao(df_b, '#E24A4A'), use_container_width=True)

                        # 3. SENTIMENTO (BARRAS HORIZONTAIS)
                        st.plotly_chart(criar_barras_sentimento(df_a, df_b, "Você", "Rival"), use_container_width=True)
                        
                        # 4. PLACAR DE PROBLEMAS (NÚMEROS GRANDES)
                        recl_a = len(df_a[df_a['stars'] <= 2])
                        recl_b = len(df_b[df_b['stars'] <= 2])
                        
                        st.subheader("🤬 Placar de Reclamações (Menos é melhor)")
                        kp1, kp2 = st.columns(2)
                        
                        # Lógica da cor: Se eu tenho MENOS reclamações que o rival, fico Verde (bom), senão Vermelho
                        cor_a = "green" if recl_a < recl_b else "red"
                        kp1.markdown(f"""
                            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid {cor_a}">
                                <h2 style="margin:0; color: {cor_a}">{recl_a}</h2>
                                <p>Suas Reclamações</p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        kp2.markdown(f"""
                            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
                                <h2 style="margin:0; color: #333">{recl_b}</h2>
                                <p>Reclamações Rival</p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # 5. RESUMO IA
                        st.divider()
                        st.subheader("🤖 Consultor Virtual")
                        st.markdown(analise.split("---")[0])
                        
                        with st.expander("Ver detalhes"):
                             st.write("Dados brutos...")
                             st.dataframe(df_a)

# ---------------------------------------------------------
# 4. HISTÓRICO
# ---------------------------------------------------------
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
            st.metric("Nota Rival", f"{rel['nota_b_corte']:.2f}")
            st.markdown(rel['analise_ia'])
            if st.button("🗑️ Excluir"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
