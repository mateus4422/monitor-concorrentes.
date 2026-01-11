import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
import google.generativeai as genai
from datetime import datetime, timedelta
import streamlit as st

# --- CONFIGURAÇÕES DE ARQUIVOS ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"

# --- GERENCIAMENTO DE CHAVES (SECRETS) ---
def get_api_keys():
    try:
        return st.secrets["MY_APIFY_TOKEN"], st.secrets["MY_GEMINI_KEY"]
    except:
        return "", "" # Retorna vazio se não configurado localmente

MY_APIFY_TOKEN, MY_GEMINI_KEY = get_api_keys()

# --- BANCO DE DADOS (JSON) ---
def carregar_dados(arquivo):
    if not os.path.exists(arquivo): return {} if arquivo == DB_EMPRESAS else []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {} if arquivo == DB_EMPRESAS else []

def salvar_dados(arquivo, dados):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False, default=str)

# --- UTILITÁRIOS DE DATA E IBGE ---
def tratar_data_google(texto):
    if not isinstance(texto, str): return pd.NaT
    texto = texto.lower().strip()
    agora = datetime.now()
    # Lógica de conversão relativa (ex: "3 dias atrás")
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

# --- INTEGRAÇÃO APIFY (GOOGLE MAPS) ---
def buscar_locais(termo):
    if not MY_APIFY_TOKEN: return []
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "searchStringsArray": [termo], "maxCrawledPlacesPerSearch": 5, "language": "pt-BR", "maxReviews": 0
        })
        return client.dataset(run['defaultDatasetId']).list_items().items
    except: return []

def baixar_reviews(url, max_reviews=150):
    if not MY_APIFY_TOKEN: return None
    client = ApifyClient(MY_APIFY_TOKEN)
    try:
        run = client.actor("compass/crawler-google-places").call(run_input={
            "startUrls": [{"url": url}], "language": "pt-BR", "maxReviews": max_reviews, "reviewsSort": "newest"
        })
        items = client.dataset(run['defaultDatasetId']).list_items().items
        return items[0] if items else None
    except: return None

# --- INTEGRAÇÃO GEMINI (IA) ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "Erro: Chave de API da IA não configurada."
    genai.configure(api_key=MY_GEMINI_KEY)
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Você é um Consultor Estratégico Sênior.
        Análise: {nome_a} (CLIENTE) vs {nome_b} (CONCORRENTE).
        
        REVIEWS CLIENTE: {texto_a[:3500]}
        REVIEWS CONCORRENTE: {texto_b[:3500]}
        
        Gere um relatório Executivo em Markdown.
        
        ### 📊 Radar de Percepção (Tags)
        **{nome_a}**
        * 👍 Positivo: (3 palavras-chave)
        * 👎 Negativo: (3 palavras-chave)
        
        **{nome_b}**
        * 👍 Positivo: (3 palavras-chave)
        * 👎 Negativo: (3 palavras-chave)

        ---
        ### 🏆 Veredito Técnico
        (Resumo comparativo direto e profissional)

        ### 💎 Análise de {nome_a}
        (Pontos fortes e Gaps de qualidade)

        ### 🥊 Análise de {nome_b}
        (Vantagens competitivas e Fraquezas exploráveis)

        ### 🚀 Plano de Ação
        (3 iniciativas estratégicas imediatas)
        """
        return model.generate_content(prompt).text
    except: return "Serviço de Inteligência indisponível no momento."
