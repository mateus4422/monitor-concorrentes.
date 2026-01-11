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
# 🔐 ÁREA DE CHAVES (SEGURA - LÊ DOS SECRETS)
# ==============================================================================
def get_keys():
    # Tenta ler do cofre do Streamlit (Nuvem)
    try:
        apify = st.secrets["MY_APIFY_TOKEN"]
        gemini = st.secrets["MY_GEMINI_KEY"]
        return apify, gemini
    except Exception:
        # Se estiver rodando no seu PC sem secrets.toml, retorna erro ou vazio
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
        if not items: return None
        return items[0]
    except: return None

# --- IA (CONEXÃO DIRETA COM FALLBACK) ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chaves não configuradas nos 'Secrets' do Streamlit."
    
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

    # Tenta usar o modelo FLASH (Rápido), se falhar, tenta o PRO
    modelos = ["gemini-1.5-flash", "gemini-pro"]
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    erros = []

    for modelo in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={MY_GEMINI_KEY}"
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                resultado = response.json()
                try:
                    return resultado['candidates'][0]['content']['parts'][0]['text']
                except:
                    erros.append(f"{modelo}: JSON inválido")
            else:
                erros.append(f"{modelo}: Erro {response.status_code} - {response.text}")
                
        except Exception as e:
            erros.append(f"{modelo}: {str(e)}")

    return f"⚠️ IA Indisponível. Detalhes: {'; '.join(erros)}"
