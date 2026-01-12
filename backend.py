import pandas as pd
import requests
import json
import os
from apify_client import ApifyClient
from datetime import datetime, timedelta
import streamlit as st
import matplotlib
matplotlib.use('Agg') # Segurança para servidores
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS

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

# --- VISUAL (NUVEM DE PALAVRAS LIMPA) ---
def gerar_nuvem_palavras(texto):
    if not texto or len(texto) < 10: return None
    
    # Lista padrão (Inglês)
    ignoradas = set(STOPWORDS)
    
    # NOSSA LISTA AGRESSIVA DE PORTUGUÊS (Adicione mais aqui se precisar)
    palavras_pt = [
        # Básico
        "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com", "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi", "ao", "ele", "das", "tem", "à", "seu", "sua", "ou", "ser", "quando", "muito", "nos", "já", "está", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela", "entre", "era", "depois", "sem", "mesmo", "aos", "ter", "seus", "quem", "nas", "me", "esse", "eles", "estão", "você", "tinha", "foram", "essa", "num", "nem", "suas", "meu", "às", "minha", "têm", "numa", "pelos", "elas", "havia", "seja", "qual", "será", "nós", "tenho", "lhe", "deles", "essas", "esses", "pelas", "este", "fosse", "dele", "tu", "te", "vocês", "vos", "lhes", "meus", "minhas", "teu", "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas", "dela", "delas", "esta", "estes", "estas", "aquele", "aquela", "aqueles", "aquelas", "isto", "aquilo",
        # Gírias e Abreviações
        "pra", "pro", "tá", "ta", "né", "ne", "vc", "vcs", "pq", "mto", "mt", "aí", "ai", "tava", "tbm", "eh", "sobre",
        # Verbos de Ação comuns (que não são o produto)
        "fui", "fomos", "fiz", "fizemos", "pedi", "pedimos", "chegou", "veio", "vai", "ia", "vão", "quer", "queria", "dizer", "falar", "falou", "disse", "amo", "amei", "gostei", "gostamos", "adoro", "adorei", "achei", "achamos", "ficar", "ficou", "ficamos", "voltar", "voltarei", "recomendo", "super",
        # Lugar e Tempo
        "aqui", "lá", "ali", "agora", "hoje", "ontem", "amanhã", "sempre", "nunca", "local", "lugar", "ambiente", "onde", "aonde",
        # Nomes comuns (Para limpar funcionários) - Edite aqui se aparecerem outros
        "maria", "josé", "joão", "pedro", "gabriel", "julia", "júlia", "isabela", "lucas", "matheus", "ana", "paulo", "atendente", "recepção", "garçom", "funcionário", "gerente", "dono"
    ]
    
    ignoradas.update(palavras_pt)

    try:
        # Gera a nuvem
        wordcloud = WordCloud(width=800, height=400, background_color='black', stopwords=ignoradas, min_font_size=10, colormap='Pastel1').generate(texto)
        
        fig, ax = plt.subplots(figsize=(10, 5), facecolor='k')
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis("off")
        plt.tight_layout(pad=0)
        return fig
    except Exception as e:
        print(f"Erro Nuvem: {e}")
        return None

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
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_escolhido}:generateContent?key={MY_GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            resultado = response.json()
            try: return resultado['candidates'][0]['content']['parts'][0]['text']
            except: return f"⚠️ IA respondeu vazio. Modelo: {modelo_escolhido}"
        else: return f"⚠️ Erro IA ({modelo_escolhido}): {response.status_code}"
    except Exception as e: return f"⚠️ Erro Conexão: {str(e)}"
