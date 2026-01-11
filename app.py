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
MY_APIFY_TOKEN = "apify_api_yRzwwIYgcwqLjvf2aL0yWnyjss54F00ym2nK"
MY_GEMINI_KEY = "AIzaSyBqEgzqsdvo-zMcVwjMLxM3H7ZAZJ4LosM"
# ==========================================

st.set_page_config(page_title="Monitor Corp V12", page_icon="🏢", layout="wide")

# --- DATABASE LOCAL ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"


def carregar_json(arquivo):
    if not os.path.exists(arquivo): return {} if arquivo == DB_EMPRESAS else []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {} if arquivo == DB_EMPRESAS else []


def salvar_json(arquivo, dados):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False, default=str)


if "db_empresas" not in st.session_state: st.session_state.db_empresas = carregar_json(DB_EMPRESAS)
if "db_historico" not in st.session_state: st.session_state.db_historico = carregar_json(DB_HISTORICO)


# --- TRATAMENTO DE DATAS ---
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
            if "mês" in texto or "mes" in texto: return agora - timedelta(days=val * 30)
            if "ano" in texto: return agora - timedelta(days=val * 365)
        except:
            pass
    try:
        return pd.to_datetime(texto)
    except:
        return pd.NaT


# --- APIFY ---
def buscar_locais_apify(termo):
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [termo], "maxCrawledPlacesPerSearch": 5, "language": "pt-BR", "maxReviews": 0
        })
        return client.dataset(run['defaultDatasetId']).list_items().items
    except:
        return []


def baixar_reviews_apify(url, max_reviews=150, sort_order="newest"):
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "startUrls": [{"url": url}], "language": "pt-BR", "maxReviews": max_reviews, "reviewsSort": sort_order
        })
        items = client.dataset(run['defaultDatasetId']).list_items().items
        return items[0] if items else None
    except:
        return None


# --- GEMINI IA ---
def configurar_gemini():
    if not MY_GEMINI_KEY: return None
    genai.configure(api_key=MY_GEMINI_KEY)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                return genai.GenerativeModel(m.name)
    except:
        pass
    return genai.GenerativeModel('gemini-pro')


model = configurar_gemini()


def analisar_ia(texto_a, texto_b, nome_a, nome_b, criterio):
    prompt = f"""
    Contexto: Análise comparativa. Foco: {criterio}.

    EMPRESA A ({nome_a}):
    {texto_a[:3500]}

    EMPRESA B ({nome_b}):
    {texto_b[:3500]}

    Gere um relatório Executivo (Markdown):
    ### 🎯 Diagnóstico ({criterio})
    (Compare o desempenho)
    ### ⚠️ Pontos de Atenção
    (Problemas citados)
    ### 💎 Pontos Fortes
    (Elogios citados)
    ### 🚀 Plano de Ação
    (Sugestão prática)
    """
    try:
        return model.generate_content(prompt).text
    except:
        return "Erro na IA."


# --- UTIL ---
@st.cache_data(ttl=3600)
def get_ibge(tipo, uf=None):
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
        if tipo == "cidades": url += f"/{uf}/municipios"
        r = requests.get(url)
        return sorted([x['sigla' if tipo == 'estados' else 'nome'] for x in r.json()])
    except:
        return []


# ==========================================
# INTERFACE
# ==========================================
with st.sidebar:
    st.title("🏢 Monitor V12")
    menu = st.radio("Menu", ["🏠 Minha Empresa", "🥊 Meus Concorrentes", "⚡ Análise Avançada", "📂 Relatórios Completos"])

# ---------------------------------------------------------
# 1. MINHA EMPRESA
# ---------------------------------------------------------
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
        c1, c2, c3 = st.columns([1, 2, 2])
        uf = c1.selectbox("UF", get_ibge("estados"), index=25)
        city = c2.selectbox("Cidade", get_ibge("cidades", uf))
        nome = c3.text_input("Nome")
        if st.button("Buscar"):
            res = buscar_locais_apify(f"{nome}, {city} - {uf}")
            if res: st.session_state.busca_minha = res
        if "busca_minha" in st.session_state:
            opts = {f"{x['title']} ({x.get('address', '')})": x for x in st.session_state.busca_minha}
            esc = st.radio("Selecione:", list(opts.keys()))
            if st.button("Salvar"):
                st.session_state.db_empresas["minha_empresa"] = opts[esc]
                salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
                st.rerun()

