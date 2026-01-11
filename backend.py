import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
from openai import OpenAI  # <--- MUDANÇA AQUI (Usa OpenAI agora)
from datetime import datetime, timedelta
import streamlit as st

# --- CONFIGURAÇÕES ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"

# ==============================================================================
# 🔐 ÁREA DE CHAVES
# ==============================================================================
TOKEN_APIFY_FIXO = "apify_api_yRzwwIYgcwqLjvf2aL0yWnyjss54F00ym2nK"
# Coloque sua chave sk-proj-... aqui dentro das aspas:
KEY_OPENAI_FIXA = "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"

def get_keys():
    apify = TOKEN_APIFY_FIXO
    openai_key = KEY_OPENAI_FIXA
    
    # Backup: Tenta pegar do Streamlit Cloud se não tiver fixo
    if not apify:
        try: apify = st.secrets["MY_APIFY_TOKEN"]
        except: pass
    
    if not openai_key:
        try: openai_key = st.secrets["MY_OPENAI_KEY"]
        except: pass
        
    return apify, openai_key

MY_APIFY_TOKEN, MY_OPENAI_KEY = get_keys()

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
        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [termo], 
            "maxCrawledPlacesPerSearch": 5, 
            "language": "pt-BR", 
            "maxReviews": 0
        })
        return client.dataset(run['defaultDatasetId']).list_items().items
    except: return []

def baixar_reviews(url, max_reviews=100):
    if not MY_APIFY_TOKEN: return None
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "startUrls": [{"url": url}], 
            "language": "pt-BR", 
            "maxReviews": max_reviews, 
            "reviewsSort": "newest"
        })
        items = client.dataset(run['defaultDatasetId']).list_items().items
        return items[0] if items else None
    except: return None

# --- IA (AGORA USANDO OPENAI / CHATGPT) ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_OPENAI_KEY: return "⚠️ Erro: Chave OpenAI não configurada."
    
    try:
        client = OpenAI(api_key=MY_OPENAI_KEY)
        
        prompt_sistema = "Você é um Consultor Sênior de Estratégia Corporativa."
        prompt_usuario = f"""
        Comparativo: {nome_a} vs {nome_b}.
        REVIEWS A: {texto_a[:3500]}
        REVIEWS B: {texto_b[:3500]}
        
        Gere relatório em Markdown:
        ### 📊 Radar (Tags Rápidas)
        **{nome_a}**
        * 👍 Positivo: (3 tags)
        * 👎 Negativo: (3 tags)
        
        **{nome_b}**
        * 👍 Positivo: (3 tags)
        * 👎 Negativo: (3 tags)

        ---
        ### 🏆 Veredito
        (Resumo direto)

        ### 💎 Análise de {nome_a}
        (Pontos fortes e fracos)

        ### 🥊 Análise de {nome_b}
        (Pontos fortes e fracos)

        ### 🚀 Plano de Ação
        (3 passos)
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Ou "gpt-4o" se tiver acesso
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ]
        )
        return response.choices[0].message.content
        
    except Exception as e:
        return f"⚠️ Erro na IA (OpenAI): {str(e)}"
