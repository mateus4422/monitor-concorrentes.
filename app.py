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
# 🔐 SUAS CHAVES (Mantenha seguro)
# ==========================================
try:
    MY_APIFY_TOKEN = st.secrets["MY_APIFY_TOKEN"]
    MY_GEMINI_KEY = st.secrets["MY_GEMINI_KEY"]
except:
    MY_APIFY_TOKEN = "apify_api_yRzwwIYgcwqLjvf2aL0yWnyjss54F00ym2nK"
    MY_GEMINI_KEY = "AIzaSyBqEgzqsdvo-zMcVwjMLxM3H7ZAZJ4LosM"

st.set_page_config(page_title="Monitor Visual V14", page_icon="📊", layout="wide")

# --- CSS CUSTOMIZADO (Para o visual 'Dashboard') ---
st.markdown("""
<style>
    .big-font { font-size: 20px !important; font-weight: bold; }
    .vs-container { text-align: center; font-size: 40px; font-weight: 900; color: #FF4B4B; padding-top: 50px; }
    div[data-testid="stMetricValue"] { font-size: 28px; }
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

# --- FUNÇÕES VISUAIS (PLOTLY) ---
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
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 3], 'color': '#ffcccc'},
                {'range': [3, 4], 'color': '#ffffcc'},
                {'range': [4, 5], 'color': '#ccffcc'}],
        }
    ))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10))
    return fig

def criar_grafico_comparativo(df_a, df_b, nome_a, nome_b):
    # Prepara dados de distribuição de estrelas
    stars_a = df_a['stars'].value_counts().sort_index()
    stars_b = df_b['stars'].value_counts().sort_index()
    
    # Garante que temos índices de 1 a 5
    for i in range(1, 6):
        if i not in stars_a: stars_a[i] = 0
        if i not in stars_b: stars_b[i] = 0
        
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stars_a.index, y=stars_a.values, name=nome_a, marker_color='#4A90E2'))
    fig.add_trace(go.Bar(x=stars_b.index, y=stars_b.values, name=nome_b, marker_color='#E24A4A'))
    
    fig.update_layout(
        title="Distribuição de Notas (Batalha de Estrelas)",
        barmode='group',
        xaxis_title="Estrelas",
        yaxis_title="Qtd Avaliações",
        height=300
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

def baixar_reviews_apify(url, max_reviews=150, sort_order="newest"):
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
    # Prompt focado em listas curtas para leitura rápida
    prompt = f"""
    Comparativo Rápido: {nome_a} vs {nome_b}. Foco: {criterio}.
    
    REVIEWS A: {texto_a[:3500]}
    REVIEWS B: {texto_b[:3500]}
    
    Responda EXATAMENTE neste formato visual (Markdown):

    ### 🏆 Veredito Rápido
    (Uma frase dizendo quem ganha e porquê)

    ### ✅ Melhor de {nome_a}
    * (Ponto forte 1)
    * (Ponto forte 2)

    ### 🚨 Pior de {nome_a}
    * (Ponto fraco 1)
    * (Ponto fraco 2)

    ### ✅ Melhor de {nome_b}
    * (Ponto forte 1)
    * (Ponto forte 2)

    ### 🚨 Pior de {nome_b}
    * (Ponto fraco 1)
    * (Ponto fraco 2)

    ---
    ### 🧠 Estratégia Sugerida
    (Um parágrafo de plano de ação)
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
    st.title("📊 Monitor V14")
    menu = st.radio("Menu", ["🏠 Minha Empresa", "🥊 Meus Concorrentes", "⚡ Análise Visual", "📂 Relatórios"])

# ... (Partes 1 e 2 de cadastro mantidas iguais para economizar espaço no chat, 
# se precisar que eu repita, me avise. Focarei na ANÁLISE VISUAL abaixo) ...

if menu == "🏠 Minha Empresa":
    st.header("🏠 Configurar Minha Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        st.success(f"Atual: **{dados['title']}**")
        st.caption(f"📍 {dados.get('address', '')}")
        if st.button("🗑️ Remover"):
            del st.session_state.db_empresas["minha_empresa"]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    else:
        c1, c2, c3 = st.columns([1,2,2])
        uf = c1.selectbox("UF", get_ibge("estados"), index=25)
        city = c2.selectbox("Cidade", get_ibge("cidades", uf))
        nome = c3.text_input("Nome")
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
    c1, c2, c3 = st.columns([1,2,2])
    uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
    city = c2.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
    nome = c3.text_input("Nome Rival")
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
# 3. ANÁLISE VISUAL (DASHBOARD)
# ---------------------------------------------------------
elif menu == "⚡ Análise Visual":
    st.title("⚡ Dashboard de Inteligência")
    
    # Filtros
    with st.expander("⚙️ Configuração da Análise", expanded=True):
        c_dt, c_filt, c_sel = st.columns([1, 1, 2])
        
        with c_dt:
            dt_ini = st.date_input("Início", date.today().replace(day=1))
        with c_filt:
            criterio = st.selectbox("Filtro", ["Padrão (Sem Filtro)", "Mais Recentes", "Piores Notas (1-2★)", "Melhores Notas (5★)"])
        with c_sel:
            opts_a = []
            if st.session_state.db_empresas.get("minha_empresa"):
                opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
            for c in st.session_state.db_empresas.get("concorrentes", []):
                opts_a.append(f"🥊 {c['title']}")
            
            # Seleção lado a lado
            c_sel_a, c_sel_b = st.columns(2)
            sel_a = c_sel_a.selectbox("Lado Esquerdo (Você)", opts_a)
            sel_b = c_sel_b.selectbox("Lado Direito (Rival)", [x for x in opts_a if x != sel_a])

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
            with st.spinner("📊 Construindo dashboard..."):
                # Baixa dados
                api_sort = "mostRelevant" if criterio == "Mais Relevantes" else "newest"
                raw_a = baixar_reviews_apify(obj_a['url'], 100, api_sort)
                raw_b = baixar_reviews_apify(obj_b['url'], 100, api_sort)
                
                if raw_a and raw_b:
                    df_a = pd.DataFrame(raw_a.get('reviews', []))
                    df_b = pd.DataFrame(raw_b.get('reviews', []))
                    
                    # Tratamento Data
                    for df in [df_a, df_b]:
                        if not df.empty and 'publishAt' in df.columns:
                            df['data_obj'] = df['publishAt'].apply(tratar_data_google)
                            df.dropna(subset=['data_obj'], inplace=True)
                            df['data'] = df['data_obj'].dt.date
                    
                    # Filtra
                    df_a = df_a[df_a['data'] >= dt_ini]
                    df_b = df_b[df_b['data'] >= dt_ini]
                    
                    # Filtra Nota (Local)
                    df_a['stars'] = pd.to_numeric(df_a['stars'])
                    df_b['stars'] = pd.to_numeric(df_b['stars'])
                    
                    if criterio == "Piores Notas (1-2★)":
                        df_a = df_a[df_a['stars'] <= 2]
                        df_b = df_b[df_b['stars'] <= 2]
                    elif criterio == "Melhores Notas (5★)":
                        df_a = df_a[df_a['stars'] == 5]
                        df_b = df_b[df_b['stars'] == 5]
                        
                    # Cálculos
                    nota_a = df_a['stars'].mean() if not df_a.empty else 0
                    nota_b = df_b['stars'].mean() if not df_b.empty else 0
                    gap = nota_a - nota_b
                    
                    # IA
                    txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.head(20).iterrows() if r['text']])
                    txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.head(20).iterrows() if r['text']])
                    analise = analisar_ia(txt_a, txt_b, obj_a['title'], obj_b['title'], criterio)
                    
                    # Salva
                    relatorio = {
                        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "data_geracao": datetime.now().strftime("%d/%m %H:%M"),
                        "criterio": criterio,
                        "empresa_a": obj_a['title'],
                        "empresa_b": obj_b['title'],
                        "nota_a_corte": float(nota_a),
                        "nota_b_corte": float(nota_b),
                        "analise_ia": analise,
                        "comentarios_a": df_a.head(50)[['stars', 'text']].to_dict('records'),
                        "comentarios_b": df_b.head(50)[['stars', 'text']].to_dict('records')
                    }
                    st.session_state.db_historico.insert(0, relatorio)
                    salvar_json(DB_HISTORICO, st.session_state.db_historico)
                    
                    # === ÁREA VISUAL DO DASHBOARD ===
                    st.divider()
                    
                    # LINHA 1: PLACAR (GAUGES)
                    col_g1, col_vs, col_g2 = st.columns([1, 0.5, 1])
                    
                    with col_g1:
                        st.markdown(f"<h3 style='text-align: center; color: #4A90E2'>{obj_a['title']}</h3>", unsafe_allow_html=True)
                        st.plotly_chart(criar_gauge(nota_a, "Sua Média", "#4A90E2"), use_container_width=True)
                        
                    with col_vs:
                        st.markdown("<div class='vs-container'>VS</div>", unsafe_allow_html=True)
                        # Gap Metric
                        cor_gap = "green" if gap > 0 else "red"
                        txt_gap = f"{gap:+.1f}"
                        st.markdown(f"<h3 style='text-align: center; color: {cor_gap}'>{txt_gap} Gap</h3>", unsafe_allow_html=True)

                    with col_g2:
                        st.markdown(f"<h3 style='text-align: center; color: #E24A4A'>{obj_b['title']}</h3>", unsafe_allow_html=True)
                        st.plotly_chart(criar_gauge(nota_b, "Média Rival", "#E24A4A"), use_container_width=True)

                    # LINHA 2: GRÁFICO DE BARRAS COMPARATIVO
                    st.plotly_chart(criar_grafico_comparativo(df_a, df_b, "Você", "Rival"), use_container_width=True)
                    
                    # LINHA 3: MELHORES E PIORES (RESUMO IA)
                    st.subheader("📋 Resumo Executivo")
                    
                    # Aqui "hackeamos" o markdown da IA para separar em colunas se possível, 
                    # ou apenas exibimos de forma limpa
                    with st.container(border=True):
                        st.markdown(analise.split("---")[0]) # Mostra só a parte dos bullets
                    
                    # LINHA 4: TEXTÃO (ESCONDIDO)
                    with st.expander("📄 Ver Estratégia Detalhada e Comentários (Clique para ler)"):
                        st.markdown("---")
                        if len(analise.split("---")) > 1:
                            st.markdown(analise.split("---")[1]) # Mostra a estratégia
                        
                        t1, t2 = st.tabs(["💬 Seus Reviews", "💬 Reviews Rival"])
                        with t1: st.dataframe(df_a[['stars', 'text', 'data']])
                        with t2: st.dataframe(df_b[['stars', 'text', 'data']])
                        
                else: st.error("Erro ao baixar dados.")

# ---------------------------------------------------------
# 4. RELATÓRIOS (Mantido com visual melhorado)
# ---------------------------------------------------------
elif menu == "📂 Relatórios":
    st.header("📂 Histórico")
    if not st.session_state.db_historico:
        st.info("Vazio.")
    else:
        opcoes = [f"{r['data_geracao']} | {r.get('criterio','Geral')} | {r['empresa_a']} vs {r['empresa_b']}" for r in st.session_state.db_historico]
        escolha = st.selectbox("Selecione:", opcoes)
        idx = opcoes.index(escolha)
        rel = st.session_state.db_historico[idx]
        
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("Você", f"{rel['nota_a_corte']:.2f} ⭐")
            c2.metric("Rival", f"{rel['nota_b_corte']:.2f} ⭐")
            dif = rel['nota_a_corte'] - rel['nota_b_corte']
            c3.metric("Diferença", f"{dif:+.2f}", delta_color="normal")
            
            st.markdown(rel['analise_ia'])
            
            if st.button("🗑️ Excluir"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
