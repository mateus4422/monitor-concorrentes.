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
# 🔐 CONFIGURAÇÃO DE SEGURANÇA E CHAVES
# ==========================================
try:
    MY_APIFY_TOKEN = st.secrets["MY_APIFY_TOKEN"]
    MY_GEMINI_KEY = st.secrets["MY_GEMINI_KEY"]
except:
    MY_APIFY_TOKEN = ""
    MY_GEMINI_KEY = ""

st.set_page_config(page_title="Monitor Corporativo V21", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 🎨 ESTILO CORPORATIVO (CSS)
# ==========================================
st.markdown("""
<style>
    /* Botões Principais - Estilo Clean e Profissional */
    .stButton > button {
        width: 100%;
        height: 70px;
        font-size: 16px;
        font-weight: 500;
        border-radius: 8px;
        margin-bottom: 8px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        color: #333;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        border-color: #2962FF;
        color: #2962FF;
        background-color: #f5f8ff;
    }
    
    /* Botão Primário (Ação) */
    div.stButton > button:first-child[kind="primary"] {
        background-color: #2962FF;
        color: white;
        border: none;
    }

    /* Botão Voltar */
    .btn-voltar > button {
        height: 40px !important;
        background: #f8f9fa;
        color: #555;
        font-size: 14px;
        border: 1px solid #ddd;
    }

    /* PAINEL DE INDICADORES (KPIs) */
    .kpi-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 25px;
    }
    .kpi-box {
        text-align: center;
        width: 45%;
    }
    .kpi-value {
        font-size: 3rem;
        font-weight: 700;
        line-height: 1.2;
        color: #333;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 5px;
    }
    .kpi-divider {
        font-size: 1rem;
        color: #999;
        font-weight: 400;
    }
    
    /* Cores Semânticas */
    .text-primary { color: #2962FF; } /* Azul Corporativo */
    .text-secondary { color: #546E7A; } /* Cinza Azulado */
    
    /* Títulos */
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #1a1a1a; }
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

# --- GRÁFICOS PROFISSIONAIS ---
def criar_grafico_comparativo(df_a, df_b, nome_a, nome_b):
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    
    fig = go.Figure()
    
    # Cores sóbrias: Azul Corporativo vs Cinza Chumbo
    fig.add_trace(go.Bar(
        y=[f"{i} ⭐" for i in stars_a.index], 
        x=stars_a.values, 
        name="Sua Empresa", 
        orientation='h', 
        marker_color='#2962FF', 
        text=stars_a.values, 
        textposition='auto'
    ))
    
    fig.add_trace(go.Bar(
        y=[f"{i} ⭐" for i in stars_b.index], 
        x=stars_b.values, 
        name="Concorrente", 
        orientation='h', 
        marker_color='#546E7A', 
        text=stars_b.values, 
        textposition='auto'
    ))

    fig.update_layout(
        title="Distribuição de Avaliações (Volume x Nota)",
        barmode='group',
        height=320,
        margin=dict(l=50, r=20, t=40, b=20),
        xaxis=dict(showgrid=True, gridcolor='#eee'),
        plot_bgcolor='white',
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

# --- INTEGRAÇÕES ---
def buscar_locais_apify(termo):
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={"searchStringsArray": [termo], "maxCrawledPlacesPerSearch": 5, "language": "pt-BR", "maxReviews": 0})
        return client.dataset(run['defaultDatasetId']).list_items().items
    except: return []

def baixar_reviews_apify(url, max_reviews=100):
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={"startUrls": [{"url": url}], "language": "pt-BR", "maxReviews": max_reviews, "reviewsSort": "newest"})
        items = client.dataset(run['defaultDatasetId']).list_items().items
        return items[0] if items else None
    except: return None

# --- INTELIGÊNCIA ARTIFICIAL (RELATÓRIO EXECUTIVO) ---
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

def analisar_ia_corporativa(texto_a, texto_b, nome_a, nome_b):
    prompt = f"""
    Atue como um Consultor Sênior de Estratégia de Negócios.
    Objetivo: Elaborar um Relatório Comparativo de Mercado (Benchmarking).
    
    EMPRESA PRINCIPAL (CLIENTE): {nome_a}
    CONCORRENTE (BENCHMARK): {nome_b}
    
    DADOS (REVIEWS RECENTES):
    --- EMPRESA PRINCIPAL ---
    {texto_a[:3500]}
    
    --- CONCORRENTE ---
    {texto_b[:3500]}
    
    Gere um relatório técnico em Markdown com a seguinte estrutura:

    ### 1. Conclusão Executiva
    (Resumo gerencial objetivo sobre o posicionamento da Empresa Principal frente ao Concorrente. Evite linguagem coloquial.)

    ---
    ### 2. Análise da Empresa Principal ({nome_a})
    **✅ Pontos de Excelência:**
    * (Fator chave de sucesso identificado)
    * (Fator chave de sucesso identificado)
    
    **⚠️ Pontos de Melhoria (Gaps):**
    * (Ponto crítico identificado)
    * (Ponto crítico identificado)

    ---
    ### 3. Análise do Concorrente ({nome_b})
    **🎯 Vantagens Competitivas (Onde eles se destacam):**
    * (Diferencial do concorrente)
    
    **📉 Vulnerabilidades (Oportunidades para o Cliente):**
    * (Falha do concorrente que pode ser explorada)

    ---
    ### 4. Recomendações Estratégicas
    (3 ações práticas e profissionais para ganho de market share ou melhoria de reputação)
    """
    try:
        return model.generate_content(prompt).text
    except: return "Serviço de IA indisponível no momento."

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
# FLUXO DA APLICAÇÃO
# ==========================================

# 1. MENU PRINCIPAL
if st.session_state.tela_atual == "menu_principal":
    st.title("Monitor Corporativo")
    st.markdown("Bem-vindo ao painel de inteligência competitiva.")
    st.markdown("---")
    
    if st.button("📊 PAINEL DE INDICADORES (Iniciar Análise)"): navegar_para("dashboard")
    if st.button("🏢 GERENCIAR MINHA EMPRESA"): navegar_para("minha_empresa")
    if st.button("🔎 GERENCIAR CONCORRENTES"): navegar_para("concorrentes")
    if st.button("📁 RELATÓRIOS SALVOS"): navegar_para("historico")

# 2. CONFIGURAÇÃO (MINHA EMPRESA)
elif st.session_state.tela_atual == "minha_empresa":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Menu Principal"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("🏢 Perfil da Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    
    if dados:
        st.success(f"Empresa Configurada: **{dados['title']}**")
        st.info("Para alterar a empresa principal, clique abaixo.")
        if st.button("Redefinir Empresa Principal"):
            del st.session_state.db_empresas["minha_empresa"]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    else:
        st.markdown("Configure sua empresa para automatizar as análises.")
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", get_ibge("estados"), index=25)
        city = c1.selectbox("Cidade", get_ibge("cidades", uf))
        nome = st.text_input("Razão Social ou Nome Fantasia")
        
        if st.button("🔍 Localizar Empresa", type="primary"):
            with st.spinner("Consultando base de dados..."):
                res = buscar_locais_apify(f"{nome}, {city} - {uf}")
                if res: st.session_state.busca_minha = res
                
        if "busca_minha" in st.session_state:
            opts = {f"{x['title']}": x for x in st.session_state.busca_minha}
            esc = st.radio("Selecione o registro correspondente:", list(opts.keys()))
            if st.button("💾 Confirmar Configuração"):
                st.session_state.db_empresas["minha_empresa"] = opts[esc]
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

# 3. CONFIGURAÇÃO (CONCORRENTES)
elif st.session_state.tela_atual == "concorrentes":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Menu Principal"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("🔎 Gestão de Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    
    if conc:
        st.dataframe(pd.DataFrame(conc)[['title', 'address']].rename(columns={'title': 'Empresa', 'address': 'Endereço'}), use_container_width=True)
        
        to_del = st.selectbox("Selecione para remover:", [c['title'] for c in conc], index=None, placeholder="Selecione um concorrente...")
        if to_del and st.button("Remover Selecionado"):
            st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != to_del]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
            
    st.markdown("---")
    st.subheader("Adicionar Novo Concorrente")
    c1, c2 = st.columns(2)
    uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
    city = c1.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
    nome = st.text_input("Nome do Concorrente")
    
    if st.button("🔍 Buscar Concorrente", type="primary"):
        with st.spinner("Consultando base de dados..."):
            res = buscar_locais_apify(f"{nome}, {city} - {uf}")
            if res: st.session_state.busca_rival = res
            
    if "busca_rival" in st.session_state:
        opts = {f"{x['title']}": x for x in st.session_state.busca_rival}
        esc = st.radio("Selecione o registro:", list(opts.keys()), key='rr')
        if st.button("💾 Adicionar à Lista"):
            if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
            st.session_state.db_empresas["concorrentes"].append(opts[esc])
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()

# 4. DASHBOARD (ANÁLISE)
elif st.session_state.tela_atual == "dashboard":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)

    # VIEW 1: CONFIGURAÇÃO DA ANÁLISE
    if st.session_state.dados_analise_atual is None:
        st.title("Configuração da Análise")
        st.markdown("Defina os parâmetros para o relatório comparativo.")
        
        c1, c2, c3 = st.columns(3)
        dt_ini = c1.date_input("Data Início", date.today().replace(day=1))
        dt_fim = c2.date_input("Data Término", date.today())
        qtd_limite = c3.slider("Amostragem (Qtd. Reviews)", 10, 100, 30, help="Quantidade de avaliações a serem processadas para cada empresa.")
        
        opts_a = []
        if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
        for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🔎 {c['title']}")
        
        c_sel_a, c_sel_b = st.columns(2)
        sel_a = c_sel_a.selectbox("Empresa Principal", opts_a)
        sel_b = c_sel_b.selectbox("Empresa Comparada (Concorrente)", [x for x in opts_a if x != sel_a])

        def get_obj(txt):
            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
            nome = txt.replace("🔎 ", "")
            for c in st.session_state.db_empresas.get("concorrentes", []):
                if c['title'] == nome: return c
            return None

        if st.button("🔄 PROCESSAR DADOS E GERAR INDICADORES", type="primary"):
            obj_a = get_obj(sel_a)
            obj_b = get_obj(sel_b)
            
            if obj_a and obj_b:
                with st.spinner("Coletando dados, calculando métricas e gerando inteligência..."):
                    raw_a = baixar_reviews_apify(obj_a['url'], 150)
                    raw_b = baixar_reviews_apify(obj_b['url'], 150)
                    
                    if raw_a and raw_b:
                        df_a = pd.DataFrame(raw_a.get('reviews', []))
                        df_b = pd.DataFrame(raw_b.get('reviews', []))
                        
                        # Processamento de Dados
                        for df in [df_a, df_b]:
                            if not df.empty and 'publishAt' in df.columns:
                                df['data_obj'] = df['publishAt'].apply(tratar_data_google)
                                df.dropna(subset=['data_obj'], inplace=True)
                                df['data'] = df['data_obj'].dt.date
                                df['stars'] = pd.to_numeric(df['stars'])
                        
                        # Filtros Temporais
                        df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)].head(qtd_limite)
                        df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)].head(qtd_limite)
                        
                        if not df_a.empty and not df_b.empty:
                            # Geração de Texto para IA
                            txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                            txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                            
                            # Chamada IA Corporativa
                            analise = analisar_ia_corporativa(txt_a, txt_b, obj_a['title'], obj_b['title'])
                            
                            # Salvar Sessão
                            st.session_state.dados_analise_atual = {
                                "df_a": df_a, "df_b": df_b,
                                "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                "analise": analise, "periodo": f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
                            }
                            
                            # Salvar Histórico
                            rel = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S"), 
                                "data_geracao": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "empresa_a": obj_a['title'], 
                                "empresa_b": obj_b['title'],
                                "nota_a_corte": float(df_a['stars'].mean()), 
                                "nota_b_corte": float(df_b['stars'].mean()),
                                "analise_ia": analise
                            }
                            st.session_state.db_historico.insert(0, rel)
                            salvar_json(DB_HISTORICO, st.session_state.db_historico)
                            st.rerun()
                        else: st.warning("Dados insuficientes para o período selecionado.")

    # VIEW 2: PAINEL DE RESULTADOS
    else:
        dados = st.session_state.dados_analise_atual
        
        c_act1, c_act2 = st.columns([3, 1])
        with c_act2:
            if st.button("🔄 Nova Análise"):
                st.session_state.dados_analise_atual = None
                st.rerun()
        
        st.header("Painel Comparativo")
        st.caption(f"Período Analisado: {dados['periodo']}")
            
        # KPI Calculation
        nota_a = dados['df_a']['stars'].mean()
        nota_b = dados['df_b']['stars'].mean()
        gap = nota_a - nota_b
        
        # HTML SCOREBOARD (PROFISSIONAL)
        st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-box">
                <div class="kpi-label text-primary">SUA EMPRESA</div>
                <div class="kpi-value text-primary">{nota_a:.2f}</div>
                <div class="kpi-divider">{len(dados['df_a'])} avaliações</div>
            </div>
            <div class="kpi-box" style="width: 10%;">
                <div class="kpi-divider">vs</div>
            </div>
            <div class="kpi-box">
                <div class="kpi-label text-secondary">CONCORRENTE</div>
                <div class="kpi-value text-secondary">{nota_b:.2f}</div>
                <div class="kpi-divider">{len(dados['df_b'])} avaliações</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Indicador de Performance Relativa
        if gap > 0: 
            st.success(f"📈 **Desempenho Superior:** Sua nota média está **{gap:+.2f} pontos** acima do concorrente.")
        elif gap < 0: 
            st.error(f"📉 **Desempenho Inferior:** Sua nota média está **{gap:+.2f} pontos** abaixo do concorrente.")
        else:
            st.info("⚖️ **Desempenho Equivalente:** As notas médias estão empatadas.")
        
        # Gráfico
        st.subheader("Indicadores de Qualidade")
        st.plotly_chart(criar_grafico_comparativo(dados['df_a'], dados['df_b'], "Sua Empresa", "Concorrente"), use_container_width=True)
        
        # Dados de Sentimento
        st.subheader("Detalhamento do Sentimento do Cliente")
        c1, c2 = st.columns(2)
        with c1: 
            positivos = len(dados['df_a'][dados['df_a']['stars'] == 5])
            negativos = len(dados['df_a'][dados['df_a']['stars'] <= 2])
            st.markdown(f"**Sua Empresa:**")
            st.markdown(f"✅ **{positivos}** Clientes Satisfeitos (Promotores)")
            st.markdown(f"⚠️ **{negativos}** Clientes Insatisfeitos (Detratores)")
            
        with c2: 
            positivos_b = len(dados['df_b'][dados['df_b']['stars'] == 5])
            negativos_b = len(dados['df_b'][dados['df_b']['stars'] <= 2])
            st.markdown(f"**Concorrente:**")
            st.markdown(f"✅ **{positivos_b}** Clientes Satisfeitos")
            st.markdown(f"⚠️ **{negativos_b}** Clientes Insatisfeitos")
            
        st.markdown("---")
        if st.button("📄 ACESSAR RELATÓRIO ESTRATÉGICO DETALHADO", type="primary"): 
            navegar_para("relatorio_detalhado")

# 5. RELATÓRIO DETALHADO
elif st.session_state.tela_atual == "relatorio_detalhado" and st.session_state.dados_analise_atual:
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Painel"): navegar_para("dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
    
    dados = st.session_state.dados_analise_atual
    
    st.header("Relatório Estratégico de IA")
    st.markdown("Análise gerada via inteligência artificial com base nos comentários públicos.")
    
    with st.container(border=True):
        st.markdown(dados['analise'])
    
    st.subheader("Base de Dados (Transparência)")
    t1, t2 = st.tabs(["Avaliações da Sua Empresa", "Avaliações do Concorrente"])
    with t1: st.dataframe(dados['df_a'][['stars', 'text', 'data']].rename(columns={'stars': 'Nota', 'text': 'Comentário', 'data': 'Data'}), use_container_width=True)
    with t2: st.dataframe(dados['df_b'][['stars', 'text', 'data']].rename(columns={'stars': 'Nota', 'text': 'Comentário', 'data': 'Data'}), use_container_width=True)

# 6. HISTÓRICO
elif st.session_state.tela_atual == "historico":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Menu"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("Relatórios Arquivados")
    if not st.session_state.db_historico: st.info("Nenhum relatório salvo no histórico.")
    else:
        opcoes = [f"{r['data_geracao']} | {r['empresa_a']} vs {r['empresa_b']}" for r in st.session_state.db_historico]
        escolha = st.selectbox("Selecione um relatório para visualizar:", opcoes)
        idx = opcoes.index(escolha)
        rel = st.session_state.db_historico[idx]
        
        with st.container(border=True):
            c1, c2 = st.columns(2)
            c1.metric("Sua Nota (Histórico)", f"{rel['nota_a_corte']:.2f}")
            c2.metric("Concorrente (Histórico)", f"{rel['nota_b_corte']:.2f}")
            
            st.markdown("---")
            st.markdown(rel['analise_ia'])
            
            if st.button("🗑️ Excluir Registro"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
