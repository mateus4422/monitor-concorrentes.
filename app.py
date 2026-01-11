# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
# IMPORTA A LÓGICA DO ARQUIVO SEPARADO
import backend as bk 

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Monitor Corp V25", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# --- CSS PROFISSIONAL (DARK/LIGHT MODE ADAPTIVE) ---
st.markdown("""
<style>
    /* Remover padding excessivo do topo */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* CARTÕES DA HOME */
    .home-card {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: transform 0.2s;
        height: 100%;
    }
    .home-card:hover {
        border-color: #2962FF;
        background-color: rgba(41, 98, 255, 0.05);
        transform: translateY(-2px);
    }
    .card-icon { font-size: 40px; margin-bottom: 10px; display: block; }
    .card-title { font-size: 18px; font-weight: bold; color: #2962FF; margin-bottom: 5px; }
    .card-desc { font-size: 14px; color: #888; }
    
    /* KPI BOXES */
    .kpi-container {
        display: flex; justify-content: space-between; align-items: center;
        background-color: rgba(255,255,255,0.03); padding: 20px; border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.2); margin-bottom: 20px;
    }
    .kpi-val { font-size: 2.5rem; font-weight: 700; }
    .kpi-lbl { font-size: 0.9rem; text-transform: uppercase; color: #888; }
    
    /* Botões */
    div.stButton > button { width: 100%; border-radius: 8px; font-weight: 600; }
    div.stButton > button[kind="primary"] { background-color: #2962FF; border: none; }
</style>
""", unsafe_allow_html=True)

# --- ESTADO DA SESSÃO ---
if "db_empresas" not in st.session_state: st.session_state.db_empresas = bk.carregar_json(bk.DB_EMPRESAS)
if "db_historico" not in st.session_state: st.session_state.db_historico = bk.carregar_json(bk.DB_HISTORICO)
if "dados_analise_atual" not in st.session_state: st.session_state.dados_analise_atual = None