# ---------------------------------------------------------
# 2. CONCORRENTES
# ---------------------------------------------------------
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
    c1, c2, c3 = st.columns([1, 2, 2])
    uf = c1.selectbox("UF", get_ibge("estados"), index=25, key='ufr')
    city = c2.selectbox("Cidade", get_ibge("cidades", uf), key='cidr')
    nome = c3.text_input("Nome Rival")
    if st.button("Buscar Rival"):
        res = buscar_locais_apify(f"{nome}, {city} - {uf}")
        if res: st.session_state.busca_rival = res
    if "busca_rival" in st.session_state:
        opts = {f"{x['title']} ({x.get('address', '')})": x for x in st.session_state.busca_rival}
        esc = st.radio("Selecione:", list(opts.keys()), key='rr')
        if st.button("Salvar Rival"):
            if "concorrentes" not in st.session_state.db_empresas: st.session_state.db_empresas["concorrentes"] = []
            st.session_state.db_empresas["concorrentes"].append(opts[esc])
            salvar_json(DB_EMPRESAS, st.session_state.db_empresas)
            st.rerun()

# ---------------------------------------------------------
# 3. ANÁLISE AVANÇADA
# ---------------------------------------------------------
elif menu == "⚡ Análise Avançada":
    st.header("⚡ Central de Inteligência")

    col_datas, col_filtros = st.columns([1, 1.5])

    with col_datas:
        st.subheader("1. Período")
        dt_ini = st.date_input("Início", date.today().replace(day=1))
        dt_fim = st.date_input("Fim", date.today())

    with col_filtros:
        st.subheader("2. Filtros de Conteúdo")
        c_qtd, c_ordem = st.columns(2)
        qtd_limite = c_qtd.slider("Qtd. Reviews p/ Analisar", 5, 50, 15)

        # --- ADICIONADO OPÇÃO PADRÃO ---
        criterio = c_ordem.selectbox(
            "O que analisar?",
            ["Padrão (Sem Filtro)", "Mais Recentes", "Mais Relevantes", "Piores Notas (1-2★)", "Melhores Notas (5★)"]
        )

    st.markdown("---")
    st.subheader("3. Combatentes")
    c_a, c_b = st.columns(2)

    opts_a = []
    if st.session_state.db_empresas.get("minha_empresa"):
        opts_a.append(f"🏠 {st.session_state.db_empresas['minha_empresa']['title']}")
    for c in st.session_state.db_empresas.get("concorrentes", []):
        opts_a.append(f"🥊 {c['title']}")

    sel_a = c_a.selectbox("Lado A", opts_a)
    sel_b = c_b.selectbox("Lado B", [x for x in opts_a if x != sel_a])


    def get_obj(txt):
        if "🏠" in txt: return st.session_state.db_empresas["minha_empresa"]
        nome = txt.replace("🥊 ", "")
        for c in st.session_state.db_empresas.get("concorrentes", []):
            if c['title'] == nome: return c
        return None


    if st.button("🚀 EXECUTAR ANÁLISE", type="primary", use_container_width=True):
        obj_a = get_obj(sel_a)
        obj_b = get_obj(sel_b)

        if obj_a and obj_b:
            with st.spinner(f"Processando '{criterio}'..."):
                # Define ordenação API
                api_sort = "mostRelevant" if criterio == "Mais Relevantes" else "newest"
                raw_a = baixar_reviews_apify(obj_a['url'], 150, api_sort)
                raw_b = baixar_reviews_apify(obj_b['url'], 150, api_sort)

                if raw_a and raw_b:
                    df_a = pd.DataFrame(raw_a.get('reviews', []))
                    df_b = pd.DataFrame(raw_b.get('reviews', []))

                    # 1. Trata Data
                    for df in [df_a, df_b]:
                        if not df.empty and 'publishAt' in df.columns:
                            df['data_obj'] = df['publishAt'].apply(tratar_data_google)
                            df.dropna(subset=['data_obj'], inplace=True)
                            df['data'] = df['data_obj'].dt.date

                    # 2. Filtra Data
                    df_a = df_a[(df_a['data'] >= dt_ini) & (df_a['data'] <= dt_fim)]
                    df_b = df_b[(df_b['data'] >= dt_ini) & (df_b['data'] <= dt_fim)]

                    # 3. Filtra Critério (Localmente)
                    df_a['stars'] = pd.to_numeric(df_a['stars'])
                    df_b['stars'] = pd.to_numeric(df_b['stars'])

                    if criterio == "Piores Notas (1-2★)":
                        df_a = df_a.sort_values('stars', ascending=True)
                        df_b = df_b.sort_values('stars', ascending=True)
                    elif criterio == "Melhores Notas (5★)":
                        df_a = df_a.sort_values('stars', ascending=False)
                        df_b = df_b.sort_values('stars', ascending=False)
                    # Se for "Padrão", "Recentes" ou "Relevantes", não reordenamos por nota, mantemos como veio

                    # 4. Limita Quantidade
                    df_a_final = df_a.head(qtd_limite)
                    df_b_final = df_b.head(qtd_limite)

                    if df_a_final.empty or df_b_final.empty:
                        st.warning("Sem dados após aplicar os filtros.")
                    else:
                        # IA
                        txt_a = "\n".join(
                            [f"({r['stars']}★) {r['text']}" for i, r in df_a_final.iterrows() if r['text']])
                        txt_b = "\n".join(
                            [f"({r['stars']}★) {r['text']}" for i, r in df_b_final.iterrows() if r['text']])

                        analise = analisar_ia(txt_a, txt_b, obj_a['title'], obj_b['title'], criterio)

                        # Salva Histórico (COM CAMPO CRITÉRIO)
                        relatorio = {
                            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                            "data_geracao": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "periodo": f"{dt_ini.strftime('%d/%m')} a {dt_fim.strftime('%d/%m')}",
                            "criterio": criterio,
                            "empresa_a": obj_a['title'],
                            "empresa_b": obj_b['title'],
                            "nota_a_corte": float(df_a_final['stars'].mean()),
                            "nota_b_corte": float(df_b_final['stars'].mean()),
                            "analise_ia": analise,
                            "comentarios_a": df_a_final[['stars', 'text', 'publishAt']].to_dict('records'),
                            "comentarios_b": df_b_final[['stars', 'text', 'publishAt']].to_dict('records')
                        }
                        st.session_state.db_historico.insert(0, relatorio)
                        salvar_json(DB_HISTORICO, st.session_state.db_historico)

                        st.success("Análise Salva!")
                        st.markdown(analise)

