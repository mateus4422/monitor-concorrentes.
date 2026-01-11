import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
import google.generativeai as genai
from datetime import datetime, timedelta
import streamlit as st

# --- CONFIGURAÇÕES ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"

def get_api_keys():
    try:
        return st.secrets["MY_APIFY_TOKEN"], st.secrets["MY_GEMINI_KEY"]
    except:
        return "", ""

MY_APIFY_TOKEN, MY_GEMINI_KEY = get_api_keys()

# --- DATABASE ---
def carregar_dados(arquivo):
    if not os.path.exists(arquivo): return {} if arquivo == DB_EMPRESAS else []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {} if arquivo == DB_EMPRESAS else []

def salvar_dados(arquivo, dados):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False, default=str)

# --- UTIL ---
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

def get_ibge_locais(tipo, uf=None):
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
        if tipo == "cidades": url += f"/{uf}/municipios"
        r = requests.get(url)
        return sorted([x['sigla' if tipo=='estados' else 'nome'] for x in r.json()])
    except: return []

# --- APIFY ---
def buscar_locais(termo):
    if not MY_APIFY_TOKEN: return []
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={"searchStringsArray": [termo], "maxCrawledPlacesPerSearch": 5, "language": "pt-BR", "maxReviews": 0})
        return client.dataset(run['defaultDatasetId']).list_items().items
    except: return []

def baixar_reviews(url, max_reviews=100):
    if not MY_APIFY_TOKEN: return None
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={"startUrls": [{"url": url}], "language": "pt-BR", "maxReviews": max_reviews, "reviewsSort": "newest"})
        items = client.dataset(run['defaultDatasetId']).list_items().items
        return items[0] if items else None
    except: return None

# --- IA PADRÃO (1 vs 1) ---
def gerar_analise_ia_detalhada(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "Erro config IA"
    genai.configure(api_key=MY_GEMINI_KEY)
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Atue como Consultor Sênior. Análise: {nome_a} (CLIENTE) vs {nome_b} (CONCORRENTE).
        REVIEWS CLIENTE: {texto_a[:3500]}
        REVIEWS CONCORRENTE: {texto_b[:3500]}
        
        Gere relatório Markdown:
        ### 📊 Radar (Tags)
        **{nome_a}**
        * 👍 Positivo: (3 tags)
        * 👎 Negativo: (3 tags)
        **{nome_b}**
        * 👍 Positivo: (3 tags)
        * 👎 Negativo: (3 tags)
        ---
        ### 🏆 Veredito Técnico
        (1 parágrafo)
        ### 💎 Análise de {nome_a}
        (Pontos fortes e Gaps)
        ### 🥊 Análise de {nome_b}
        (Vantagens e Fraquezas)
        ### 🚀 Plano de Ação
        (3 estratégias)
        """
        return model.generate_content(prompt).text
    except: return "IA Indisponível"

# --- IA NOVA (MATRIZ MULTI-CONCORRENTE) ---
def gerar_matriz_comparativa(dados_empresas):
    """
    Recebe um dict: {'Empresa A': 'Texto Reviews...', 'Empresa B': 'Texto Reviews...'}
    Retorna JSON para montar a tabela.
    """
    if not MY_GEMINI_KEY: return None
    genai.configure(api_key=MY_GEMINI_KEY)
    
    # Monta o prompt com os dados de todos
    texto_base = ""
    for nome, reviews in dados_empresas.items():
        texto_base += f"\n--- EMPRESA: {nome} ---\nREVIEWS: {reviews[:2500]}\n"

    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Atue como Juiz de Mercado. Analise as empresas abaixo com base nos reviews.
        {texto_base}

        Sua tarefa é determinar QUAL EMPRESA VENCE em cada categoria. Apenas UMA empresa pode vencer cada categoria.
        
        Categorias:
        1. Qualidade do Produto (Sabor/Material)
        2. Atendimento ao Cliente
        3. Rapidez/Entrega
        4. Custo-Benefício (Preço Justo)
        5. Ambiente/Apresentação

        Responda APENAS um JSON puro neste formato (sem markdown):
        {{
            "vencedores": {{
                "Qualidade do Produto": "Nome Exato da Empresa Vencedora",
                "Atendimento ao Cliente": "Nome Exato da Empresa Vencedora",
                "Rapidez/Entrega": "Nome Exato da Empresa Vencedora",
                "Custo-Benefício": "Nome Exato da Empresa Vencedora",
                "Ambiente/Apresentação": "Nome Exato da Empresa Vencedora"
            }},
            "resumo": "Um parágrafo curto explicando quem é o líder geral e porquê."
        }}
        """
        resposta = model.generate_content(prompt).text
        # Limpeza para garantir JSON puro
        resposta = resposta.replace("```json", "").replace("```", "").strip()
        return json.loads(resposta)
    except Exception as e:
        print(f"Erro IA: {e}")
        return None
