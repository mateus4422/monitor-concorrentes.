import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
from datetime import datetime, timedelta
import streamlit as st

# --- CONFIGURAÇÕES ---
DB_EMPRESAS = "empresas.json"
DB_HISTORICO = "historico.json"

# ==============================================================================
# 🔐 ÁREA DE CHAVES
# ==============================================================================
TOKEN_APIFY_FIXO = "apify_api_RgXeXG5dKTgLN0US1LbDrNFDS9xJHY1eJK86"
# Sua chave Google AI Studio:
KEY_GEMINI_FIXA = "AIzaSyBqEgzqsdvo-zMcVwjMLxM3H7ZAZJ4LosM"

def get_keys():
    return TOKEN_APIFY_FIXO, KEY_GEMINI_FIXA

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
        if not items: return None
        return items[0]
    except: return None

# --- IA (AUTO-DESCOBERTA DE MODELO) ---
def descobrir_modelo_disponivel(api_key):
    """Pergunta ao Google quais modelos a chave pode usar"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Procura o primeiro modelo que suporte 'generateContent'
            for model in data.get('models', []):
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    # Retorna o nome limpo (ex: models/gemini-pro -> gemini-pro)
                    return model['name'].replace("models/", "")
        return None
    except:
        return None

def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chave IA ausente."
    
    # 1. TENTA DESCOBRIR QUAL MODELO USAR
    modelo_ativo = descobrir_modelo_disponivel(MY_GEMINI_KEY)
    
    # Se não descobrir, usa um fallback manual
    if not modelo_ativo:
        modelo_ativo = "gemini-1.5-flash" 

    prompt_text = f"""
    Atue como Consultor Sênior. Comparativo: {nome_a} vs {nome_b}.
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

    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    # Tenta usar o modelo descoberto
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_ativo}:generateContent?key={MY_GEMINI_KEY}"
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            resultado = response.json()
            try:
                return resultado['candidates'][0]['content']['parts'][0]['text']
            except:
                return "⚠️ Erro: A IA respondeu mas o formato veio vazio."
        else:
            # RETORNA O ERRO REAL DO GOOGLE PARA LERMOS
            return f"⚠️ Erro Google ({response.status_code}): {response.text}"

    except Exception as e:
        return f"⚠️ Erro de Conexão: {str(e)}"
