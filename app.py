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
# 🔐 CONFIGURAÇÃO E CHAVES
# ==========================================
try:
    MY_APIFY_TOKEN = st.secrets["MY_APIFY_TOKEN"]
    MY_GEMINI_KEY = st.secrets["MY_GEMINI_KEY"]
except:
    MY_APIFY_TOKEN = ""
    MY_GEMINI_KEY = ""

st.set_page_config(page_title="Monitor Corp V22", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 🎨 ESTILO ADAPTATIVO (TRANSPARENTE)
# ==========================================
st.markdown("""
<style>
    /* Botões Grandes e Limpos (Fundos adaptáveis) */
    .stButton > button {
        width: 100%;
        height: 70px;
        font-size: 16px;
        font-weight: 600;
        border-radius: 12px;
        margin-bottom: 8px;
    }
    
    /* Botão Voltar */
    .btn-voltar > button {
        height: 40px !important;
        background: transparent;
        border: 1px solid #555;
    }

    /* Cores de Texto para Destaque (Funcionam em Dark/Light) */
    .text-positive { color: #4CAF50; font-weight: bold; }
    .text-negative { color: #FF5252; font-weight: bold; }
    .text-primary { color: #2962FF; font-weight: bold; }
    
    /* Ajuste de Métricas para Mobile */
    [data-testid="stMetricValue"] { font-size: 2rem !important; }
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

# --- GRÁFICOS TRANSPARENTES ---
def criar_grafico_comparativo(df_a, df_b, nome_a, nome_b):
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=[f"{i} ⭐" for i in stars_a.index], x=stars_a.values, 
        name="Sua Empresa", orientation='h', marker_color='#2962FF', 
        text=stars_a.values, textposition='auto'
    ))
    
    fig.add_trace(go.Bar(
        y=[f"{i} ⭐" for i in stars_b.index], x=stars_b.values, 
        name="Concorrente", orientation='h', marker_color='#546E7A', 
        text=stars_b.values, textposition='auto'
    ))

    fig.update_layout(
        title="Volume de Avaliações por Nota",
        barmode='group',
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
        # FUNDO TRANSPARENTE AQUI:
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888'), # Cor do texto adapta levemente
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

# --- IA COM TAGS ---
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
    Atue como Consultor de Negócios.
    EMPRESA PRINCIPAL: {nome_a}
    CONCORRENTE: {nome_b}
    
    REVIEWS PRINCIPAL: {texto_a[:3000]}
    REVIEWS CONCORRENTE: {texto_b[:3000]}
    
    Gere um relatório em Markdown. 
    IMPORTANTE: Crie uma seção de "Palavras-Chave" (Tags) resumindo o que é bom e ruim em 3 ou 4 palavras soltas.
    
    Estrutura Exata:
    
    ### 📊 Resumo Rápido (Tags)
    **{nome_a}**
    * 👍 Positivo: (Ex: Hambúrguer, Atendimento, Rapidez)
    * 👎 Negativo: (Ex: Frio, Atraso, Preço)
    
    **{nome_b}**
    * 👍 Positivo: (Tags do concorrente)
    * 👎 Negativo: (Tags do concorrente)

    ---
    ### 🏆 Conclusão Executiva
    (Resumo de 1 parágrafo sobre quem está melhor)

    ### 💎 Detalhes - Sua Empresa
    (Análise mais profunda dos pontos fortes e fracos)

    ### 🥊 Detalhes - Concorrente
    (Análise profunda dos pontos fortes e fracos deles)

    ### 🚀 Plano de Ação
    (3 ações práticas)
    """
    try:
        return model.generate_content(prompt).text
    except: return "IA indisponível."

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
    st.title("Monitor Corporativo")
    st.markdown("Inteligência de Mercado em Tempo Real.")
    
    if st.button("📊 INICIAR ANÁLISE AGORA", type="primary"): navegar_para("dashboard")
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("🏢 Minha Empresa"): navegar_para("minha_empresa")
    with c2: 
        if st.button("🔎 Concorrentes"): navegar_para("concorrentes")
    with c3: 
        if st.button("📁 Relatórios"): navegar_para("historico")

# 2. MINHA EMPRESA
elif st.session_state.tela_atual == "minha_empresa":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    st.header("🏢 Perfil da Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        st.success(f"Configurada: **{dados['title']}**")
        if st.button("Alterar Empresa"):
            del st.session_state.db_empresas["minha_empresa"]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    else:
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", get_ibge("estados"), index=25)
        city = c1.selectbox("Cidade", get_ibge("cidades", uf))
        nome = st.text_input("Nome da Empresa")
        if st.button("Buscar", type="primary"):
            with st.spinner("Buscando..."):
                res = buscar_locais_apify(f"{nome}, {city} - {uf}")
                if res: st.session_state.busca_minha = res
        if "busca_minha" in st.session_state:
            opts = {f"{x['title']}": x for x in st.session_state.busca_minha}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.button("Salvar Configuração"):
                st.session_state.db_empresas["minha_empresa"] = opts[esc]
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

# 3. CONCORRENTES
elif st.session_state.tela_atual == "concorrentes":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    st.header("🔎 Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    if conc:
        st.dataframe(pd.DataFrame(conc)[['title', 'address']], use_container_width=True)
        to_del = st.selectbox("Remover:", [c['title'] for c in conc], index=None)
        if to_del and st.button("Apagar"):
            st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != to_del]
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()
    st.markdown("---")
    st.subheader("Novo Concorrente")
    c1, c2 = st.columns(2)
    uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
    city = c1.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
    nome = st.text_input("Nome Rival")
    if st.button("Buscar", type="primary"):
        with st.spinner("Buscando..."):
            res = buscar_locais_apify(f"{nome}, {city} - {uf}")
            if res: st.session_state.busca_rival = res
    if "busca_rival" in st.session_state:
        opts = {f"{x['title']}": x for x in st.session_state.busca_rival}
        esc = st.radio("Selecione:", list(opts.keys()), key='rr')
        if st.button("Adicionar Concorrente"):
            if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
            st.session_state.db_empresas["concorrentes"].append(opts[esc])
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()

# 4. DASHBOARD
elif st.session_state.tela_atual == "dashboard":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)

    # CONFIGURAÇÃO
    if st.session_state.dados_analise_atual is None:
        st.title("Parâmetros da Análise")
        
        c1, c2, c3 = st.columns(3)
        dt_ini = c1.date_input("Início", date.today().replace(day=1))
        dt_fim = c2.date_input("Fim", date.today())
        qtd_limite = c3.slider("Amostragem", 10, 100, 30)
        
        opts_a = []
        if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
        for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🔎 {c['title']}")
        
        c_sel_a, c_sel_b = st.columns(2)
        sel_a = c_sel_a.selectbox("Empresa Principal", opts_a)
        sel_b = c_sel_b.selectbox("Concorrente", [x for x in opts_a if x != sel_a])

        def get_obj(txt):
            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
            nome = txt.replace("🔎 ", "")
            for c in st.session_state.db_empresas.get("concorrentes", []):
                if c['title'] == nome: return c
            return None

        if st.button("🔄 GERAR RELATÓRIO", type="primary"):
            obj_a = get_obj(sel_a)
            obj_b = get_obj(sel_b)
            if obj_a and obj_b:
                with st.spinner("Processando Inteligência Artificial..."):
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
                            analise = analisar_ia_corporativa(txt_a, txt_b, obj_a['title'], obj_b['title'])
                            
                            st.session_state.dados_analise_atual = {
                                "df_a": df_a, "df_b": df_b, "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                "analise": analise, "periodo": f"{dt_ini.strftime('%d/%m')} - {dt_fim.strftime('%d/%m')}"
                            }
                            rel = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S"), "data_geracao": datetime.now().strftime("%d/%m %H:%M"),
                                "empresa_a": obj_a['title'], "empresa_b": obj_b['title'],
                                "nota_a_corte": float(df_a['stars'].mean()), "nota_b_corte": float(df_b['stars'].mean()),
                                "analise_ia": analise
                            }
                            st.session_state.db_historico.insert(0, rel)
                            salvar_json(DB_HISTORICO, st.session_state.db_historico)
                            st.rerun()
                        else: st.warning("Dados insuficientes.")

    # PAINEL
    else:
        dados = st.session_state.dados_analise_atual
        c_head1, c_head2 = st.columns([3, 1])
        with c_head2:
            if st.button("🔄 Nova Análise"):
                st.session_state.dados_analise_atual = None
                st.rerun()
        
        st.header("Painel Comparativo")
        
        # PLACAR NATIVO (TRANSPARENTE E RESPONSIVO)
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 0.2, 1])
            with c1:
                st.markdown(f"<div style='text-align:center'><span class='text-primary'>SUA EMPRESA</span></div>", unsafe_allow_html=True)
                st.metric("Nota Média", f"{dados['df_a']['stars'].mean():.2f}", f"{len(dados['df_a'])} reviews")
            with c2:
                st.markdown("<div style='text-align:center; padding-top:20px; font-weight:bold; color:#888'>VS</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='text-align:center'><span style='color:#546E7A; font-weight:bold'>CONCORRENTE</span></div>", unsafe_allow_html=True)
                st.metric("Nota Média", f"{dados['df_b']['stars'].mean():.2f}", f"{len(dados['df_b'])} reviews")
        
        # ÁREA DE TAGS (PALAVRAS-CHAVE)
        st.subheader("📌 Destaques Rápidos (Tags)")
        
        # Extrai a parte das tags do texto da IA (Hack simples de split)
        try:
            resumo_tags = dados['analise'].split("### 🏆 Conclusão")[0]
            with st.container(border=True):
                st.markdown(resumo_tags)
        except:
            st.info("Veja os destaques no relatório completo abaixo.")

        # GRÁFICO
        st.subheader("Indicadores")
        st.plotly_chart(criar_grafico_comparativo(dados['df_a'], dados['df_b'], "Sua Empresa", "Concorrente"), use_container_width=True)
        
        st.markdown("---")
        if st.button("📄 LER RELATÓRIO ESTRATÉGICO COMPLETO", type="primary"): navegar_para("relatorio_detalhado")

# 5. RELATÓRIO
elif st.session_state.tela_atual == "relatorio_detalhado" and st.session_state.dados_analise_atual:
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
    
    dados = st.session_state.dados_analise_atual
    st.header("Dossiê Completo")
    
    with st.container(border=True):
        # Mostra tudo, inclusive as tags de novo se quiser, ou filtra
        st.markdown(dados['analise'])
    
    t1, t2 = st.tabs(["Sua Empresa", "Concorrente"])
    with t1: st.dataframe(dados['df_a'][['stars', 'text', 'data']], use_container_width=True)
    with t2: st.dataframe(dados['df_b'][['stars', 'text', 'data']], use_container_width=True)

# 6. HISTÓRICO
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
            c1, c2 = st.columns(2)
            c1.metric("Você", f"{rel['nota_a_corte']:.2f}")
            c2.metric("Concorrente", f"{rel['nota_b_corte']:.2f}")
            st.markdown(rel['analise_ia'])
            if st.button("🗑️ Excluir"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
