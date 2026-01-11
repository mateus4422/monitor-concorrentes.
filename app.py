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
    """, unsafe_allow_html=True)

# ==========================================
# 2. DASHBOARD (ANÁLISE)
# ==========================================
elif menu == "📊 Painel de Análise":
    st.title("Painel de Inteligência")
    
    if st.session_state.dados_analise is None:
        with st.container(border=True):
            st.subheader("Parâmetros da Pesquisa")
            with st.form("form_analise"):
                c1, c2, c3 = st.columns(3)
                dt_ini = c1.date_input("Início", date.today().replace(day=1))
                dt_fim = c2.date_input("Fim", date.today())
                qtd = c3.slider("Amostra", 10, 100, 30)
                
                opts = []
                if st.session_state.db_empresas.get("minha_empresa"): opts.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
                for c in st.session_state.db_empresas.get("concorrentes", []): opts.append(f"🔎 {c['title']}")
                
                c_sel1, c_sel2 = st.columns(2)
                sel_a = c_sel1.selectbox("Empresa Base", opts)
                opcoes_b = [x for x in opts if x != sel_a]
                sel_b = c_sel2.selectbox("Concorrente", opcoes_b if opcoes_b else ["Sem opções"])
                
                submit = st.form_submit_button("🚀 INICIAR PROCESSAMENTO")
                
                if submit:
                    if not opcoes_b: st.error("Cadastre concorrentes primeiro.")
                    else:
                        def get_obj(txt):
                            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
                            nome = txt.replace("🔎 ", "")
                            for c in st.session_state.db_empresas.get("concorrentes", []):
                                if c['title'] == nome: return c
                            return None
                        
                        obj_a = get_obj(sel_a)
                        obj_b = get_obj(sel_b)
                        
                        with st.spinner("Conectando aos satélites..."):
                            raw_a = bk.baixar_reviews(obj_a['url'], 150)
                            raw_b = bk.baixar_reviews(obj_b['url'], 150)
                            
                            if raw_a and raw_b:
                                df_a = pd.DataFrame(raw_a.get('reviews', []))
                                df_b = pd.DataFrame(raw_b.get('reviews', []))
                                
                                for df in [df_a, df_b]:
                                    if not df.empty and 'publishAt' in df.columns:
                                        df['data_obj'] = df['publishAt'].apply(bk.tratar_data_google)
                                        df.dropna(subset=['data_obj'], inplace=True)
                                        df['data'] = df['data_obj'].dt.date
                                        df['stars'] = pd.to_numeric(df['stars'])
                                
                                df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)].head(qtd)
                                df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)].head(qtd)
                                
                                if not df_a.empty and not df_b.empty:
                                    txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                                    txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                                    
                                    analise = bk.gerar_analise_ia(txt_a, txt_b, obj_a['title'], obj_b['title'])
                                    
                                    st.session_state.dados_analise = {
                                        "df_a": df_a, "df_b": df_b, "analise": analise,
                                        "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                        "periodo": f"{dt_ini.strftime('%d/%m')} a {dt_fim.strftime('%d/%m')}"
                                    }
                                    rel = {
                                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                        "empresa_a": obj_a['title'], "empresa_b": obj_b['title'],
                                        "nota_a": float(df_a['stars'].mean()), "nota_b": float(df_b['stars'].mean()),
                                        "analise_ia": analise
                                    }
                                    st.session_state.db_historico.insert(0, rel)
                                    bk.salvar_dados(bk.DB_HISTORICO, st.session_state.db_historico)
                                    st.rerun()
                                else: st.warning("Dados insuficientes no período.")
    else:
        dados = st.session_state.dados_analise
        c1, c2 = st.columns([4, 1])
        with c1: st.caption(f"Período: {dados['periodo']}")
        with c2: 
            if st.button("🔄 Nova Pesquisa"):
                st.session_state.dados_analise = None
                st.rerun()
        
        nota_a = dados['df_a']['stars'].mean()
        nota_b = dados['df_b']['stars'].mean()
        gap = nota_a - nota_b
        
        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        with c_kpi1: st.markdown(f"""<div class="kpi-box"><div class="kpi-lbl" style="color:#2962FF">SUA EMPRESA</div><div class="kpi-val">{nota_a:.2f}</div><div class="kpi-lbl">{len(dados['df_a'])} reviews</div></div>""", unsafe_allow_html=True)
        with c_kpi2:
            cor = "#4CAF50" if gap > 0 else "#FF5252"
            sinal = "+" if gap > 0 else ""
            st.markdown(f"""<div class="kpi-box" style="border: 1px solid {cor}"><div class="kpi-lbl" style="color:{cor}">GAP COMPETITIVO</div><div class="kpi-val" style="color:{cor}">{sinal}{gap:.2f}</div></div>""", unsafe_allow_html=True)
        with c_kpi3: st.markdown(f"""<div class="kpi-box"><div class="kpi-lbl" style="color:#546E7A">CONCORRENTE</div><div class="kpi-val">{nota_b:.2f}</div><div class="kpi-lbl">{len(dados['df_b'])} reviews</div></div>""", unsafe_allow_html=True)
            
        st.markdown("###")
        t1, t2, t3 = st.tabs(["📊 Visão Geral", "📑 Relatório IA", "🔎 Dados Brutos"])
        
        with t1:
            try:
                tags = dados['analise'].split("### 🏆")[0]
                with st.container(border=True): st.markdown(tags)
            except: pass
            render_grafico_comparativo(dados['df_a'], dados['df_b'])
        with t2:
            with st.container(border=True): st.markdown(dados['analise'])
        with t3:
            c1, c2 = st.columns(2)
            c1.dataframe(dados['df_a'][['stars','text','data']], use_container_width=True)
            c2.dataframe(dados['df_b'][['stars','text','data']], use_container_width=True)

# ==========================================
# 3. MINHA EMPRESA
# ==========================================
elif menu == "🏢 Minha Empresa":
    st.title("Perfil da Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        with st.container(border=True):
            st.info(f"Empresa Atual: **{dados['title']}**")
            if st.button("Remover"):
                del st.session_state.db_empresas["minha_empresa"]
                bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()
    else:
        with st.form("minha_emp"):
            c1, c2 = st.columns(2)
            uf = c1.selectbox("UF", bk.get_ibge_locais("estados"), index=25)
            city = c1.selectbox("Cidade", bk.get_ibge_locais("cidades", uf))
            nome = st.text_input("Nome")
            if st.form_submit_button("Buscar"):
                res = bk.buscar_locais(f"{nome}, {city} - {uf}")
                if res: st.session_state.temp_minha = res
        
        if "temp_minha" in st.session_state:
            with st.form("save_m"):
                opts = {f"{x['title']}": x for x in st.session_state.temp_minha}
                esc = st.radio("Selecione:", list(opts.keys()))
                if st.form_submit_button("Salvar"):
                    st.session_state.db_empresas["minha_empresa"] = opts[esc]
                    bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                    st.rerun()

# ==========================================
# 4. CONCORRENTES
# ==========================================
elif menu == "🔎 Concorrentes":
    st.title("Gestão de Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    if conc:
        st.dataframe(pd.DataFrame(conc)[['title','address']], use_container_width=True)
        with st.form("del_c"):
            sel = st.selectbox("Remover:", [c['title'] for c in conc])
            if st.form_submit_button("Apagar"):
                st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != sel]
                bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()
    
    st.divider()
    st.subheader("Adicionar Novo")
    with st.form("add_c"):
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", bk.get_ibge_locais("estados"), index=25, key='ufr')
        city = c1.selectbox("Cidade", bk.get_ibge_locais("cidades", uf), key='cr')
        nome = st.text_input("Nome Rival")
        if st.form_submit_button("Buscar"):
            res = bk.buscar_locais(f"{nome}, {city} - {uf}")
            if res: st.session_state.temp_rival = res
            
    if "temp_rival" in st.session_state:
        with st.form("save_r"):
            opts = {f"{x['title']}": x for x in st.session_state.temp_rival}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.form_submit_button("Adicionar"):
                if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
                st.session_state.db_empresas["concorrentes"].append(opts[esc])
                bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

# ==========================================
# 5. HISTÓRICO
# ==========================================
elif menu == "📂 Histórico":
    st.header("Relatórios Salvos")
    if not st.session_state.db_historico: st.info("Vazio.")
    else:
        for i, rel in enumerate(st.session_state.db_historico):
            with st.expander(f"{rel['data']} | {rel.get('empresa_a','Multi')} vs {rel.get('empresa_b','Multi')}"):
                if 'analise_ia' in rel: st.markdown(rel['analise_ia'])
                else: st.write("Dados complexos (ver no painel)")
                if st.button("Excluir", key=f"d{i}"):
                    st.session_state.db_historico.pop(i)
                    bk.salvar_dados(bk.DB_HISTORICO, st.session_state.db_historico)
                    st.rerun()
