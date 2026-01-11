import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime
import backend as bk 

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Monitor Corp V27", page_icon="🏢", layout="wide")

# --- CSS PROFISSIONAL & MATRIZ ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    
    /* CARDS HOME */
    .tutorial-step {
        display: flex; align-items: flex-start; margin-bottom: 20px;
        background: rgba(255,255,255,0.02); padding: 20px; border-radius: 12px;
        border-left: 5px solid #2962FF; transition: all 0.3s ease;
    }
    .step-number {
        background-color: #2962FF; color: white; width: 40px; height: 40px;
        border-radius: 50%; text-align: center; line-height: 40px; font-weight: bold; font-size: 18px; margin-right: 20px; flex-shrink: 0;
    }
    
    /* MATRIZ DE COMPARAÇÃO */
    .matrix-table { width: 100%; border-collapse: separate; border-spacing: 4px; margin-top: 20px; }
    .matrix-header { padding: 15px; border-radius: 8px; color: white; font-weight: bold; text-align: center; font-size: 14px; }
    .matrix-row-label { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; font-weight: 600; color: #ddd; }
    .matrix-cell { background: rgba(255,255,255,0.02); padding: 10px; border-radius: 8px; text-align: center; font-size: 24px; border: 1px solid rgba(255,255,255,0.05); }
    .winner-cell { background: rgba(46, 204, 113, 0.15); border: 1px solid #2ecc71; }
    
    /* CORES DINÂMICAS PARA EMPRESAS */
    .color-0 { background-color: #2962FF; } /* Azul */
    .color-1 { background-color: #FF5252; } /* Vermelho */
    .color-2 { background-color: #FFA726; } /* Laranja */
    .color-3 { background-color: #66BB6A; } /* Verde */
    .color-4 { background-color: #AB47BC; } /* Roxo */

    /* BOTÕES */
    div.stButton > button[kind="primary"] { background-color: #2962FF; color: white; border: none; height: 50px; }
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

# --- FUNÇÕES VISUAIS ---
def render_grafico_1v1(df_a, df_b):
    fig = go.Figure()
    stars_a = df_a['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    stars_b = df_b['stars'].value_counts().reindex(range(1, 6), fill_value=0)
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_a.index], x=stars_a.values, name="Você", orientation='h', marker_color='#2962FF', text=stars_a.values, textposition='auto'))
    fig.add_trace(go.Bar(y=[f"{i} ⭐" for i in stars_b.index], x=stars_b.values, name="Rival", orientation='h', marker_color='#FF5252', text=stars_b.values, textposition='auto'))
    fig.update_layout(title="Volume de Avaliações", barmode='group', height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#888'), margin=dict(l=20,r=20,t=40,b=20))
    st.plotly_chart(fig, use_container_width=True)

def render_matriz_comparativa(resultado_json, nomes_empresas):
    """
    Renderiza a tabela HTML estilo 'Imagem de Referência'
    """
    categorias = [
        "Qualidade do Produto", 
        "Atendimento ao Cliente", 
        "Rapidez/Entrega", 
        "Custo-Benefício", 
        "Ambiente/Apresentação"
    ]
    
    # Header da Tabela
    html = '<table class="matrix-table"><tr><td class="matrix-header" style="background:transparent"></td>'
    for i, nome in enumerate(nomes_empresas):
        # Limita nome para não quebrar layout
        nome_curto = nome[:15] + "..." if len(nome) > 15 else nome
        html += f'<td class="matrix-header color-{i % 5}">{nome_curto}</td>'
    html += '</tr>'
    
    # Linhas da Tabela
    vencedores = resultado_json.get("vencedores", {})
    
    for cat in categorias:
        html += f'<tr><td class="matrix-row-label">{cat}</td>'
        vencedor_nome = vencedores.get(cat, "")
        
        for nome in nomes_empresas:
            # Verifica se essa empresa é a vencedora (Match de string parcial para segurança)
            is_winner = nome in vencedor_nome or vencedor_nome in nome
            
            if is_winner:
                html += '<td class="matrix-cell winner-cell">✅</td>'
            else:
                html += '<td class="matrix-cell"></td>'
        html += '</tr>'
        
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)
    
    # Resumo
    st.markdown("### 📝 Resumo do Analista")
    with st.container(border=True):
        st.info(resultado_json.get("resumo", "Sem resumo disponível."))

# ==========================================
# 1. HOME
# ==========================================
if menu == "🏠 Início":
    st.title("Bem-vindo ao Monitor Corporativo")
    st.markdown("---")
    st.subheader("📘 Guia Passo a Passo")
    st.markdown("""
    <div class="tutorial-step"><div class="step-number">1</div><div class="step-content"><h4>Configure sua Empresa</h4><p>Acesse o menu lateral <b>"Minha Empresa"</b> e defina seu negócio.</p></div></div>
    <div class="tutorial-step"><div class="step-number">2</div><div class="step-content"><h4>Cadastre Concorrentes</h4><p>Vá até <b>"Concorrentes"</b>. Você pode adicionar múltiplos rivais para comparação.</p></div></div>
    <div class="tutorial-step"><div class="step-number">3</div><div class="step-content"><h4>Gere Inteligência</h4><p>No <b>"Painel de Análise"</b>, selecione quem você quer enfrentar. Se escolher vários, geramos uma matriz.</p></div></div>
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
                
                # Coleta Opções
                opts_minha = []
                if st.session_state.db_empresas.get("minha_empresa"): opts_minha.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
                
                opts_rivais = []
                for c in st.session_state.db_empresas.get("concorrentes", []): opts_rivais.append(f"🔎 {c['title']}")
                
                # SELEÇÃO INTELIGENTE
                st.markdown("**Selecione os participantes:**")
                sel_a = st.selectbox("Sua Empresa (Base)", opts_minha if opts_minha else ["Configure sua empresa primeiro"])
                # Multiselect para Rivais
                sel_rivais = st.multiselect("Concorrentes (Selecione 1 ou mais)", opts_rivais)
                
                submit = st.form_submit_button("🚀 INICIAR ANÁLISE")
                
                if submit:
                    if not sel_rivais or "Configure" in sel_a:
                        st.error("Selecione sua empresa e pelo menos 1 concorrente.")
                    else:
                        # Helper para buscar objeto
                        def get_obj(txt):
                            if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
                            nome = txt.replace("🔎 ", "")
                            for c in st.session_state.db_empresas.get("concorrentes", []):
                                if c['title'] == nome: return c
                            return None

                        # Lista de Empresas para Analisar
                        empresas_alvo = [get_obj(sel_a)]
                        for r in sel_rivais: empresas_alvo.append(get_obj(r))
                        
                        with st.spinner(f"Analisando {len(empresas_alvo)} empresas..."):
                            # Coleta de Dados em Loop
                            dados_coletados = {} # {Nome: Texto}
                            dfs_coletados = {} # {Nome: DataFrame}
                            
                            for emp in empresas_alvo:
                                if emp:
                                    raw = bk.baixar_reviews(emp['url'], 150)
                                    if raw:
                                        df = pd.DataFrame(raw.get('reviews', []))
                                        if not df.empty and 'publishAt' in df.columns:
                                            df['data_obj'] = df['publishAt'].apply(bk.tratar_data_google)
                                            df.dropna(subset=['data_obj'], inplace=True)
                                            df['data'] = df['data_obj'].dt.date
                                            # Filtro Data
                                            df = df[(df['data'] >= dt_ini) & (df['data'] <= dt_fim)].head(qtd)
                                            
                                            # Salva texto para IA
                                            texto_reviews = "\n".join([f"({r['stars']}★) {r['text']}" for i, r in df.iterrows() if r['text']])
                                            dados_coletados[emp['title']] = texto_reviews
                                            dfs_coletados[emp['title']] = df
                            
                            if len(dados_coletados) >= 2:
                                # DECISÃO DO MODO DE EXIBIÇÃO
                                modo = "1v1" if len(dados_coletados) == 2 else "multi"
                                
                                resultado_ia = None
                                if modo == "1v1":
                                    nomes = list(dados_coletados.keys())
                                    resultado_ia = bk.gerar_analise_ia_detalhada(dados_coletados[nomes[0]], dados_coletados[nomes[1]], nomes[0], nomes[1])
                                else:
                                    resultado_ia = bk.gerar_matriz_comparativa(dados_coletados)
                                
                                st.session_state.dados_analise = {
                                    "modo": modo,
                                    "resultado": resultado_ia,
                                    "dfs": dfs_coletados,
                                    "periodo": f"{dt_ini.strftime('%d/%m')} a {dt_fim.strftime('%d/%m')}"
                                }
                                st.rerun()
                            else:
                                st.error("Dados insuficientes para comparação no período selecionado.")

    # TELA DE RESULTADOS (HÍBRIDA)
    else:
        dados = st.session_state.dados_analise
        c_head1, c_head2 = st.columns([4, 1])
        with c_head1: st.title("Relatório de Mercado")
        with c_head2: 
            if st.button("🔄 Nova Pesquisa"):
                st.session_state.dados_analise = None
                st.rerun()
                
        st.caption(f"Período: {dados['periodo']}")
        
        # --- MODO 1: DETALHADO (1x1) ---
        if dados['modo'] == "1v1":
            nomes = list(dados['dfs'].keys())
            df_a = dados['dfs'][nomes[0]]
            df_b = dados['dfs'][nomes[1]]
            
            col_kpi1, col_kpi2 = st.columns(2)
            with col_kpi1: st.metric(nomes[0], f"{pd.to_numeric(df_a['stars']).mean():.2f} ⭐", f"{len(df_a)} reviews")
            with col_kpi2: st.metric(nomes[1], f"{pd.to_numeric(df_b['stars']).mean():.2f} ⭐", f"{len(df_b)} reviews")
            
            st.subheader("Indicadores")
            render_grafico_1v1(df_a, df_b)
            
            st.subheader("Análise Estratégica")
            with st.container(border=True):
                st.markdown(dados['resultado'])
                
        # --- MODO 2: MATRIZ DE BATALHA (MULTI) ---
        else:
            st.subheader("🏆 Matriz de Vencedores")
            st.markdown("Comparativo direto onde a IA determina quem é a referência em cada quesito.")
            
            nomes_ordenados = list(dados['dfs'].keys())
            render_matriz_comparativa(dados['resultado'], nomes_ordenados)
            
            st.subheader("📊 Médias Gerais")
            cols = st.columns(len(nomes_ordenados))
            for i, nome in enumerate(nomes_ordenados):
                df = dados['dfs'][nome]
                media = pd.to_numeric(df['stars']).mean()
                with cols[i]:
                    st.markdown(f"**{nome}**")
                    st.markdown(f"<h2 style='color:#ccc'>{media:.1f} ⭐</h2>", unsafe_allow_html=True)

# ==========================================
# 3. MINHA EMPRESA (IGUAL)
# ==========================================
elif menu == "🏢 Minha Empresa":
    st.header("Perfil da Empresa")
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
# 4. CONCORRENTES (IGUAL)
# ==========================================
elif menu == "🔎 Concorrentes":
    st.header("Gestão de Concorrentes")
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
                if 'analise_ia' in rel: st.markdown(rel['analise_ia']) # Legado
                else: st.write("Dados complexos (ver no painel)") # Novo formato multi
                if st.button("Excluir", key=f"d{i}"):
                    st.session_state.db_historico.pop(i)
                    bk.salvar_dados(bk.DB_HISTORICO, st.session_state.db_historico)
                    st.rerun()
