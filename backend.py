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
    # 1. Tenta pegar dos Secrets do Streamlit (Recomendado)
    try:
        apify = st.secrets["MY_APIFY_TOKEN"]
        gemini = st.secrets["MY_GEMINI_KEY"]
        return apify, gemini
    except:
        # 2. Se não tiver Secrets, use estas variáveis de fallback (Cuidado com GitHub!)
        # Se você não configurou os Secrets, cole suas chaves aqui:
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

# --- IA (AUTO-SCAN DE MODELOS) ---
def descobrir_modelo_ativo(api_key):
    """
    Consulta a API do Google para saber quais modelos esta chave tem permissão de usar.
    Retorna o nome exato do primeiro modelo compatível encontrado.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, f"Erro ao listar modelos: {response.text}"
        
        dados = response.json()
        modelos_disponiveis = dados.get('models', [])
        
        # Filtra apenas modelos que sabem gerar texto (generateContent)
        candidatos = []
        for m in modelos_disponiveis:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                # Remove o prefixo "models/" se existir, para usar na URL depois
                nome_limpo = m['name'].replace("models/", "")
                candidatos.append(nome_limpo)
        
        if not candidatos:
            return None, "Nenhum modelo de texto disponível para esta chave."
            
        # Prioridade: Tenta achar o Flash ou Pro, senão pega o primeiro que vier
        for c in candidatos:
            if 'flash' in c: return c, None
        for c in candidatos:
            if 'pro' in c: return c, None
            
        return candidatos[0], None # Retorna o primeiro que achar
        
    except Exception as e:
        return None, str(e)

def gerar_analise_ia(texto_a, texto_b, nome_a, nome_b):
    if not MY_GEMINI_KEY: return "⚠️ Erro: Chave IA não configurada."
    
    # 1. AUTO-SCAN: Descobre qual modelo usar
    modelo_escolhido, erro_scan = descobrir_modelo_ativo(MY_GEMINI_KEY)
    
    if not modelo_escolhido:
        return f"⚠️ Erro de Configuração IA: {erro_scan}. Verifique se a 'Generative Language API' está ativada no Google Cloud Console."

    # 2. PREPARA O PROMPT
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

    # 3. FAZ A CHAMADA USANDO O MODELO DESCOBERTO
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_escolhido}:generateContent?key={MY_GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            resultado = response.json()
            try:
                return resultado['candidates'][0]['content']['parts'][0]['text']
            except:
                return f"⚠️ A IA respondeu, mas o formato veio vazio. Modelo usado: {modelo_escolhido}"
        else:
            return f"⚠️ Erro na IA ({modelo_escolhido}): {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"⚠️ Erro de Conexão: {str(e)}"
