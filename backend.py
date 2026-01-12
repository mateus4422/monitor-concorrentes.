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
def get_keys():
    try:
        apify = st.secrets["MY_APIFY_TOKEN"]
        gemini = st.secrets["MY_GEMINI_KEY"]
        return apify, gemini
    except:
        TOKEN_APIFY_FIXO = "apify_api_RgXeXG5dKTgLN0US1LbDrNFDS9xJHY1eJK86"
        KEY_GEMINI_FIXA = "AIzaSyBqEgzqsdvo-zMcVwjMLxM3H7ZAZJ4LosM" 
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

# --- IA (AUTO-SCAN) ---
def descobrir_modelo_ativo(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200: return None, f"Erro ao listar: {response.text}"
        dados = response.json()
        candidatos = []
        for m in dados.get('models', []):
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                candidatos.append(m['name'].replace("models/", ""))
        if not candidatos: return None, "Sem modelos disponíveis."
        for c in candidatos:
            if 'flash' in c: return c, None
        for c in candidatos:
            if 'pro' in c: return c, None
        return candidatos[0], None
    except Exception as e: return None, str(e)

# --- FUNÇÃO 1: ANÁLISE COMPARATIVA ---
def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chave IA não configurada."
    
    modelo_escolhido, erro_scan = descobrir_modelo_ativo(MY_GEMINI_KEY)
    if not modelo_escolhido: return f"⚠️ Config IA: {erro_scan}"

    prompt_text = f"""
    Atue como Consultor Sênior. Comparativo: {nome_a} vs {nome_b}.
    REVIEWS A: {texto_a[:3500]}
    REVIEWS B: {texto_b[:3500]}
    
    Gere relatório em Markdown:
    ### 📊 Radar (Tags Rápidas)
    **{nome_a}**
    * 👍 Positivo: (3 tags curtas)
    * 👎 Negativo: (3 tags curtas)
    
    **{nome_b}**
    * 👍 Positivo: (3 tags curtas)
    * 👎 Negativo: (3 tags curtas)

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
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_escolhido}:generateContent?key={MY_GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            resultado = response.json()
            try: return resultado['candidates'][0]['content']['parts'][0]['text']
            except: return "⚠️ IA respondeu vazio."
        else:
            # MOSTRA O ERRO REAL (DIAGNÓSTICO)
            return f"⚠️ Erro Google ({response.status_code}): {response.text}"
    except Exception as e: return f"⚠️ Erro Conexão: {str(e)}"

# --- FUNÇÃO 2: GERADOR DE RESPOSTAS (DIAGNÓSTICO ATIVADO) ---
def gerar_sugestao_resposta(review_texto, estrelas, nome_empresa):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chave IA não configurada."
    
    modelo_escolhido, erro_scan = descobrir_modelo_ativo(MY_GEMINI_KEY)
    if not modelo_escolhido: return f"Erro na IA: {erro_scan}"

    prompt_text = f"""
    Você é o Gerente de Sucesso do Cliente da empresa '{nome_empresa}'.
    
    TAREFA: Escreva uma resposta profissional e humanizada para este review recebido no Google.
    
    DADOS DO REVIEW:
    Nota: {estrelas} Estrelas
    Comentário do Cliente: "{review_texto}"
    
    DIRETRIZES:
    1. Se for crítica (1-3 estrelas): Peça desculpas, mostre empatia, não dê desculpas esfarrapadas e convide para uma nova chance.
    2. Se for elogio (4-5 estrelas): Agradeça com entusiasmo e convide para voltar.
    3. Seja breve e cordial.
    4. Responda em Português do Brasil.
    
    Gere apenas o texto da resposta, pronto para copiar e colar.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_escolhido}:generateContent?key={MY_GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            resultado = response.json()
            try: return resultado['candidates'][0]['content']['parts'][0]['text']
            except: return "⚠️ Erro ao gerar texto (JSON inválido)."
        else:
            # MOSTRA O ERRO REAL AQUI
            return f"⚠️ Erro Google ({response.status_code}): {response.text}"
            
    except Exception as e: return f"⚠️ Erro Python: {str(e)}"
