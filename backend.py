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

def get_keys():
    # Tenta pegar dos segredos do Streamlit, senão retorna vazio
    try:
        return st.secrets["MY_APIFY_TOKEN"], st.secrets["MY_GEMINI_KEY"]
    except:
        return "", ""

MY_APIFY_TOKEN, MY_GEMINI_KEY = get_keys()

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

# --- IA (TEXTO SIMPLES - MAIS ESTÁVEL) ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chave da IA não configurada. Verifique os 'Secrets'."
    
    genai.configure(api_key=MY_GEMINI_KEY)
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Atue como Consultor Sênior. Comparativo: {nome_a} vs {nome_b}.
        REVIEWS A: {texto_a[:3500]}
        REVIEWS B: {texto_b[:3500]}
        
        Gere relatório Markdown:
        ### 📊 Radar (Tags Rápidas)
        **{nome_a}**
        * 👍 Positivo: (3 palavras-chave)
        * 👎 Negativo: (3 palavras-chave)
        
        **{nome_b}**
        * 👍 Positivo: (3 palavras-chave)
        * 👎 Negativo: (3 palavras-chave)

        ---
        ### 🏆 Veredito
        (Resumo de quem ganha)

        ### 💎 Análise de {nome_a}
        (Pontos fortes e fracos detalhados)

        ### 🥊 Análise de {nome_b}
        (Pontos fortes e fracos detalhados)

        ### 🚀 Plano de Ação
        (3 passos práticos)
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ IA Indisponível no momento. Detalhe: {str(e)}"
