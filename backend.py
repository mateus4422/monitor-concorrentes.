import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
from openai import OpenAI
from datetime import datetime, timedelta
import streamlit as st

# --- CONFIGURAÇÕES ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"

# ==============================================================================
# 🔐 ÁREA DE CHAVES (ATUALIZADA)
# ==============================================================================
# NOVA CHAVE APIFY:
TOKEN_APIFY_FIXO = "apify_api_RgXeXG5dKTgLN0US1LbDrNFDS9xJHY1eJK86"

# SUA CHAVE OPENAI (Mantida a anterior):
KEY_OPENAI_FIXA = "AIzaSyBzC0pjgmhKXUxrsDlO5eUPqZxfhg-gfXw"

def get_keys():
    return TOKEN_APIFY_FIXO, KEY_OPENAI_FIXA

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

# --- APIFY (GOOGLE MAPS) ---
def buscar_locais(termo):
    if not MY_APIFY_TOKEN: 
        st.error("❌ Erro: Chave Apify não configurada no backend.")
        return []
    
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [termo], 
            "maxCrawledPlacesPerSearch": 5, 
            "language": "pt-BR", 
            "maxReviews": 0
        })
        return client.dataset(run['defaultDatasetId']).list_items().items
    except Exception as e:
        st.error(f"❌ Erro ao Buscar Empresa (Apify): {e}")
        return []

def baixar_reviews(url, max_reviews=100):
    if not MY_APIFY_TOKEN: 
        st.error("❌ Erro: Chave Apify vazia.")
        return None
    
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        # Tenta rodar o scraper
        run = client.actor("compass/crawler-google-places").call(run_input={
            "startUrls": [{"url": url}], 
            "language": "pt-BR", 
            "maxReviews": max_reviews, 
            "reviewsSort": "newest"
        })
        # Pega os resultados
        items = client.dataset(run['defaultDatasetId']).list_items().items
        
        if not items:
            st.warning(f"⚠️ O Apify rodou mas não retornou dados para a URL: {url}")
            return None
            
        return items[0]
        
    except Exception as e:
        st.error(f"❌ ERRO CRÍTICO NO APIFY: {str(e)}")
        return None

# --- IA (OPENAI / CHATGPT) ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_OPENAI_KEY: 
        return "⚠️ Erro: Chave OpenAI não configurada."
    
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
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ]
        )
        return response.choices[0].message.content
        
    except Exception as e:
        return f"⚠️ Erro na IA (OpenAI): {str(e)}"