# ---------------------------------------------------------
# 4. RELATÓRIOS
# ---------------------------------------------------------
elif menu == "📂 Relatórios Completos":
    st.header("📂 Arquivo de Estratégias")

    if not st.session_state.db_historico:
        st.info("Nenhum relatório.")
    else:
        # --- CORREÇÃO DO ERRO AQUI: .get('criterio', 'Geral') ---
        opcoes = [f"{r['data_geracao']} | {r.get('criterio', 'Geral')} | {r['empresa_a']} vs {r['empresa_b']}" for r in
                  st.session_state.db_historico]
        escolha = st.selectbox("Selecione um relatório:", opcoes)

        idx = opcoes.index(escolha)
        rel = st.session_state.db_historico[idx]

        with st.container(border=True):
            st.markdown(f"### 📊 Relatório: {rel.get('criterio', 'Geral')}")
            st.caption(f"Gerado em: {rel['data_geracao']} | Período: {rel['periodo']}")

            c1, c2 = st.columns(2)
            c1.metric(rel['empresa_a'], f"{rel['nota_a_corte']:.1f} ⭐")
            c2.metric(rel['empresa_b'], f"{rel['nota_b_corte']:.1f} ⭐")

            st.markdown("---")
            st.markdown(rel['analise_ia'])

            st.markdown("---")
            st.subheader("💬 Comentários Analisados")

            with st.expander(f"Reviews {rel['empresa_a']}"):
                if 'comentarios_a' in rel:
                    st.dataframe(pd.DataFrame(rel['comentarios_a']))
                else:
                    st.warning("Dados brutos indisponíveis.")

            with st.expander(f"Reviews {rel['empresa_b']}"):
                if 'comentarios_b' in rel:
                    st.dataframe(pd.DataFrame(rel['comentarios_b']))
                else:
                    st.warning("Dados brutos indisponíveis.")

            if st.button("🗑️ Excluir"):
                st.session_state.db_historico.pop(idx)
                salvar_json(DB_HISTORICO, st.session_state.db_historico)
                st.rerun()