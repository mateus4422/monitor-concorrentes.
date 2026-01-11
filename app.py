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

st.set_page_config(page_title="Monitor Corp V24", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 🎨 ESTILO PROFISSIONAL (CSS)
# ==========================================
st.markdown("""
<style>
    /* CARTÕES (Cards) */
    .card-container {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 20px;
    }
    
    /* Tutorial Steps */
    .step-box {
        display: flex; align-items: center; margin-bottom: 15px;
        background-color: rgba(255, 255, 255, 0.02);
        padding: 15px; border-radius: 10px; border-left: 4px solid #2962FF;
    }
    .step-num { font-size: 24px; font-weight: bold; color: #2962FF; margin-right: 15px; min-width: 30px; }
    .step-text { font-size: 16px; }

    /* Botões Padrão (Menu) */
    .stButton > button {
        width: 100%; height: 60px; font-size: 16px; font-weight: 600;
        border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.3);
        margin-bottom: 10px; transition: all 0.2s;
    }
    .stButton > button:hover { border-color: #2962FF; color: #2962FF; background-color: rgba(41, 98, 255, 0.1); }
    
    /* Botão Primário (Dentro de Forms) */
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #2962FF; color: white; border: none; height: 60px; font-size: 18px; width: 100%;
    }
    div.stButton > button:first-child[kind="primary"] {
        background-color: #2962FF; color: white; border: none; height: 70px; font-size: 18px;
    }

    /* Botão Voltar */
    .btn-voltar > button { height: 40px !important; background: transparent; border: 1px solid #555; width: auto !important; padding: 0 20px; }
    .text-primary { color: #2962FF; font-weight: bold; }
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

# --- GRÁFICOS ---
def criar_grafico_comparativo(df_a, df_b, nome_a, nome_b):
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_a.index], x=stars_a.values, name="Sua Empresa", orientation='h', marker_color='#2962FF', text=stars_a.values, textposition='auto'))
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_b.index], x=stars_b.values, name="Concorrente", orientation='h', marker_color='#546E7A', text=stars_b.values, textposition='auto'))
    fig.update_layout(title="Volume de Avaliações por Nota", barmode='group', height=320, margin=dict(l=20, r=20, t=40, b=20), xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#888'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
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

def analisar_ia_corporativa(texto_a, texto_b, nome_a, nome_b):
    prompt = f"""
    Atue como Consultor de Negócios.
    EMPRESA PRINCIPAL: {nome_a}
    CONCORRENTE: {nome_b}
    REVIEWS PRINCIPAL: {texto_a[:3000]}
    REVIEWS CONCORRENTE: {texto_b[:3000]}
    
    Gere um relatório Executivo em Markdown.
    
    Estrutura Exata:
    
    ### 📊 Resumo Rápido (Tags)
    **{nome_a}**
    * 👍 Positivo: (3 tags curtas)
    * 👎 Negativo: (3 tags curtas)
    
    **{nome_b}**
    * 👍 Positivo: (Tags do concorrente)
    * 👎 Negativo: (Tags do concorrente)

    ---
    ### 🏆 Conclusão Executiva
    (Resumo de 1 parágrafo sobre quem está melhor)

    ### 💎 Detalhes - Sua Empresa
    (Análise profunda dos pontos fortes e fracos)

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

# 1. MENU PRINCIPAL
if st.session_state.tela_atual == "menu_principal":
    st.title("Monitor Corporativo")
    st.caption("Inteligência de Mercado & Benchmarking")
    st.markdown("---")

    col_tutorial, col_menu = st.columns([1.5, 1], gap="large")
    
    with col_tutorial:
        st.subheader("📘 Como usar a ferramenta")
        st.markdown("""
        <div class="card-container">
            <div class="step-box"><div class="step-num">1</div><div class="step-text"><b>Cadastre sua Empresa</b><br>Vá em "Minha Empresa" e defina o negócio principal.</div></div>
            <div class="step-box"><div class="step-num">2</div><div class="step-text"><b>Adicione Concorrentes</b><br>Cadastre os principais rivais do seu setor.</div></div>
            <div class="step-box"><div class="step-num">3</div><div class="step-text"><b>Execute a Análise</b><br>Clique no botão azul "Iniciar Análise".</div></div>
        </div>
        """, unsafe_allow_html=True)

    with col_menu:
        st.subheader("🚀 Central de Comando")
        with st.container(border=True):
            if st.button("📊 INICIAR ANÁLISE AGORA", type="primary"): navegar_para("dashboard")
            st.markdown("---")
            if st.button("🏢 Gerenciar Minha Empresa"): navegar_para("minha_empresa")
            if st.button("🔎 Gerenciar Concorrentes"): navegar_para("concorrentes")
            if st.button("📁 Histórico de Relatórios"): navegar_para("historico")

# 2. MINHA EMPRESA (COM FORMULÁRIO)
elif st.session_state.tela_atual == "minha_empresa":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Início"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("🏢 Perfil da Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    
    with st.container(border=True):
        if dados:
            st.success(f"Configurada: **{dados['title']}**")
            st.caption(dados.get('address', ''))
            if st.button("Alterar Empresa"):
                del st.session_state.db_empresas["minha_empresa"]
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()
        else:
            st.info("Nenhuma empresa configurada.")
            
            # --- FORMULÁRIO DE BUSCA (Protege contra duplo clique) ---
            with st.form("form_busca_minha"):
                c1, c2 = st.columns(2)
                uf = c1.selectbox("UF", get_ibge("estados"), index=25)
                city = c1.selectbox("Cidade", get_ibge("cidades", uf))
                nome = st.text_input("Nome da Empresa")
                
                # O spinner roda apenas quando o formulário é submetido
                submitted = st.form_submit_button("🔍 Localizar Empresa")
                
                if submitted:
                    with st.spinner("Consultando Google Maps..."):
                        res = buscar_locais_apify(f"{nome}, {city} - {uf}")
                        if res: 
                            st.session_state.busca_minha = res
                        else:
                            st.error("Empresa não encontrada.")

            if "busca_minha" in st.session_state:
                with st.form("form_salvar_minha"):
                    opts = {f"{x['title']}": x for x in st.session_state.busca_minha}
                    esc = st.radio("Selecione o registro correspondente:", list(opts.keys()))
                    
                    save_submitted = st.form_submit_button("💾 Confirmar Configuração")
                    if save_submitted:
                        st.session_state.db_empresas["minha_empresa"] = opts[esc]
                        salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                        st.session_state.pop("busca_minha", None) # Limpa busca
                        st.rerun()

# 3. CONCORRENTES (COM FORMULÁRIO)
elif st.session_state.tela_atual == "concorrentes":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Início"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("🔎 Gestão de Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    
    with st.container(border=True):
        if conc:
            st.dataframe(pd.DataFrame(conc)[['title', 'address']], use_container_width=True)
            
            with st.form("form_del_conc"):
                to_del = st.selectbox("Selecione para remover:", [c['title'] for c in conc])
                del_submitted = st.form_submit_button("Remover Selecionado")
                if del_submitted and to_del:
                    st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != to_del]
                    salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                    st.rerun()
        else:
            st.info("Lista vazia.")
            
    st.markdown("### Adicionar Novo Concorrente")
    
    # --- FORMULÁRIO DE BUSCA RIVAL ---
    with st.form("form_busca_rival"):
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
        city = c1.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
        nome = st.text_input("Nome do Concorrente")
        
        search_rival = st.form_submit_button("🔍 Buscar Concorrente")
        
        if search_rival:
            with st.spinner("Buscando concorrente..."):
                res = buscar_locais_apify(f"{nome}, {city} - {uf}")
                if res: st.session_state.busca_rival = res
                else: st.error("Não encontrado.")
            
    if "busca_rival" in st.session_state:
        with st.form("form_add_rival"):
            opts = {f"{x['title']}": x for x in st.session_state.busca_rival}
            esc = st.radio("Selecione o registro:", list(opts.keys()), key='rr')
            
            add_submitted = st.form_submit_button("💾 Adicionar à Lista")
            if add_submitted:
                if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
                st.session_state.db_empresas["concorrentes"].append(opts[esc])
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.session_state.pop("busca_rival", None)
                st.rerun()

# 4. DASHBOARD (ANÁLISE COM FORMULÁRIO)
elif st.session_state.tela_atual == "dashboard":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)

    # CONFIGURAÇÃO DA ANÁLISE
    if st.session_state.dados_analise_atual is None:
        st.title("Parâmetros da Análise")
        
        # --- FORMULÁRIO DE ANÁLISE (O MAIS IMPORTANTE) ---
        with st.form("form_analise"):
            c1, c2, c3 = st.columns(3)
            dt_ini = c1.date_input("Data Início", date.today().replace(day=1))
            dt_fim = c2.date_input("Data Término", date.today())
            qtd_limite = c3.slider("Amostragem", 10, 100, 30)
            
            opts_a = []
            if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
            for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🔎 {c['title']}")
            
            c_sel_a, c_sel_b = st.columns(2)
            sel_a = c_sel_a.selectbox("Empresa Principal", opts_a)
            # Logica simples para evitar crash se lista vazia
            opcoes_b = [x for x in opts_a if x != sel_a]
            sel_b = c_sel_b.selectbox("Concorrente", opcoes_b if opcoes_b else ["Sem concorrente"])

            # O BOTÃO DE AÇÃO FICA AQUI DENTRO
            submitted_analise = st.form_submit_button("🔄 PROCESSAR DADOS E GERAR INDICADORES")
            
            if submitted_analise:
                if not opcoes_b:
                    st.error("Cadastre pelo menos 1 concorrente.")
                else:
                    # Função Helper interna
                    def get_obj(txt):
                        if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
                        nome = txt.replace("🔎 ", "")
                        for c in st.session_state.db_empresas.get("concorrentes", []):
                            if c['title'] == nome: return c
                        return None

                    obj_a = get_obj(sel_a)
                    obj_b = get_obj(sel_b)
                    
                    if obj_a and obj_b:
                        with st.spinner("Coletando dados, calculando métricas e gerando inteligência..."):
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
                                        "analise": analise, "periodo": f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
                                    }
                                    
                                    rel = {
                                        "id": datetime.now().strftime("%Y%m%d%H%M%S"), "data_geracao": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                        "empresa_a": obj_a['title'], "empresa_b": obj_b['title'],
                                        "nota_a_corte": float(df_a['stars'].mean()), "nota_b_corte": float(df_b['stars'].mean()),
                                        "analise_ia": analise
                                    }
                                    st.session_state.db_historico.insert(0, rel)
                                    salvar_json(DB_HISTORICO, st.session_state.db_historico)
                                    st.rerun()
                                else: st.error("Dados insuficientes para o período.")

    # VIEW: PAINEL DE RESULTADOS
    else:
        dados = st.session_state.dados_analise_atual
        c_act1, c_act2 = st.columns([3, 1])
        with c_act2:
            if st.button("🔄 Nova Análise"):
                st.session_state.dados_analise_atual = None
                st.rerun()
        
        st.header("Painel Comparativo")
        st.caption(f"Período Analisado: {dados['periodo']}")
            
        nota_a = dados['df_a']['stars'].mean()
        nota_b = dados['df_b']['stars'].mean()
        gap = nota_a - nota_b
        
        # HTML SCOREBOARD
        st.markdown(f"""
        <div class="card-container" style="display:flex; justify-content:space-between; align-items:center;">
            <div style="text-align:center; width:45%;">
                <div class="text-primary" style="font-size:0.9rem;">SUA EMPRESA</div>
                <div class="text-primary" style="font-size:3rem; font-weight:bold;">{nota_a:.2f}</div>
                <div style="color:#888;">{len(dados['df_a'])} reviews</div>
            </div>
            <div style="font-size:1.5rem; color:#888; font-weight:bold;">VS</div>
            <div style="text-align:center; width:45%;">
                <div style="color:#546E7A; font-size:0.9rem;">CONCORRENTE</div>
                <div style="color:#546E7A; font-size:3rem; font-weight:bold;">{nota_b:.2f}</div>
                <div style="color:#888;">{len(dados['df_b'])} reviews</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if gap > 0: st.success(f"📈 **Desempenho Superior:** +{gap:.2f} pontos acima do concorrente.")
        elif gap < 0: st.error(f"📉 **Desempenho Inferior:** {gap:.2f} pontos abaixo do concorrente.")
        else: st.info("⚖️ **Desempenho Equivalente.**")
        
        st.subheader("📌 Destaques Rápidos (Tags)")
        try:
            resumo_tags = dados['analise'].split("### 🏆 Conclusão")[0]
            with st.container(border=True): st.markdown(resumo_tags)
        except: st.info("Ver relatório completo.")

        st.subheader("Indicadores de Qualidade")
        st.plotly_chart(criar_grafico_comparativo(dados['df_a'], dados['df_b'], "Sua Empresa", "Concorrente"), use_container_width=True)
        
        st.markdown("---")
        if st.button("📄 ACESSAR RELATÓRIO ESTRATÉGICO DETALHADO", type="primary"): 
            navegar_para("relatorio_detalhado")

# 5. RELATÓRIO
elif st.session_state.tela_atual == "relatorio_detalhado" and st.session_state.dados_analise_atual:
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Painel"): navegar_para("dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
    
    dados = st.session_state.dados_analise_atual
    st.header("Relatório Estratégico de IA")
    
    with st.container(border=True):
        st.markdown(dados['analise'])
    
    st.subheader("Base de Dados")
    t1, t2 = st.tabs(["Sua Empresa", "Concorrente"])
    with t1: st.dataframe(dados['df_a'][['stars', 'text', 'data']], use_container_width=True)
    with t2: st.dataframe(dados['df_b'][['stars', 'text', 'data']], use_container_width=True)

# 6. HISTÓRICO
elif st.session_state.tela_atual == "historico":
    st.markdown('<div class="btn-voltar">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Menu"): navegar_para("menu_principal")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.header("Relatórios Arquivados")
    if not st.session_state.db_historico: st.info("Vazio.")
    else:
        opcoes = [f"{r['data_geracao']} | {r['empresa_a']} vs {r['empresa_b']}" for r in st.session_state.db_historico]
        escolha = st.selectbox("Selecione:", opcoes)
        idx = opcoes.index(escolha)
        rel = st.session_state.db_historico[idx]
        with st.container(border=True):
            c1, c2 = st.columns(2)
            c1.metric("Você", f"{rel['nota_a_corte']:.2f}")
            c2.metric("Rival", f"{rel['nota_b_corte']:.2f}")
            st.markdown(rel['analise_ia'])
            if st.button("🗑️ Excluir Registro"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