# --- SIDEBAR (MENU LATERAL) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055646.png", width=50)
    st.title("Monitor Corp")
    st.markdown("---")
    
    # Navegação usando Radio Button que parece Menu
    menu_selecionado = st.radio(
        "Navegação", 
        ["🏠 Início", "📊 Dashboard (Análise)", "🏢 Minha Empresa", "🔎 Concorrentes", "📂 Relatórios"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.caption("v25.0 Enterprise")
    
    # Status da Empresa
    dados_empresa = st.session_state.db_empresas.get("minha_empresa")
    if dados_empresa:
        st.success(f"Logado como:\n**{dados_empresa['title']}**")
    else:
        st.warning("Empresa não configurada")

# --- FUNÇÃO DE GRÁFICO (FRONTEND) ---
def render_grafico_comparativo(df_a, df_b):
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_a.index], x=stars_a.values, name="Sua Empresa", orientation='h', marker_color='#2962FF', text=stars_a.values, textposition='auto'))
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_b.index], x=stars_b.values, name="Concorrente", orientation='h', marker_color='#546E7A', text=stars_b.values, textposition='auto'))

    fig.update_layout(
        title="Volume de Avaliações", barmode='group', height=300,
        margin=dict(l=20, r=20, t=40, b=20), xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#888'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# PÁGINAS DO SISTEMA
# ==========================================

# 1. HOME (DASHBOARD INICIAL)
if menu_selecionado == "🏠 Início":
    st.title("Central de Comando")
    st.markdown("Bem-vindo ao sistema de inteligência competitiva.")
    
    st.markdown("### Acesso Rápido")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""
        <div class="home-card">
            <span class="card-icon">⚡</span>
            <div class="card-title">Nova Análise</div>
            <div class="card-desc">Comparar desempenho com concorrentes agora.</div>
        </div>
        """, unsafe_allow_html=True)
        # O botão do Streamlit é transparente e fica "em cima" do card visualmente
        if st.button("Ir para Análise", key="btn_home_analise"): 
            # Hack para mudar o radio button não é simples no Streamlit puro, 
            # então apenas mostramos uma mensagem ou instrução
            st.info("Clique em '📊 Dashboard' no menu lateral.")

    with c2:
        st.markdown("""
        <div class="home-card">
            <span class="card-icon">🏢</span>
            <div class="card-title">Configurações</div>
            <div class="card-desc">Gerenciar dados da sua empresa e filiais.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Configurar Empresa", key="btn_home_conf"): 
            st.info("Clique em '🏢 Minha Empresa' no menu lateral.")

    with c3:
        qtd_reports = len(st.session_state.db_historico)
        st.markdown(f"""
        <div class="home-card">
            <span class="card-icon">📂</span>
            <div class="card-title">Histórico</div>
            <div class="card-desc">Você possui <b>{qtd_reports}</b> relatórios salvos.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ver Relatórios", key="btn_home_hist"):
             st.info("Clique em '📂 Relatórios' no menu lateral.")

# 2. DASHBOARD DE ANÁLISE
elif menu_selecionado == "📊 Dashboard (Análise)":
    st.title("Análise de Mercado")
    
    # Se não tem análise rodada, mostra FORMULÁRIO
    if st.session_state.dados_analise_atual is None:
        with st.container(border=True):
            st.subheader("Parâmetros da Pesquisa")
            with st.form("form_analise"):
                c1, c2, c3 = st.columns(3)
                dt_ini = c1.date_input("Início", date.today().replace(day=1))
                dt_fim = c2.date_input("Fim", date.today())
                qtd_limite = c3.slider("Amostra", 10, 100, 30)
                
                opts_a = []
                if st.session_state.db_empresas.get("minha_empresa"): opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
                for c in st.session_state.db_empresas.get("concorrentes", []): opts_a.append(f"🔎 {c['title']}")
                
                c_sel1, c_sel2 = st.columns(2)
                sel_a = c_sel1.selectbox("Empresa Principal", opts_a)
                opcoes_b = [x for x in opts_a if x != sel_a]
                sel_b = c_sel2.selectbox("Concorrente", opcoes_b if opcoes_b else ["Cadastre um rival primeiro"])
                
                submitted = st.form_submit_button("🚀 PROCESSAR INTELIGÊNCIA ARTIFICIAL")
                
                if submitted:
                    if not opcoes_b: st.error("Cadastre concorrentes no menu lateral.")
                    else:
                        def get_obj(txt):
                            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
                            nome = txt.replace("🔎 ", "")
                            for c in st.session_state.db_empresas.get("concorrentes", []):
                                if c['title'] == nome: return c
                            return None

                        obj_a = get_obj(sel_a)
                        obj_b = get_obj(sel_b)
                        
                        if obj_a and obj_b:
                            with st.spinner("Conectando satélites e processando dados..."):
                                raw_a = bk.baixar_reviews_apify(obj_a['url'], 150)
                                raw_b = bk.baixar_reviews_apify(obj_b['url'], 150)
                                
                                if raw_a and raw_b:
                                    df_a = pd.DataFrame(raw_a.get('reviews', []))
                                    df_b = pd.DataFrame(raw_b.get('reviews', []))
                                    
                                    for df in [df_a, df_b]:
                                        if not df.empty and 'publishAt' in df.columns:
                                            df['data_obj'] = df['publishAt'].apply(bk.tratar_data_google)
                                            df.dropna(subset=['data_obj'], inplace=True)
                                            df['data'] = df['data_obj'].dt.date
                                            df['stars'] = pd.to_numeric(df['stars'])
                                    
                                    df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)].head(qtd_limite)
                                    df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)].head(qtd_limite)
                                    
                                    if not df_a.empty and not df_b.empty:
                                        txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                                        txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                                        
                                        analise = bk.analisar_ia_corporativa(txt_a, txt_b, obj_a['title'], obj_b['title'])
                                        
                                        st.session_state.dados_analise_atual = {
                                            "df_a": df_a, "df_b": df_b, "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                            "analise": analise, "periodo": f"{dt_ini.strftime('%d/%m')} a {dt_fim.strftime('%d/%m')}"
                                        }
                                        # Salvar histórico
                                        rel = {
                                            "data_geracao": datetime.now().strftime("%d/%m %H:%M"),
                                            "empresa_a": obj_a['title'], "empresa_b": obj_b['title'],
                                            "nota_a_corte": float(df_a['stars'].mean()), "nota_b_corte": float(df_b['stars'].mean()),
                                            "analise_ia": analise
                                        }
                                        st.session_state.db_historico.insert(0, rel)
                                        bk.salvar_json(bk.DB_HISTORICO, st.session_state.db_historico)
                                        st.rerun()
                                    else: st.warning("Dados insuficientes no período.")
    
    # Se JÁ tem análise, mostra RESULTADOS
    else:
        dados = st.session_state.dados_analise_atual
        c_tit, c_btn = st.columns([4, 1])
        with c_btn: 
            if st.button("🔄 Nova Busca"): 
                st.session_state.dados_analise_atual = None
                st.rerun()
        
        # PLACAR (KPI)
        nota_a = dados['df_a']['stars'].mean()
        nota_b = dados['df_b']['stars'].mean()
        gap = nota_a - nota_b
        
        st.markdown(f"""
        <div class="kpi-container">
            <div style="text-align:center;">
                <div class="kpi-lbl" style="color:#2962FF">VOCÊ</div>
                <div class="kpi-val" style="color:#2962FF">{nota_a:.2f}</div>
            </div>
            <div style="font-size:1.5rem; font-weight:bold; color:#888;">VS</div>
            <div style="text-align:center;">
                <div class="kpi-lbl" style="color:#546E7A">RIVAL</div>
                <div class="kpi-val" style="color:#546E7A">{nota_b:.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if gap > 0: st.success(f"📈 Liderança: Você está **{gap:+.2f}** pontos à frente.")
        elif gap < 0: st.error(f"📉 Alerta: Você está **{gap:+.2f}** pontos atrás.")
        
        # Conteúdo
        t_dash, t_rel = st.tabs(["📊 Gráficos & Tags", "📑 Relatório Completo"])
        
        with t_dash:
            try:
                tags = dados['analise'].split("### 🏆")[0]
                with st.container(border=True): st.markdown(tags)
            except: pass
            render_grafico_comparativo(dados['df_a'], dados['df_b'])
            
        with t_rel:
            with st.container(border=True):
                st.markdown(dados['analise'])
            st.dataframe(dados['df_a'][['stars','text','data']])

# 3. MINHA EMPRESA
elif menu_selecionado == "🏢 Minha Empresa":
    st.header("Configuração da Empresa")
    dados = st.session_state.db_empresas.get("minha_empresa")
    
    if dados:
        with st.container(border=True):
            st.success(f"Ativa: **{dados['title']}**")
            st.caption(dados.get('address',''))
            if st.button("Remover Empresa"):
                del st.session_state.db_empresas["minha_empresa"]
                bk.salvar_json(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()
    else:
        with st.form("form_minha_empresa"):
            st.subheader("Cadastrar Nova")
            c1, c2 = st.columns(2)
            uf = c1.selectbox("UF", bk.get_ibge("estados"), index=25)
            city = c1.selectbox("Cidade", bk.get_ibge("cidades", uf))
            nome = st.text_input("Nome da Empresa")
            if st.form_submit_button("Buscar"):
                res = bk.buscar_locais_apify(f"{nome}, {city} - {uf}")
                if res: st.session_state.busca_minha = res
        
        if "busca_minha" in st.session_state:
            with st.form("confirma_minha"):
                opts = {f"{x['title']}": x for x in st.session_state.busca_minha}
                esc = st.radio("Selecione:", list(opts.keys()))
                if st.form_submit_button("Salvar"):
                    st.session_state.db_empresas["minha_empresa"] = opts[esc]
                    bk.salvar_json(bk.DB_EMPRESAS, st.session_state.db_empresas)
                    st.rerun()

# 4. CONCORRENTES
elif menu_selecionado == "🔎 Concorrentes":
    st.header("Gestão de Concorrentes")
    conc = st.session_state.db_empresas.get("concorrentes", [])
    
    if conc:
        st.dataframe(pd.DataFrame(conc)[['title','address']], use_container_width=True)
        with st.form("del_conc"):
            to_del = st.selectbox("Remover:", [c['title'] for c in conc])
            if st.form_submit_button("Apagar"):
                st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != to_del]
                bk.salvar_json(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()
    
    st.divider()
    with st.form("add_conc"):
        st.subheader("Adicionar Novo")
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", bk.get_ibge("estados"), index=25, key='uf2')
        city = c1.selectbox("Cidade", bk.get_ibge("cidades", uf), key='cid2')
        nome = st.text_input("Nome Rival")
        if st.form_submit_button("Buscar"):
            res = bk.buscar_locais_apify(f"{nome}, {city} - {uf}")
            if res: st.session_state.busca_rival = res
            
    if "busca_rival" in st.session_state:
        with st.form("confirma_rival"):
            opts = {f"{x['title']}": x for x in st.session_state.busca_rival}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.form_submit_button("Adicionar"):
                if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
                st.session_state.db_empresas["concorrentes"].append(opts[esc])
                bk.salvar_json(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

# 5. HISTÓRICO
elif menu_selecionado == "📂 Relatórios":
    st.header("Arquivo de Relatórios")
    if not st.session_state.db_historico: st.info("Nenhum relatório salvo.")
    else:
        opcoes = [f"{r['data_geracao']} | {r['empresa_a']} vs {r['empresa_b']}" for r in st.session_state.db_historico]
        escolha = st.selectbox("Selecione:", opcoes)
        idx = opcoes.index(escolha)
        rel = st.session_state.db_historico[idx]
        
        with st.container(border=True):
            st.markdown(rel['analise_ia'])
            if st.button("Excluir Registro"):
                st.session_state.db_historico.pop(idx)
                bk.salvar_json(bk.DB_HISTORICO, st.session_state.db_historico)
                st.rerun()
