import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime
import backend as bk # <--- IMPORTANDO SEU CÉREBRO AQUI

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Monitor Corp Enterprise", page_icon="🏢", layout="wide")

# --- CSS PROFISSIONAL (DESIGN SYSTEM) ---
st.markdown("""
<style>
    /* RESET */
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }
    
    /* CARDS DA HOME */
    .action-card {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(128, 128, 128, 0.1);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        height: 100%;
        transition: all 0.3s ease;
    }
    .action-card:hover {
        border-color: #2962FF;
        transform: translateY(-3px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    .card-emoji { font-size: 40px; margin-bottom: 10px; display: block; }
    .card-title { font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 5px; }
    .card-text { font-size: 14px; color: #aaa; margin-bottom: 15px; }

    /* TUTORIAL STEPS */
    .tutorial-step {
        display: flex;
        align-items: flex-start;
        margin-bottom: 20px;
        background: rgba(255,255,255,0.02);
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #2962FF;
    }
    .step-number {
        background-color: #2962FF;
        color: white;
        width: 30px; height: 30px;
        border-radius: 50%;
        text-align: center;
        line-height: 30px;
        font-weight: bold;
        margin-right: 15px;
        flex-shrink: 0;
    }
    .step-content h4 { margin: 0 0 5px 0; font-size: 16px; color: #fff; }
    .step-content p { margin: 0; font-size: 14px; color: #aaa; }

    /* KPI BOXES */
    .kpi-box {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .kpi-val { font-size: 2.2rem; font-weight: 800; color: #fff; }
    .kpi-lbl { font-size: 0.9rem; text-transform: uppercase; color: #888; letter-spacing: 1px; }

    /* BOTÕES */
    div.stButton > button {
        width: 100%; border-radius: 8px; height: 50px; font-weight: 600;
    }
    div.stButton > button[kind="primary"] {
        background-color: #2962FF; color: white; border: none;
    }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO ---
if "db_empresas" not in st.session_state: st.session_state.db_empresas = bk.carregar_dados(bk.DB_EMPRESAS)
if "db_historico" not in st.session_state: st.session_state.db_historico = bk.carregar_dados(bk.DB_HISTORICO)
if "dados_analise" not in st.session_state: st.session_state.dados_analise = None

# --- SIDEBAR (NAVEGAÇÃO) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055646.png", width=60)
    st.title("Monitor Corp")
    st.markdown("---")
    
    menu = st.radio(
        "Menu Principal",
        ["🏠 Início", "📊 Painel de Análise", "🏢 Minha Empresa", "🔎 Concorrentes", "📂 Histórico"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    # Widget de Status da Empresa
    empresa_ativa = st.session_state.db_empresas.get("minha_empresa")
    if empresa_ativa:
        st.success(f"Ativo: **{empresa_ativa['title']}**")
    else:
        st.warning("⚠️ Empresa não configurada")

# ==========================================
# PÁGINA 1: HOME (TUTORIAL + ACESSO RÁPIDO)
# ==========================================
if menu == "🏠 Início":
    st.title("Bem-vindo ao Monitor Corporativo")
    st.markdown("Plataforma de inteligência competitiva baseada em dados públicos.")
    st.markdown("---")

    # Layout: 60% Tutorial (Esq) | 40% Ações (Dir)
    col_tut, col_actions = st.columns([1.5, 1], gap="large")

    with col_tut:
        st.subheader("📘 Guia Rápido")
        st.markdown("""
        <div class="tutorial-step">
            <div class="step-number">1</div>
            <div class="step-content">
                <h4>Configure sua Empresa</h4>
                <p>Acesse o menu "Minha Empresa" e defina o negócio principal que servirá de base para todas as comparações.</p>
            </div>
        </div>
        <div class="tutorial-step">
            <div class="step-number">2</div>
            <div class="step-content">
                <h4>Cadastre Concorrentes</h4>
                <p>No menu "Concorrentes", adicione as empresas rivais do seu setor ou região.</p>
            </div>
        </div>
        <div class="tutorial-step">
            <div class="step-number">3</div>
            <div class="step-content">
                <h4>Gere Inteligência</h4>
                <p>Vá para o "Painel de Análise", selecione o período e clique em Processar. A IA fará o resto.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_actions:
        st.subheader("⚡ Acesso Rápido")
        
        # Card 1
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1: st.markdown("📊", unsafe_allow_html=True)
            with c2: 
                st.markdown("**Nova Análise**")
                st.caption("Comparar performance agora.")
            if st.button("Ir para Dashboard", key="btn_dash"):
                st.switch_page("app.py") # Recarrega para simular navegação se necessario, ou instrui

        # Card 2
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1: st.markdown("🏢", unsafe_allow_html=True)
            with c2: 
                st.markdown("**Configurações**")
                st.caption("Gerenciar dados cadastrais.")
            if st.button("Ir para Empresa", key="btn_emp"):
                pass # Ação de navegação seria via session state se não usar radio

# ==========================================
# PÁGINA 2: DASHBOARD (ANÁLISE)
# ==========================================
elif menu == "📊 Painel de Análise":
    st.title("Painel de Inteligência")
    
    # Se não tem dados, mostra CONFIGURAÇÃO
    if st.session_state.dados_analise is None:
        with st.container(border=True):
            st.subheader("Definição de Parâmetros")
            
            with st.form("form_analise"):
                c1, c2, c3 = st.columns(3)
                dt_ini = c1.date_input("Início", date.today().replace(day=1))
                dt_fim = c2.date_input("Fim", date.today())
                qtd = c3.slider("Amostra de Reviews", 10, 100, 30)
                
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
                        # Recupera objetos reais
                        def get_obj(txt):
                            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
                            nome = txt.replace("🔎 ", "")
                            for c in st.session_state.db_empresas.get("concorrentes", []):
                                if c['title'] == nome: return c
                            return None
                        
                        obj_a = get_obj(sel_a)
                        obj_b = get_obj(sel_b)
                        
                        with st.spinner("Processando dados de mercado..."):
                            # BACKEND CALL
                            raw_a = bk.baixar_reviews(obj_a['url'], 150)
                            raw_b = bk.baixar_reviews(obj_b['url'], 150)
                            
                            if raw_a and raw_b:
                                df_a = pd.DataFrame(raw_a.get('reviews', []))
                                df_b = pd.DataFrame(raw_b.get('reviews', []))
                                
                                # Processamento
                                for df in [df_a, df_b]:
                                    if not df.empty and 'publishAt' in df.columns:
                                        df['data_obj'] = df['publishAt'].apply(bk.tratar_data_google)
                                        df.dropna(subset=['data_obj'], inplace=True)
                                        df['data'] = df['data_obj'].dt.date
                                        df['stars'] = pd.to_numeric(df['stars'])
                                
                                # Filtros
                                df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)].head(qtd)
                                df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)].head(qtd)
                                
                                if not df_a.empty and not df_b.empty:
                                    # Preparar texto IA
                                    txt_a = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_a.iterrows() if r['text']])
                                    txt_b = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df_b.iterrows() if r['text']])
                                    
                                    analise = bk.gerar_analise_ia(txt_a, txt_b, obj_a['title'], obj_b['title'])
                                    
                                    # Salvar Sessão
                                    st.session_state.dados_analise = {
                                        "df_a": df_a, "df_b": df_b, "analise": analise,
                                        "nome_a": obj_a['title'], "nome_b": obj_b['title'],
                                        "periodo": f"{dt_ini.strftime('%d/%m')} a {dt_fim.strftime('%d/%m')}"
                                    }
                                    
                                    # Salvar Histórico
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

    # Se tem dados, mostra RESULTADOS
    else:
        dados = st.session_state.dados_analise
        
        # Header com Botão Voltar
        c1, c2 = st.columns([4, 1])
        with c1: st.caption(f"Período: {dados['periodo']}")
        with c2: 
            if st.button("🔄 Nova Pesquisa"):
                st.session_state.dados_analise = None
                st.rerun()
        
        # KPIs
        nota_a = dados['df_a']['stars'].mean()
        nota_b = dados['df_b']['stars'].mean()
        gap = nota_a - nota_b
        
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        with col_kpi1:
            st.markdown(f"""
            <div class="kpi-box">
                <div class="kpi-lbl" style="color:#2962FF">SUA EMPRESA</div>
                <div class="kpi-val">{nota_a:.2f}</div>
                <div class="kpi-lbl">{len(dados['df_a'])} avaliações</div>
            </div>""", unsafe_allow_html=True)
        
        with col_kpi2:
            cor = "#4CAF50" if gap > 0 else "#FF5252"
            sinal = "+" if gap > 0 else ""
            st.markdown(f"""
            <div class="kpi-box" style="border: 1px solid {cor}">
                <div class="kpi-lbl" style="color:{cor}">GAP COMPETITIVO</div>
                <div class="kpi-val" style="color:{cor}">{sinal}{gap:.2f}</div>
                <div class="kpi-lbl">Pontos de diferença</div>
            </div>""", unsafe_allow_html=True)

        with col_kpi3:
            st.markdown(f"""
            <div class="kpi-box">
                <div class="kpi-lbl" style="color:#546E7A">CONCORRENTE</div>
                <div class="kpi-val">{nota_b:.2f}</div>
                <div class="kpi-lbl">{len(dados['df_b'])} avaliações</div>
            </div>""", unsafe_allow_html=True)
            
        # Abas de Conteúdo
        st.markdown("###")
        tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "📑 Relatório IA", "🔎 Dados Brutos"])
        
        with tab1:
            # Tenta extrair tags do texto da IA
            try:
                tags = dados['analise'].split("### 🏆")[0]
                with st.container(border=True): st.markdown(tags)
            except: pass
            
            # Gráfico
            fig = go.Figure()
            stars_a = dados['df_a']['stars'].value_counts().reindex(range(1, 6), fill_value=0)
            stars_b = dados['df_b']['stars'].value_counts().reindex(range(1, 6), fill_value=0)
            
            fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_a.index], x=stars_a.values, name="Você", orientation='h', marker_color='#2962FF'))
            fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_b.index], x=stars_b.values, name="Rival", orientation='h', marker_color='#546E7A'))
            
            fig.update_layout(title="Distribuição de Notas", barmode='group', height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#888'))
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            with st.container(border=True):
                st.markdown(dados['analise'])
                
        with tab3:
            c1, c2 = st.columns(2)
            c1.dataframe(dados['df_a'][['stars', 'text', 'data']], use_container_width=True)
            c2.dataframe(dados['df_b'][['stars', 'text', 'data']], use_container_width=True)

# ==========================================
# PÁGINA 3: CONFIGURAÇÃO DE EMPRESA
# ==========================================
elif menu == "🏢 Minha Empresa":
    st.title("Perfil da Empresa")
    
    dados = st.session_state.db_empresas.get("minha_empresa")
    if dados:
        with st.container(border=True):
            st.info(f"Empresa Atual: **{dados['title']}**")
            st.caption(dados.get('address',''))
            if st.button("Remover e Cadastrar Outra"):
                del st.session_state.db_empresas["minha_empresa"]
                bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()
    else:
        with st.form("form_minha"):
            c1, c2 = st.columns(2)
            uf = c1.selectbox("UF", bk.get_ibge_locais("estados"), index=25)
            city = c1.selectbox("Cidade", bk.get_ibge_locais("cidades", uf))
            nome = st.text_input("Nome")
            
            if st.form_submit_button("🔍 Buscar"):
                res = bk.buscar_locais(f"{nome}, {city} - {uf}")
                if res: st.session_state.temp_minha = res
                else: st.error("Não encontrado.")
        
        if "temp_minha" in st.session_state:
            with st.form("save_minha"):
                opts = {f"{x['title']}": x for x in st.session_state.temp_minha}
                esc = st.radio("Selecione:", list(opts.keys()))
                if st.form_submit_button("💾 Salvar"):
                    st.session_state.db_empresas["minha_empresa"] = opts[esc]
                    bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                    del st.session_state.temp_minha
                    st.rerun()

# ==========================================
# PÁGINA 4: CONCORRENTES
# ==========================================
elif menu == "🔎 Concorrentes":
    st.title("Gestão de Concorrentes")
    
    conc = st.session_state.db_empresas.get("concorrentes", [])
    if conc:
        with st.container(border=True):
            st.dataframe(pd.DataFrame(conc)[['title', 'address']], use_container_width=True)
            with st.form("del_conc"):
                sel = st.selectbox("Remover:", [c['title'] for c in conc])
                if st.form_submit_button("Apagar"):
                    st.session_state.db_empresas["concorrentes"] = [c for c in conc if c['title'] != sel]
                    bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                    st.rerun()
    
    st.subheader("Adicionar Novo")
    with st.form("form_rival"):
        c1, c2 = st.columns(2)
        uf = c1.selectbox("UF", bk.get_ibge_locais("estados"), index=25, key='ufr')
        city = c1.selectbox("Cidade", bk.get_ibge_locais("cidades", uf), key='cr')
        nome = st.text_input("Nome Rival")
        if st.form_submit_button("🔍 Buscar"):
            res = bk.buscar_locais(f"{nome}, {city} - {uf}")
            if res: st.session_state.temp_rival = res
    
    if "temp_rival" in st.session_state:
        with st.form("save_rival"):
            opts = {f"{x['title']}": x for x in st.session_state.temp_rival}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.form_submit_button("💾 Adicionar"):
                if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
                st.session_state.db_empresas["concorrentes"].append(opts[esc])
                bk.salvar_dados(bk.DB_EMPRESAS, st.session_state.db_empresas)
                del st.session_state.temp_rival
                st.rerun()

# ==========================================
# PÁGINA 5: HISTÓRICO
# ==========================================
elif menu == "📂 Histórico":
    st.title("Arquivo de Relatórios")
    
    if not st.session_state.db_historico:
        st.info("Nenhum relatório salvo.")
    else:
        for i, rel in enumerate(st.session_state.db_historico):
            with st.expander(f"{rel['data']} | {rel['empresa_a']} vs {rel['empresa_b']}"):
                c1, c2 = st.columns(2)
                c1.metric("Você", f"{rel['nota_a']:.2f}")
                c2.metric("Rival", f"{rel['nota_b']:.2f}")
                st.markdown(rel['analise_ia'])
                if st.button("Excluir", key=f"del_{i}"):
                    st.session_state.db_historico.pop(i)
                    bk.salvar_dados(bk.DB_HISTORICO, st.session_state.db_historico)
                    st.rerun()
