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

# ==============================================================================
# 🔐 ÁREA DE CHAVES (EDITAR AQUI SE NÃO CONECTAR)
# ==============================================================================
# Coloque suas chaves dentro das aspas abaixo para garantir a conexão:
TOKEN_APIFY_FIXO = "apify_api_yRzwwIYgcwqLjvf2aL0yWnyjss54F00ym2nK"  # <--- Sua chave Apify
KEY_GEMINI_FIXA = ""       # <--- Cole sua chave do Google Gemini (AIza...) aqui

def get_keys():
    # 1. Tenta usar as chaves fixas acima
    apify = TOKEN_APIFY_FIXO
    gemini = KEY_GEMINI_FIXA
    
    # 2. Se estiverem vazias, tenta pegar do Streamlit Secrets (Nuvem)
    if not apify:
        try: apify = st.secrets["MY_APIFY_TOKEN"]
        except: pass
    
    if not gemini:
        try: gemini = st.secrets["MY_GEMINI_KEY"]
        except: pass
        
    return apify, gemini

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

# --- APIFY (GOOGLE MAPS) ---
def buscar_locais(termo):
    if not MY_APIFY_TOKEN: 
        print("ERRO: Token Apify não encontrado.")
        return []
    
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        # Busca no Google Maps
        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [termo], 
            "maxCrawledPlacesPerSearch": 5, 
            "language": "pt-BR", 
            "maxReviews": 0
        })
        return client.dataset(run['defaultDatasetId']).list_items().items
    except Exception as e:
        print(f"Erro Apify Busca: {e}")
        return []

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
    except Exception as e:
        print(f"Erro Apify Reviews: {e}")
        return None

# --- IA (MODELO ATUALIZADO) ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chave da IA (Gemini) não configurada no backend.py"
    
    genai.configure(api_key=MY_GEMINI_KEY)
    try:
        # USA O MODELO NOVO (CORREÇÃO DO ERRO 404)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
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
        (Resumo de quem ganha e porquê)

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
        return f"⚠️ IA Indisponível. Erro: {str(e)}"
