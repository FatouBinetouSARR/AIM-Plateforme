# ================================================================
# streamlit_app.py — Version complète avec toutes les fonctionnalités
# AIM : Analyse Marketing Intelligente
# ================================================================

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import re
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import requests
from datetime import datetime, timedelta

# ================================================================
# 🎨 Palette couleurs AIM + Fond jaune clair
# ================================================================
AIM_PALETTE = [
    "#2ECC71", "#27AE60", "#3498DB", "#2980B9",
    "#F1C40F", "#F39C12", "#E67E22", "#E74C3C", "#C0392B"
]

# Configuration du fond jaune très clair
BACKGROUND_COLOR = "#FFFDE7"  # Jaune très clair et lumineux
SIDEBAR_COLOR = "#FFF9C4"    # Jaune un peu plus soutenu pour le sidebar
TEXT_COLOR = "#212121"       # Gris foncé pour meilleur contraste

# Appliquer le style CSS pour le fond clair et titre centré
page_bg_css = """
<style>
.stApp {
    background-color: #FFFDE7 !important;
    color: #212121 !important;
}

/* TITRE PRINCIPAL CENTRÉ ET PLUS GROS */
h1 {
    text-align: center !important;
    font-size: 3.5rem !important;
    font-weight: 800 !important;
    color: #FF6B00 !important;
    margin-top: 20px !important;
    margin-bottom: 40px !important;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
    background: linear-gradient(90deg, #FF6B00, #FF9800);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding: 15px;
    border-bottom: 4px solid #FFD54F;
}

/* Sous-titres */
h2 {
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #5D4037 !important;
    margin-top: 30px !important;
    margin-bottom: 20px !important;
    padding-bottom: 10px;
    border-bottom: 2px solid #FFD54F;
}

h3 {
    font-size: 1.8rem !important;
    font-weight: 600 !important;
    color: #795548 !important;
}

/* Style pour les cartes d'opportunités */
.opportunity-card {
    background: linear-gradient(135deg, #ffffff, #FFF9C4);
    border-radius: 15px;
    padding: 20px;
    margin: 15px 0;
    border-left: 6px solid #FF9800;
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.opportunity-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.12);
}

.opportunity-badge {
    display: inline-block;
    background: linear-gradient(90deg, #FF9800, #FF5722);
    color: white;
    padding: 8px 15px;
    border-radius: 20px;
    font-weight: bold;
    margin-bottom: 10px;
    font-size: 0.9rem;
}

.opportunity-tag {
    display: inline-block;
    background: #E3F2FD;
    color: #1565C0;
    padding: 5px 12px;
    border-radius: 15px;
    margin: 3px;
    font-size: 0.85rem;
    border: 1px solid #90CAF9;
}

/* Style pour le contenu principal */
.main .block-container {
    background-color: rgba(255, 255, 255, 0.85) !important;
    border-radius: 15px;
    padding: 25px;
    margin-top: 20px;
    margin-bottom: 20px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(255, 235, 59, 0.2);
}

/* Style pour les cartes et sections */
.css-1d391kg, .css-12oz5g7, .css-1y4p8pa, .css-18e3th9, .css-1lcbmhc {
    background-color: rgba(255, 255, 255, 0.92) !important;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    border: 1px solid rgba(255, 235, 59, 0.3);
}

/* Style pour les métriques */
.css-1xarl3l, .css-1v0mbdj, [data-testid="stMetric"] {
    background-color: rgba(255, 255, 255, 0.95) !important;
    border-radius: 10px;
    padding: 15px;
    border: 2px solid #FFEB3B !important;
    box-shadow: 0 3px 8px rgba(255, 193, 7, 0.15);
}

/* Style pour le sidebar */
.css-1d391kg {
    background-color: rgba(255, 253, 231, 0.95) !important;
}

/* Style pour les faux avis */
.fake-review-card {
    background: linear-gradient(135deg, #FFEBEE, #FFCDD2);
    border-radius: 10px;
    padding: 15px;
    margin: 10px 0;
    border-left: 6px solid #F44336;
    box-shadow: 0 4px 10px rgba(244, 67, 54, 0.1);
}

.real-review-card {
    background: linear-gradient(135deg, #E8F5E9, #C8E6C9);
    border-radius: 10px;
    padding: 15px;
    margin: 10px 0;
    border-left: 6px solid #4CAF50;
    box-shadow: 0 4px 10px rgba(76, 175, 80, 0.1);
}

/* Style pour les statistiques */
.statistics-table {
    background: white;
    border-radius: 10px;
    padding: 15px;
    margin: 15px 0;
    box-shadow: 0 3px 10px rgba(0,0,0,0.1);
}
</style>
"""

# ================================================================
# ⚙️ Configuration Streamlit
# ================================================================
st.set_page_config(page_title="AIM – Dashboard", page_icon="📊", layout="wide")
st.markdown(page_bg_css, unsafe_allow_html=True)

# TITRE CENTRÉ AVEC MARKDOWN POUR UN MEILLUR CONTRÔLE
st.markdown("""
<div style="text-align: center;">
    <h1 style="font-size: 3.8rem; font-weight: 900; color: #FF6B00; 
               margin-bottom: 10px; text-shadow: 3px 3px 6px rgba(0,0,0,0.15);">
        📊 AIM – Analyse Marketing Intelligente
    </h1>
    <p style="font-size: 1.3rem; color: #666; margin-top: 0; margin-bottom: 40px;">
        Plateforme d'analyse avancée des sentiments, détection de faux avis et insights marketing
    </p>
</div>
""", unsafe_allow_html=True)

# ================================================================
# 🔧 Fonctions utilitaires
# ================================================================
@st.cache_data(show_spinner=False)
def safe_load(filename):
    try:
        return joblib.load(filename)
    except:
        return None

def clean_text(text):
    if pd.isnull(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+|https\S+", " ", text)
    text = re.sub(r"[^a-z0-9àâäéèêëïîôöùûüç\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def detect_fake_reviews(texts, threshold=0.6):
    """Détection de faux avis par patterns et analyse linguistique"""
    fake_patterns = [
        # Patterns de répétition exagérée
        r"(excellent|parfait|génial|incroyable).{0,5}\1",
        r"(\w+).{0,3}\1.{0,3}\1",  # Mots répétés 3 fois
        
        # Patterns de formules génériques
        r"je.*recommande.*(à tous|fortement|vivement)",
        r"produit.*(exceptionnel|parfait|incroyable).*service.*(exceptionnel|parfait|incroyable)",
        
        # Patterns de superlatifs multiples
        r"(très|vraiment|absolument).{0,5}(bon|excellent|parfait|génial)",
        r"(le|la).{0,5}(meilleur|meilleure|top|numéro)",
        
        # Patterns de spam
        r"ach.{0,5}maintenant|commander.{0,5}immédiat",
        r"\d{5,}|[A-Z]{5,}",  # Codes ou séries de majuscules
        
        # Patterns de manque de spécificité
        r"produit|service|article.{0,10}(correct|ok|bien)",
    ]
    
    fake_scores = []
    fake_reasons = []
    
    for text in texts:
        score = 0
        reasons = []
        
        # Vérifier chaque pattern
        for i, pattern in enumerate(fake_patterns):
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.1
                reasons.append(f"Pattern {i+1}")
        
        # Longueur du texte (trop court = suspect)
        if len(text.split()) < 5:
            score += 0.3
            reasons.append("Texte trop court")
        
        # Émojis excessifs
        emoji_count = len(re.findall(r'[^\w\s,]', text))
        if emoji_count > 5:
            score += 0.2
            reasons.append("Trop d'émojis")
        
        fake_scores.append(score / 1.0)  # Normalisation
        fake_reasons.append(", ".join(reasons[:3]) if reasons else "Aucun pattern détecté")
    
    # Déterminer si c'est faux basé sur le seuil
    is_fake = [score > threshold for score in fake_scores]
    
    return is_fake, fake_scores, fake_reasons

def calculate_engagement_score(df, product_col=None):
    """Calcul du score d'engagement"""
    engagement_scores = []
    
    for idx, row in df.iterrows():
        score = 0
        
        # Score basé sur la longueur du texte
        text_length = len(str(row.get('clean_text', '')))
        if text_length > 100:
            score += 2
        elif text_length > 50:
            score += 1
        
        # Score basé sur le sentiment
        sentiment = row.get('sentiment', 'neutral')
        if sentiment == 'positive':
            score += 2
        elif sentiment == 'negative':
            score += 1  # Les avis négatifs montrent aussi de l'engagement
        
        # Score basé sur la présence de questions
        if '?' in str(row.get('clean_text', '')):
            score += 1
        
        # Score basé sur la présence de mots d'action
        action_words = ['recommand', 'achèterai', 'conseill', 'utilis', 'essay']
        text_lower = str(row.get('clean_text', '')).lower()
        if any(word in text_lower for word in action_words):
            score += 1
        
        engagement_scores.append(min(score, 5))  # Limiter à 5
    
    return engagement_scores

def fetch_from_api(api_url, api_key=None, params=None):
    """Fonction pour récupérer des données depuis une API"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        if params is None:
            params = {}
        
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Convertir en DataFrame (structure générique)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                if 'data' in data:
                    df = pd.DataFrame(data['data'])
                elif 'results' in data:
                    df = pd.DataFrame(data['results'])
                else:
                    # Essayer de créer un DataFrame avec le dictionnaire
                    df = pd.DataFrame([data])
            else:
                df = pd.DataFrame()
            
            return df
        else:
            st.error(f"Erreur API: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Erreur de connexion à l'API: {e}")
        return pd.DataFrame()

# ================================================================
# 📥 IMPORTATION DES DONNÉES
# ================================================================
st.sidebar.header("📥 Source des données")

# Initialisation de la variable session state pour stocker les données
if 'df' not in st.session_state:
    st.session_state.df = None
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# Choix de la source
data_source = st.sidebar.radio("Choisir la source:", ["Fichier local", "API Entreprise", "Exemple de données"])

if data_source == "Fichier local":
    st.sidebar.header("1️⃣ Importer un Dataset")
    uploaded = st.sidebar.file_uploader("Importer un CSV ou Excel", type=["csv", "xlsx"])
    
    if uploaded is not None:
        try:
            if uploaded.name.lower().endswith(".csv"):
                st.session_state.df = pd.read_csv(uploaded)
            else:
                st.session_state.df = pd.read_excel(uploaded)
            st.session_state.data_loaded = True
            st.sidebar.success(f"✅ {uploaded.name} chargé avec succès !")
        except Exception as e:
            st.sidebar.error(f"❌ Erreur lors du chargement : {e}")
            st.stop()
    else:
        if not st.session_state.data_loaded:
            st.info("🗂️ Veuillez importer un fichier pour commencer.")
            st.stop()

elif data_source == "API Entreprise":
    st.sidebar.header("🌐 Connexion API")
    
    api_url = st.sidebar.text_input("URL de l'API", value="https://api.example.com/reviews")
    api_key = st.sidebar.text_input("Clé API", type="password")
    
    # Paramètres API
    col1, col2 = st.sidebar.columns(2)
    with col1:
        limit = st.number_input("Nombre de résultats", min_value=10, max_value=1000, value=100)
    with col2:
        days_back = st.number_input("Derniers jours", min_value=1, max_value=365, value=30)
    
    # Bouton pour récupérer les données
    if st.sidebar.button("📡 Récupérer les données", type="primary"):
        with st.spinner("Connexion à l'API en cours..."):
            params = {
                'limit': limit,
                'date_from': (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            }
            df_temp = fetch_from_api(api_url, api_key, params)
            
            if df_temp is not None and not df_temp.empty:
                st.session_state.df = df_temp
                st.session_state.data_loaded = True
                st.sidebar.success(f"✅ {len(df_temp)} enregistrements récupérés")
            else:
                st.sidebar.warning("⚠️ Aucune donnée récupérée ou erreur de connexion")
                st.stop()
    
    # Si aucune donnée n'a été chargée, afficher un message
    if not st.session_state.data_loaded:
        st.info("🌐 Configurez les paramètres de l'API et cliquez sur 'Récupérer les données'")
        st.stop()

elif data_source == "Exemple de données":
    # Créer un dataset exemple plus complet et varié
    st.sidebar.info("📊 Chargement des données exemple...")
    
    example_data = {
        'produit': ['iPhone 15 Pro', 'iPhone 15 Pro', 'Samsung Galaxy S24', 'Samsung Galaxy S24', 'Google Pixel 8', 
                   'iPhone 15 Pro', 'Samsung Galaxy S24', 'Google Pixel 8', 'iPhone 15 Pro', 'Google Pixel 8',
                   'Casque Sony WH-1000XM5', 'MacBook Pro M3', 'Nike Air Max', 'PlayStation 5', 'Canon EOS R5'],
        'avis': [
            'Le téléphone est excellent, la caméra est incroyable pour les photos de nuit.',
            'Bonne batterie, écran fluide. Je suis satisfait de mon achat.',
            'Correct mais la batterie se décharge trop vite. Rien d exceptionnel.',
            'Incroyable ! Le meilleur téléphone Android ! ACHETEZ-LE MAINTENANT !',
            'Service client médiocre mais le produit fonctionne bien.',
            'Bon rapport qualité-prix, je recommande ce produit à mes amis.',
            'Mauvais produit, je regrette mon achat. La qualité est faible.',
            'Photos exceptionnelles, interface intuitive. Très bon téléphone.',
            'Correct mais pourrait être amélioré. La charge rapide manque.',
            'PARFAIT PARFAIT PARFAIT ! Meilleur achat de l année !',
            'Casque confortable, réduction de bruit impressionnante. Excellent achat.',
            'Ordinateur puissant, écran Retina magnifique. Parfait pour le travail.',
            'Chaussures très confortables pour la course. Je les utilise tous les jours.',
            'Console géniale, les graphismes sont incroyables. Je recommande !',
            'Appareil photo professionnel, autofocus rapide. Idéal pour les portraits.'
        ],
        'date': pd.date_range(start='2024-01-01', periods=15, freq='D'),
        'note': [5, 4, 3, 5, 2, 4, 1, 5, 3, 5, 5, 5, 4, 5, 5],
        'utilisateur': ['JeanDupont', 'MarieMartin', 'PierreDurand', 'SophieLeroy', 'ThomasMoreau',
                       'JulieBernard', 'NicolasPetit', 'IsabelleRoux', 'MichelLefevre', 'CarolineMorel',
                       'DavidSimon', 'SarahLaurent', 'AlexandreFontaine', 'LauraChevalier', 'MarcDumont']
    }
    
    st.session_state.df = pd.DataFrame(example_data)
    st.session_state.data_loaded = True
    st.sidebar.success("✅ Données exemple chargées")

# Vérifier si le DataFrame est vide ou None
if st.session_state.df is None or st.session_state.df.empty or not st.session_state.data_loaded:
    st.warning("⚠️ Aucune donnée disponible. Veuillez charger des données.")
    st.stop()

# Récupérer le DataFrame depuis session state
df = st.session_state.df


# ================================================================
# 🔍 FILTRES AVANCÉS
# ================================================================
st.sidebar.header("🔍 Filtres Avancés")

# Identifier les colonnes potentielles pour les filtres
# Version robuste qui n'utilise pas select_dtypes
text_columns = []
date_columns = []
numeric_columns = []

if df is not None and not df.empty:
    for col in df.columns:
        try:
            # Vérifier le type de la colonne
            col_dtype = str(df[col].dtype)
            
            # Détecter les colonnes texte
            if any(dtype in col_dtype.lower() for dtype in ['object', 'string', 'category']):
                text_columns.append(col)
            # Vérifier si c'est une colonne datetime
            elif any(dtype in col_dtype.lower() for dtype in ['datetime', 'date', 'time']):
                date_columns.append(col)
            # Vérifier si c'est numérique
            elif any(dtype in col_dtype.lower() for dtype in ['int', 'float', 'number']):
                numeric_columns.append(col)
            # Fallback : vérifier le contenu
            else:
                # Échantillonner quelques valeurs
                sample = df[col].dropna().head(5)
                if len(sample) > 0:
                    # Vérifier si c'est du texte
                    if all(isinstance(x, str) for x in sample):
                        text_columns.append(col)
                    # Vérifier si c'est une date
                    elif all(isinstance(x, (datetime, pd.Timestamp)) for x in sample):
                        date_columns.append(col)
                    # Vérifier si c'est numérique
                    elif all(isinstance(x, (int, float, np.number)) for x in sample):
                        numeric_columns.append(col)
        except:
            continue
else:
    st.sidebar.warning("⚠️ Aucune donnée disponible pour les filtres")

# Filtre par colonne de texte (si disponible)
if text_columns:
    search_column = st.sidebar.selectbox("Colonne à rechercher:", text_columns)
    keyword = st.sidebar.text_input("Rechercher un mot-clé")
else:
    keyword = ""
    search_column = None

# Filtre par date (si disponible)
if date_columns:
    date_column = st.sidebar.selectbox("Colonne de date:", date_columns)
    if df[date_column].notna().any():
        min_date = df[date_column].min()
        max_date = df[date_column].max()
        date_range = st.sidebar.date_input(
            "Période:",
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
    else:
        date_range = None
else:
    date_range = None

# Filtre par note (si disponible)
rating_filter = None
if 'note' in df.columns or 'rating' in df.columns:
    rating_col = 'note' if 'note' in df.columns else 'rating'
    if df[rating_col].notna().any():
        min_rating = int(df[rating_col].min())
        max_rating = int(df[rating_col].max())
        rating_range = st.sidebar.slider(
            "Filtrer par note:",
            min_value=min_rating,
            max_value=max_rating,
            value=(min_rating, max_rating)
        )
        rating_filter = rating_range

# Appliquer les filtres
filtered_df = df.copy()

if keyword and search_column:
    filtered_df = filtered_df[filtered_df[search_column].str.contains(keyword, case=False, na=False)]

if date_range and len(date_range) == 2 and date_columns:
    filtered_df = filtered_df[
        (filtered_df[date_column] >= pd.Timestamp(date_range[0])) &
        (filtered_df[date_column] <= pd.Timestamp(date_range[1]))
    ]

if rating_filter:
    filtered_df = filtered_df[
        (filtered_df[rating_col] >= rating_filter[0]) &
        (filtered_df[rating_col] <= rating_filter[1])
    ]

# Afficher le nombre de résultats filtrés
st.sidebar.metric("Résultats filtrés", len(filtered_df))

# ================================================================
# 📌 APERÇU DU DATASET
# ================================================================
st.subheader("📌 Aperçu du dataset")

# Vérifier si filtered_df n'est pas vide
if filtered_df.empty:
    st.warning("⚠️ Aucune donnée ne correspond aux filtres appliqués. Veuillez ajuster vos critères de filtrage.")
    st.stop()

# Calculer le pourcentage de données filtrées en évitant la division par zéro
if len(df) > 0:
    filtered_percentage = len(filtered_df) / len(df)
else:
    filtered_percentage = 0

st.write(f"Nombre de lignes : **{filtered_df.shape[0]}** (filtré: {filtered_percentage:.0%} du total)")
st.write(f"Nombre de colonnes : **{filtered_df.shape[1]}**")

with st.expander("Voir les premières lignes"):
    st.dataframe(filtered_df.head(), use_container_width=True)

with st.expander("Voir les statistiques descriptives"):
    if not filtered_df.empty:
        st.write(filtered_df.describe())
    else:
        st.write("Aucune statistique disponible.")

# ================================================================
# 🧹 PRÉTRAITEMENT AUTOMATIQUE DU TEXTE
# ================================================================
st.subheader("🧹 Prétraitement automatique du texte")

# Identifier les colonnes texte de manière robuste
text_cols = []
if filtered_df is not None and not filtered_df.empty:
    for col in filtered_df.columns:
        try:
            # Vérifier si la colonne contient du texte
            sample = filtered_df[col].dropna().head(5)
            if len(sample) > 0:
                # Vérifier si au moins une valeur est une string
                if any(isinstance(x, str) for x in sample):
                    text_cols.append(col)
        except:
            continue

if len(text_cols) == 0:
    st.error("❌ Aucune colonne texte trouvée dans les données filtrées.")
    st.write("**Conseil :** Vérifiez que votre dataset contient des colonnes avec du texte (commentaires, avis, descriptions, etc.)")
    st.stop()

st.info(f"🔍 Colonnes texte détectées : {', '.join(text_cols[:3])}{'...' if len(text_cols) > 3 else ''}")

# Nettoyer chaque colonne texte
for col in text_cols:
    filtered_df[col] = filtered_df[col].astype(str).apply(clean_text)

# Combiner toutes les colonnes texte en une seule
filtered_df["clean_text"] = filtered_df[text_cols].agg(" ".join, axis=1)

# Vérifier que le texte nettoyé n'est pas vide
if filtered_df["clean_text"].str.len().sum() == 0:
    st.warning("⚠️ Le texte nettoyé est vide. Vérifiez le contenu de vos données.")
else:
    st.success(f"✅ Texte nettoyé avec succès ({len(text_cols)} colonnes traitées)")

# ================================================================
# 🕵️ DÉTECTION DES FAUX AVIS
# ================================================================
st.header("🕵️ Détection des Faux Avis")

# Ajouter un contrôle pour ajuster le seuil de détection
col_thresh1, col_thresh2 = st.columns([1, 3])
with col_thresh1:
    detection_threshold = st.slider(
        "Seuil de détection", 
        min_value=0.1, 
        max_value=1.0, 
        value=0.6,
        step=0.05,
        help="Ajustez la sensibilité de détection des faux avis. Valeur plus basse = plus sensible."
    )

with col_thresh2:
    st.info(f"""
    **Paramètre actuel : {detection_threshold}**
    - **< 0.4** : Très sensible (détecte plus de faux avis)
    - **0.4-0.7** : Équilibre recommandé
    - **> 0.7** : Moins sensible (faux positifs réduits)
    """)

with st.spinner("Analyse des patterns suspects..."):
    is_fake, fake_scores, fake_reasons = detect_fake_reviews(
        filtered_df["clean_text"].tolist(), 
        threshold=detection_threshold  # Utiliser le seuil dynamique
    )
    filtered_df["is_fake"] = is_fake
    filtered_df["fake_score"] = fake_scores
    filtered_df["fake_reason"] = fake_reasons

# KPI de détection des faux avis (DOIT ÊTRE APRÈS LA DÉTECTION DYNAMIQUE)
fake_count = filtered_df["is_fake"].sum()
real_count = len(filtered_df) - fake_count
fake_percentage = fake_count / len(filtered_df) if len(filtered_df) > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total avis", len(filtered_df))
col2.metric("Faux avis", fake_count, f"{fake_percentage:.1%}")
col3.metric("Avis authentiques", real_count)
col4.metric("Score de confiance", f"{(1 - fake_percentage)*100:.1f}%")

# Afficher quelques exemples (DOIT ÊTRE APRÈS LES KPI)
st.subheader("🔍 Exemples d'analyse")

# Récupérer les exemples APRES la détection dynamique
fake_examples = filtered_df[filtered_df["is_fake"]].head(3)
real_examples = filtered_df[~filtered_df["is_fake"]].head(3)

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### ⚠️ Avis suspects détectés")
    if not fake_examples.empty:
        for idx, row in fake_examples.iterrows():
            # Récupérer le texte original (avant nettoyage)
            original_text = row.get('avis', row.get('review', 'Texte non disponible'))
            
            # Déterminer le niveau de risque basé sur le score
            fake_score = row['fake_score']
            if fake_score >= 0.8:
                risk_level = "🟥 HAUT RISQUE"
                risk_color = "#C0392B"
            elif fake_score >= 0.6:
                risk_level = "🟧 RISQUE MODÉRÉ"
                risk_color = "#E67E22"
            else:
                risk_level = "🟨 FAIBLE RISQUE"
                risk_color = "#F1C40F"
            
            # Formater la note
            rating = row.get('note', row.get('rating', 'N/A'))
            if isinstance(rating, (int, float)) and rating <= 5:
                rating_display = f"{rating}/5"
            else:
                rating_display = str(rating)
            
            st.markdown(f"""
            <div class="fake-review-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: {risk_color}; font-size: 1.1rem;">
                        {risk_level}
                    </strong>
                    <span style="background: {risk_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.9rem;">
                        Score: {fake_score:.2f}/1.0
                    </span>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>🔍 Raisons:</strong> {row['fake_reason']}
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>📝 Avis suspect:</strong> {original_text[:200]}{'...' if len(original_text) > 200 else ''}
                </div>
                <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px; font-size: 0.9rem;">
                    <div>
                        <strong>👤</strong> {row.get('utilisateur', row.get('user', 'Anonyme'))}
                    </div>
                    <div>
                        <strong>⭐</strong> {rating_display}
                    </div>
                    <div>
                        <strong>📅</strong> {row.get('date', 'Date non disponible')}
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #666;">
                    <strong>💡 Analyse:</strong> Cet avis présente {len(row['fake_reason'].split(', '))} caractéristiques suspectes.
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("""
        ✅ **Excellent ! Aucun faux avis détecté**
        
        **Vos données semblent authentiques :**
        - Tous les avis analysés paraissent légitimes
        - Aucun pattern suspect n'a été identifié
        - Score de confiance global élevé
        
        **💡 Recommandation :** Continuez à surveiller régulièrement vos avis pour maintenir cette qualité.
        """)

with col2:
    st.markdown("#### ✅ Avis authentiques")
    if not real_examples.empty:
        for idx, row in real_examples.iterrows():
            # Récupérer le texte original (avant nettoyage)
            original_text = row.get('avis', row.get('review', 'Texte non disponible'))
            
            # Déterminer le score de confiance (en pourcentage)
            confidence_score = (1 - row['fake_score']) * 100
            
            # Déterminer la couleur basée sur le score de confiance
            if confidence_score >= 80:
                confidence_color = "#2ECC71"  # Vert
                confidence_text = "Élevé"
            elif confidence_score >= 60:
                confidence_color = "#F1C40F"  # Jaune
                confidence_text = "Moyen"
            else:
                confidence_color = "#E67E22"  # Orange
                confidence_text = "Faible"
            
            # Formater la note
            rating = row.get('note', row.get('rating', 'N/A'))
            if isinstance(rating, (int, float)) and rating <= 5:
                rating_stars = "⭐" * int(rating)
                rating_display = f"{rating}/5 {rating_stars}"
            else:
                rating_display = str(rating)
            
            # Formater la date si disponible
            date_value = row.get('date', '')
            if pd.notna(date_value):
                if isinstance(date_value, (datetime, pd.Timestamp)):
                    formatted_date = date_value.strftime("%d/%m/%Y")
                else:
                    formatted_date = str(date_value)[:10]
            else:
                formatted_date = "Non disponible"
            
            st.markdown(f"""
            <div class="real-review-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: {confidence_color}; font-size: 1.1rem;">
                        🛡️ Confiance: {confidence_text} ({confidence_score:.0f}%)
                    </strong>
                    <span style="background: {confidence_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem;">
                        {row['fake_score']:.2f}/1.0
                    </span>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>📝 Avis:</strong> {original_text[:200]}{'...' if len(original_text) > 200 else ''}
                </div>
                <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <strong>👤</strong> {row.get('utilisateur', row.get('user', 'Anonyme'))}
                    </div>
                    <div>
                        <strong>⭐</strong> {rating_display}
                    </div>
                    <div>
                        <strong>📅</strong> {formatted_date}
                    </div>
                </div>
                {f'<div style="margin-top: 10px; font-size: 0.9rem; color: #666;"><strong>📊 Score de sentiment:</strong> {row.get("score_moyen", "N/A"):.2f}</div>' if "score_moyen" in row else ""}
            </div>
            """, unsafe_allow_html=True)
    else:
        # Afficher un message quand aucun avis authentique n'est détecté
        st.info("""
        **📊 Aucun avis authentique à afficher**
        
        Cela peut être dû à :
        1. Tous les avis ont été détectés comme suspects
        2. Le seuil de détection est trop bas
        3. Aucune donnée valide n'a été analysée
        
        **💡 Conseils :**
        - Ajustez le seuil de détection (actuellement à {detection_threshold})
        - Vérifiez la qualité des données
        - Consultez les statistiques de détection
        """.format(detection_threshold=detection_threshold))

# Graphique des faux avis
if fake_count > 0 or real_count > 0:
    fig_fake = px.pie(
        names=["Faux avis", "Avis authentiques"],
        values=[fake_count, real_count],
        title=f"Répartition des avis (Seuil: {detection_threshold})",
        color=["Faux avis", "Avis authentiques"],
        color_discrete_map={"Faux avis": "#E74C3C", "Avis authentiques": "#2ECC71"},
        hole=0.3
    )
    
    # Ajouter des annotations personnalisées
    fig_fake.update_traces(
        textinfo='percent+label',
        textposition='inside',
        hovertemplate="<b>%{label}</b><br>Quantité: %{value}<br>Pourcentage: %{percent}"
    )
    
    fig_fake.update_layout(
        annotations=[dict(
            text=f'Total: {len(filtered_df)}',
            x=0.5, y=0.5,
            font_size=20,
            showarrow=False
        )]
    )
    
    st.plotly_chart(fig_fake, use_container_width=True)
else:
    st.warning("⚠️ Aucune donnée disponible pour créer le graphique.")

# ================================================================
# 🤖 CHARGEMENT MODÈLES IA
# ================================================================
st.subheader("🤖 Chargement des modèles IA")
models = {
    "youtube": safe_load("model_youtube.sav"),
    "twitter": safe_load("model_tweets.sav"),
    "reviews": safe_load("model_reviews.sav")
}
vectorizers = {
    "youtube": safe_load("youtube_vectorizer.sav"),
    "twitter": safe_load("tweets_vectorizer.sav"),
    "reviews": safe_load("reviews_vectorizer.sav")
}

valid = [k for k in models if models[k] is not None and vectorizers[k] is not None]

if not valid:
    st.warning("⚠️ Aucun modèle IA chargé. Utilisation d'un scoring basique.")
    # Scoring basique basé sur les mots positifs/négatifs
    positive_words = ["excellent", "bon", "super", "parfait", "génial", "recommande", "satisfait", 
                      "impressionnant", "puissant", "confortable", "idéal", "magnifique"]
    negative_words = ["mauvais", "nul", "déçu", "éviter", "problème", "médiocre", "défectueux",
                      "regrette", "faible", "médiocre", "décharge", "manque"]
    
    def basic_sentiment_score(text):
        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count > neg_count:
            return 1, "positive"
        elif neg_count > pos_count:
            return -1, "negative"
        else:
            return 0, "neutral"
    
    filtered_df["score_moyen"] = filtered_df["clean_text"].apply(lambda x: basic_sentiment_score(x)[0])
    filtered_df["sentiment"] = filtered_df["clean_text"].apply(lambda x: basic_sentiment_score(x)[1])
else:
    # ================================================================
    # 📡 PRÉDICTIONS IA
    # ================================================================
    pred_cols = []
    for k in valid:
        try:
            X = vectorizers[k].transform(filtered_df["clean_text"])
            filtered_df[f"pred_{k}"] = models[k].predict(X)
            pred_cols.append(f"pred_{k}")
        except Exception as e:
            st.warning(f"Erreur avec le modèle {k}: {e}")
            filtered_df[f"pred_{k}"] = np.nan

    label_to_score = {"positive": 1, "neutral": 0, "negative": -1}

    def fusion(row):
        scores = []
        for c in pred_cols:
            v = row[c]
            if pd.notnull(v): scores.append(label_to_score.get(str(v), 0))
        return np.mean(scores) if scores else 0

    filtered_df["score_moyen"] = filtered_df.apply(fusion, axis=1)
    filtered_df["sentiment"] = filtered_df["score_moyen"].apply(lambda s: "positive" if s>0 else "negative" if s<0 else "neutral")

# ================================================================
# 📊 CALCUL DES KPI ET SCORES D'ENGAGEMENT
# ================================================================
st.header("📊 KPIs – Vue d'ensemble")

# Calcul des scores d'engagement
filtered_df["engagement_score"] = calculate_engagement_score(filtered_df)

# Identifier la colonne produit
product_columns = [col for col in filtered_df.columns if 'product' in col.lower() or 'produit' in col.lower() or 'item' in col.lower()]
product_col = product_columns[0] if product_columns else None

# Statistiques globales
total = len(filtered_df)
pos = (filtered_df["sentiment"]=="positive").sum()
neut = (filtered_df["sentiment"]=="neutral").sum()
neg = (filtered_df["sentiment"]=="negative").sum()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total messages", total)
col2.metric("Positifs", pos, f"{pos/total:.0%}" if total > 0 else "0%")
col3.metric("Neutres", neut, f"{neut/total:.0%}" if total > 0 else "0%")
col4.metric("Négatifs", neg, f"{neg/total:.0%}" if total > 0 else "0%")
col5.metric("Score AIM moyen", f"{filtered_df['score_moyen'].mean():.2f}" if total > 0 else "0.00")
col6.metric("Engagement moyen", f"{filtered_df['engagement_score'].mean():.1f}/5" if total > 0 else "0.0/5")

# ================================================================
# 📦 ANALYSE PAR PRODUIT (si disponible)
# ================================================================
if product_col and not filtered_df.empty:
    st.header("📦 Analyse par Produit")
    
    # KPI par produit
    product_stats = filtered_df.groupby(product_col).agg({
        "sentiment": lambda x: (x == "positive").mean(),
        "score_moyen": "mean",
        "engagement_score": "mean",
        "is_fake": "mean",
        "clean_text": "count"
    }).rename(columns={
        "sentiment": "Taux Positif",
        "score_moyen": "Score Moyen",
        "engagement_score": "Engagement Moyen",
        "is_fake": "Taux Faux Avis",
        "clean_text": "Nombre d'Avis"
    }).round(3)
    
    # Trier par taux positif
    product_stats = product_stats.sort_values("Taux Positif", ascending=False)
    
    st.dataframe(product_stats, use_container_width=True)
    
    # Graphique comparatif
    fig_products = px.bar(
        product_stats.reset_index(),
        x=product_col,
        y=["Taux Positif", "Engagement Moyen"],
        title="Comparaison des produits",
        barmode="group",
        color_discrete_sequence=AIM_PALETTE[:2]
    )
    st.plotly_chart(fig_products, use_container_width=True)

# ================================================================
# 📈 GRAPHIQUES ET VISUALISATIONS
# ================================================================

# ------------------ 1️⃣ Top 20 des mots ------------------
st.subheader("🔠 Top 20 des mots les plus fréquents")

# Ajouter des contrôles pour personnaliser l'analyse
with st.expander("⚙️ Paramètres d'analyse", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        min_word_length = st.slider(
            "Longueur minimale des mots", 
            min_value=2, 
            max_value=8, 
            value=4,
            help="Filtrer les mots trop courts qui sont souvent moins significatifs"
        )
    with col2:
        top_n_words = st.slider(
            "Nombre de mots à afficher", 
            min_value=10, 
            max_value=50, 
            value=20,
            help="Afficher plus ou moins de mots dans le graphique"
        )

# Vérifier si filtered_df["clean_text"] contient des données
if filtered_df["clean_text"].notna().any() and len(filtered_df["clean_text"]) > 0:
    # Récupérer tout le texte nettoyé
    all_text = " ".join(filtered_df["clean_text"].dropna().astype(str))
    
    if all_text.strip():  # Vérifier que le texte n'est pas vide
        # Tokeniser et compter les mots
        all_words = all_text.split()
        
        # Filtrer les mots courts et les stop words AVEC LE PARAMÈTRE DYNAMIQUE
        words = [w for w in all_words if len(w) >= min_word_length and w.lower() not in ENGLISH_STOP_WORDS]
        
        # Compter la fréquence
        wc = Counter(words)
        
        if wc:  # Vérifier que nous avons des mots
            # Récupérer les N mots les plus fréquents (dynamique)
            top_words_list = wc.most_common(top_n_words)
            
            # Créer le DataFrame pour le graphique
            freq_df = pd.DataFrame(top_words_list, columns=["Mot", "Fréquence"])
            
            # Créer le graphique à barres dynamique
            fig_words = px.bar(
                freq_df, 
                x="Mot", 
                y="Fréquence",
                title=f"🔠 Top {top_n_words} des mots les plus fréquents",
                color="Fréquence",
                color_continuous_scale=AIM_PALETTE,
                text="Fréquence"
            )
            
            # Améliorer l'apparence
            fig_words.update_traces(
                textposition='outside',
                marker_line_color='rgb(8,48,107)',
                marker_line_width=1.5
            )
            
            fig_words.update_layout(
                xaxis_tickangle=-45,
                xaxis_title="Mots",
                yaxis_title="Nombre d'occurrences",
                showlegend=False,
                hovermode='x unified'
            )
            
            # Afficher le graphique
            st.plotly_chart(fig_words, use_container_width=True, key="fig_words_top20")
            
            # Statistiques supplémentaires
            st.info(f"""
            **📊 Statistiques d'analyse :**
            - **Mots analysés :** {len(words):,} 
            - **Mots uniques :** {len(wc):,}
            - **Longueur minimale :** {min_word_length} caractères
            - **Top N affiché :** {top_n_words} mots
            - **Occurrences totales :** {sum(wc.values()):,}
            """)
            
            # Stocker wc dans session state pour l'utiliser plus tard
            st.session_state.wc = wc
            st.session_state.top_words_list = top_words_list
        else:
            st.warning("⚠️ Aucun mot significatif détecté après filtrage.")
            st.session_state.wc = Counter()
            st.session_state.top_words_list = []
    else:
        st.warning("⚠️ Le texte nettoyé est vide.")
        st.session_state.wc = Counter()
        st.session_state.top_words_list = []
else:
    st.warning("⚠️ Aucun texte disponible pour l'analyse.")
    st.session_state.wc = Counter()
    st.session_state.top_words_list = []

# ------------------ 2️⃣ Répartition des sentiments ------------------
st.subheader("📊 Répartition des sentiments")

if not filtered_df.empty and 'sentiment' in filtered_df.columns:
    sentiment_counts = filtered_df['sentiment'].value_counts()
    
    fig_sent = px.pie(
        values=sentiment_counts.values,
        names=sentiment_counts.index,
        title="Répartition des sentiments",
        color=sentiment_counts.index,
        color_discrete_map={
            "positive": "#2ECC71",
            "neutral": "#F1C40F",
            "negative": "#E74C3C"
        }
    )
    
    # Ajouter des annotations personnalisées
    fig_sent.update_traces(
        textinfo='percent+label+value',
        textposition='inside',
        hovertemplate="<b>%{label}</b><br>Quantité: %{value}<br>Pourcentage: %{percent}"
    )
    
    st.plotly_chart(fig_sent, use_container_width=True, key="fig_sentiment")
    
    # Statistiques détaillées
    col1, col2, col3 = st.columns(3)
    with col1:
        positive_pct = (sentiment_counts.get('positive', 0) / len(filtered_df)) * 100
        st.metric("Positifs", f"{sentiment_counts.get('positive', 0):,}", f"{positive_pct:.1f}%")
    with col2:
        neutral_pct = (sentiment_counts.get('neutral', 0) / len(filtered_df)) * 100
        st.metric("Neutres", f"{sentiment_counts.get('neutral', 0):,}", f"{neutral_pct:.1f}%")
    with col3:
        negative_pct = (sentiment_counts.get('negative', 0) / len(filtered_df)) * 100
        st.metric("Négatifs", f"{sentiment_counts.get('negative', 0):,}", f"{negative_pct:.1f}%")
    
    st.write("""
    **Objectif :** Ce diagramme circulaire montre la proportion de messages positifs, neutres et négatifs.
    Il donne une vue d'ensemble rapide de la tonalité générale des retours clients.
    """)
else:
    st.warning("⚠️ Aucune donnée de sentiment disponible.")

# ------------------ 3️⃣ Distribution du score de sentiment ------------------
st.subheader("📈 Distribution du score de sentiment")

if not filtered_df.empty and 'score_moyen' in filtered_df.columns:
    # Créer un histogramme dynamique avec curseur pour le nombre de bins
    col1, col2 = st.columns([3, 1])
    with col2:
        nbins = st.slider("Nombre d'intervalles:", min_value=10, max_value=50, value=30, key="nbins_slider")
    
    # Calculer des statistiques descriptives
    mean_score = filtered_df['score_moyen'].mean()
    median_score = filtered_df['score_moyen'].median()
    std_score = filtered_df['score_moyen'].std()
    
    fig_score = px.histogram(
        filtered_df, 
        x="score_moyen", 
        nbins=nbins,
        title=f"Distribution du score de sentiment ({nbins} intervalles)",
        color_discrete_sequence=AIM_PALETTE,
        labels={"score_moyen": "Score de sentiment", "count": "Nombre d'avis"},
        marginal="box"
    )
    
    # Ajouter des lignes verticales pour les statistiques
    fig_score.add_vline(x=mean_score, line_dash="dash", line_color="red", 
                        annotation_text=f"Moyenne: {mean_score:.2f}", 
                        annotation_position="top right")
    fig_score.add_vline(x=median_score, line_dash="dot", line_color="green", 
                        annotation_text=f"Médiane: {median_score:.2f}", 
                        annotation_position="top left")
    
    # Ajouter une boîte à moustaches séparée
    fig_box = px.box(
        filtered_df,
        y="score_moyen",
        title="Boîte à moustaches des scores de sentiment",
        color_discrete_sequence=AIM_PALETTE,
        points="all"
    )
    
    # Ajouter des annotations statistiques
    fig_box.add_annotation(
        x=0.5, y=filtered_df['score_moyen'].max(),
        text=f"Moyenne: {mean_score:.2f} | Écart-type: {std_score:.2f}",
        showarrow=False,
        font=dict(size=12)
    )
    
    tab1, tab2 = st.tabs(["📊 Histogramme + Boxplot", "📦 Boîte à moustaches détaillée"])
    with tab1:
        st.plotly_chart(fig_score, use_container_width=True)
    with tab2:
        st.plotly_chart(fig_box, use_container_width=True)
    
    # Distribution par sentiment
    st.subheader("📊 Distribution par catégorie de sentiment")
    
    if 'sentiment' in filtered_df.columns:
        fig_sent_dist = px.box(
            filtered_df,
            x="sentiment",
            y="score_moyen",
            color="sentiment",
            color_discrete_map={
                "positive": "#2ECC71",
                "neutral": "#F1C40F",
                "negative": "#E74C3C"
            },
            title="Distribution des scores par sentiment",
            points="all"
        )
        st.plotly_chart(fig_sent_dist, use_container_width=True)
    
    st.write(f"""
    **Objectif :** L'histogramme montre comment les scores de sentiment sont distribués.
    
    **📊 Statistiques descriptives :**
    - **Moyenne :** {mean_score:.3f} (tendance générale)
    - **Médiane :** {median_score:.3f} (valeur centrale)
    - **Écart-type :** {std_score:.3f} (dispersion des données)
    - **Minimum :** {filtered_df['score_moyen'].min():.3f}
    - **Maximum :** {filtered_df['score_moyen'].max():.3f}
    - **Étendue :** {filtered_df['score_moyen'].max() - filtered_df['score_moyen'].min():.3f}
    
    **🔍 Interprétation :**
    - **Scores négatifs (< 0)** : Avis défavorables
    - **Scores autour de 0** : Avis neutres  
    - **Scores positifs (> 0)** : Avis favorables
    
    La **ligne rouge pointillée** indique la moyenne générale. Une distribution centrée à droite indique une tendance positive, à gauche une tendance négative.
    """)
else:
    st.warning("⚠️ Aucun score de sentiment disponible pour l'analyse.")

# ------------------ 4️⃣ Statistiques descriptives en français ------------------
st.subheader("📋 Statistiques descriptives des scores")

# Calculer les statistiques
if not filtered_df.empty and 'score_moyen' in filtered_df.columns:
    # Statistiques de base
    stats_data = {
        "Métrique": [
            "Moyenne", "Médiane", "Écart-type", "Minimum", 
            "Maximum", "1er Quartile (Q1)", "3ème Quartile (Q3)", "Étendue",
            "Intervalle Interquartile", "Coefficient de variation"
        ],
        "Valeur": [
            f"{filtered_df['score_moyen'].mean():.3f}",
            f"{filtered_df['score_moyen'].median():.3f}",
            f"{filtered_df['score_moyen'].std():.3f}",
            f"{filtered_df['score_moyen'].min():.3f}",
            f"{filtered_df['score_moyen'].max():.3f}",
            f"{filtered_df['score_moyen'].quantile(0.25):.3f}",
            f"{filtered_df['score_moyen'].quantile(0.75):.3f}",
            f"{filtered_df['score_moyen'].max() - filtered_df['score_moyen'].min():.3f}",
            f"{filtered_df['score_moyen'].quantile(0.75) - filtered_df['score_moyen'].quantile(0.25):.3f}",
            f"{(filtered_df['score_moyen'].std() / filtered_df['score_moyen'].mean() * 100 if filtered_df['score_moyen'].mean() != 0 else 0):.1f}%"
        ],
        "Interprétation": [
            "Score moyen de tous les avis",
            "Valeur centrale (50% des scores sont inférieurs)",
            "Dispersion des scores autour de la moyenne",
            "Score le plus négatif",
            "Score le plus positif",
            "25% des scores sont inférieurs à cette valeur",
            "75% des scores sont inférieurs à cette valeur",
            "Différence entre les scores extrêmes",
            "Dispersion des 50% centraux des données",
            "Variabilité relative des scores"
        ]
    }

    stats_df = pd.DataFrame(stats_data)
    
    # Afficher dans un tableau stylisé
    st.markdown('<div class="statistics-table">', unsafe_allow_html=True)
    
    # Afficher sous forme de métriques aussi
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Moyenne", f"{filtered_df['score_moyen'].mean():.3f}")
    with col2:
        st.metric("Médiane", f"{filtered_df['score_moyen'].median():.3f}")
    with col3:
        st.metric("Écart-type", f"{filtered_df['score_moyen'].std():.3f}")
    with col4:
        st.metric("Étendue", f"{filtered_df['score_moyen'].max() - filtered_df['score_moyen'].min():.3f}")
    
    # Tableau détaillé
    st.dataframe(
        stats_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Métrique": st.column_config.TextColumn("Métrique", width="medium"),
            "Valeur": st.column_config.TextColumn("Valeur", width="small"),
            "Interprétation": st.column_config.TextColumn("Interprétation", width="large")
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Analyse de la distribution
    st.subheader("📊 Analyse de la distribution")
    
    # Calculer la skewness et kurtosis
    from scipy.stats import skew, kurtosis
    
    if len(filtered_df) > 1:
        skewness = skew(filtered_df['score_moyen'].dropna())
        kurt = kurtosis(filtered_df['score_moyen'].dropna())
        
        col1, col2 = st.columns(2)
        with col1:
            if skewness > 0.5:
                skew_interpretation = "Asymétrie positive (queue à droite)"
                skew_color = "#2ECC71"
            elif skewness < -0.5:
                skew_interpretation = "Asymétrie négative (queue à gauche)"
                skew_color = "#E74C3C"
            else:
                skew_interpretation = "Distribution symétrique"
                skew_color = "#F1C40F"
            
            st.metric("Asymétrie (Skewness)", f"{skewness:.3f}", skew_interpretation)
        
        with col2:
            if kurt > 3:
                kurt_interpretation = "Distribution leptokurtique (pic élevé)"
                kurt_color = "#E74C3C"
            elif kurt < 3:
                kurt_interpretation = "Distribution platykurtique (pic bas)"
                kurt_color = "#3498DB"
            else:
                kurt_interpretation = "Distribution normale"
                kurt_color = "#2ECC71"
            
            st.metric("Aplatissement (Kurtosis)", f"{kurt:.3f}", kurt_interpretation)
    
    # Tester la normalité avec QQ plot
    st.subheader("📈 Test de normalité (QQ Plot)")
    
    try:
        import scipy.stats as stats
        
        # Créer un QQ plot
        fig_qq = go.Figure()
        
        # Calculer les quantiles théoriques
        theoretical_quantiles = stats.probplot(filtered_df['score_moyen'].dropna(), dist="norm")
        
        fig_qq.add_trace(go.Scatter(
            x=theoretical_quantiles[0][0],
            y=theoretical_quantiles[0][1],
            mode='markers',
            name='Données',
            marker=dict(color=AIM_PALETTE[0], size=8)
        ))
        
        # Ajouter la ligne de référence (normale)
        fig_qq.add_trace(go.Scatter(
            x=[theoretical_quantiles[0][0].min(), theoretical_quantiles[0][0].max()],
            y=[theoretical_quantiles[0][0].min() * theoretical_quantiles[1][0] + theoretical_quantiles[1][1],
               theoretical_quantiles[0][0].max() * theoretical_quantiles[1][0] + theoretical_quantiles[1][1]],
            mode='lines',
            name='Loi normale',
            line=dict(color='red', dash='dash')
        ))
        
        fig_qq.update_layout(
            title="QQ Plot - Test de normalité",
            xaxis_title="Quantiles théoriques (normale)",
            yaxis_title="Quantiles observés",
            showlegend=True
        )
        
        st.plotly_chart(fig_qq, use_container_width=True)
        
        # Interprétation du QQ plot
        st.info("""
        **🔍 Interprétation du QQ Plot :**
        - **Points alignés sur la ligne rouge** : Distribution proche de la normale
        - **Points au-dessus de la ligne en queue droite** : Distribution avec queue lourde à droite
        - **Points au-dessous de la ligne en queue gauche** : Distribution avec queue lourde à gauche
        - **Courbure en S** : Distribution avec asymétrie
        """)
        
    except Exception as e:
        st.warning(f"⚠️ Impossible de créer le QQ plot : {e}")
else:
    st.warning("⚠️ Aucune statistique disponible pour les scores.")

# ------------------ 5️⃣ Heatmap : influence des mots ------------------
st.subheader("🔥 Influence des mots-clés sur le sentiment")

# Utiliser le wc stocké dans session state
if hasattr(st.session_state, 'wc') and len(st.session_state.wc) > 0:
    wc = st.session_state.wc
    top_words = [w for w, _ in wc.most_common(min(20, len(wc)))]
    
    # Calculer l'influence moyenne de chaque mot
    heat_data = {}
    word_stats = []
    
    for w in top_words:
        # Trouver les avis contenant ce mot
        mask = filtered_df["clean_text"].str.contains(r'\b' + w + r'\b', na=False)
        matching_rows = filtered_df[mask]
        
        if len(matching_rows) > 0:
            avg_score = matching_rows["score_moyen"].mean()
            count = len(matching_rows)
            sentiment_dist = matching_rows["sentiment"].value_counts().to_dict()
            
            heat_data[w] = [avg_score]
            word_stats.append({
                "Mot": w,
                "Fréquence": wc[w],
                "Score moyen": avg_score,
                "Occurrences": count,
                "Positifs": sentiment_dist.get('positive', 0),
                "Neutres": sentiment_dist.get('neutral', 0),
                "Négatifs": sentiment_dist.get('negative', 0)
            })
        else:
            heat_data[w] = [0]
    
    if heat_data:
        heat_df = pd.DataFrame(heat_data)
        
        fig_heat = px.imshow(
            heat_df,
            labels=dict(x="Mot-clé", y="", color="Score moyen"),
            x=heat_df.columns,
            y=["Score moyen"],
            color_continuous_scale="RdYlGn",
            title="🔥 Influence des mots-clés sur le sentiment",
            aspect="auto",
            text_auto=".2f"
        )
        
        fig_heat.update_layout(
            xaxis_tickangle=-45,
            height=300
        )
        
        st.plotly_chart(fig_heat, use_container_width=True, key="fig_heatmap")
        
        # Tableau détaillé des mots-clés
        st.subheader("📋 Analyse détaillée des mots-clés")
        
        if word_stats:
            word_stats_df = pd.DataFrame(word_stats)
            
            # Ajouter des colonnes calculées
            word_stats_df["% Positifs"] = (word_stats_df["Positifs"] / word_stats_df["Occurrences"] * 100).round(1)
            word_stats_df["% Négatifs"] = (word_stats_df["Négatifs"] / word_stats_df["Occurrences"] * 100).round(1)
            word_stats_df["Impact"] = word_stats_df["Score moyen"].apply(
                lambda x: "🟢 Positif" if x > 0.1 else "🔴 Négatif" if x < -0.1 else "🟡 Neutre"
            )
            
            # Trier par impact
            word_stats_df = word_stats_df.sort_values("Score moyen", ascending=False)
            
            # Afficher le tableau
            st.dataframe(
                word_stats_df,
                use_container_width=True,
                column_config={
                    "Mot": st.column_config.TextColumn("Mot-clé"),
                    "Fréquence": st.column_config.NumberColumn("Fréq. totale", format="%d"),
                    "Score moyen": st.column_config.NumberColumn("Score moyen", format="%.3f"),
                    "Occurrences": st.column_config.NumberColumn("Occurrences", format="%d"),
                    "% Positifs": st.column_config.NumberColumn("% Pos", format="%.1f%%"),
                    "% Négatifs": st.column_config.NumberColumn("% Nég", format="%.1f%%"),
                    "Impact": st.column_config.TextColumn("Impact")
                }
            )
        
        st.write("""
        **Objectif :** Cette heatmap montre l'influence moyenne de chaque mot-clé sur le sentiment.
        
        **🎨 Légende des couleurs :**
        - **🟢 Vert foncé** : Impact fortement positif (score > 0.5)
        - **🟢 Vert clair** : Impact positif modéré (0 < score ≤ 0.5)
        - **🟡 Jaune** : Impact neutre (score ≈ 0)
        - **🔴 Rouge clair** : Impact négatif modéré (-0.5 ≤ score < 0)
        - **🔴 Rouge foncé** : Impact fortement négatif (score < -0.5)
        
        **💡 Insights actionnables :**
        1. **Mots positifs** : À intégrer dans vos communications marketing
        2. **Mots négatifs** : À surveiller et adresser dans vos améliorations
        3. **Mots fréquents** : Reflètent les préoccupations principales des clients
        """)
        
        # Graphique supplémentaire : Mots les plus positifs/négatifs
        st.subheader("📊 Mots les plus influents sur le sentiment")
        
        if word_stats:
            # Top 10 mots positifs
            positive_words = word_stats_df[word_stats_df["Score moyen"] > 0].head(10)
            # Top 10 mots négatifs
            negative_words = word_stats_df[word_stats_df["Score moyen"] < 0].head(10)
            
            if not positive_words.empty:
                fig_pos = px.bar(
                    positive_words,
                    x="Mot",
                    y="Score moyen",
                    title="🔝 Top 10 des mots les plus positifs",
                    color="Score moyen",
                    color_continuous_scale="Greens",
                    text="Score moyen"
                )
                fig_pos.update_traces(texttemplate='%{text:.3f}', textposition='outside')
                st.plotly_chart(fig_pos, use_container_width=True)
            
            if not negative_words.empty:
                fig_neg = px.bar(
                    negative_words,
                    x="Mot",
                    y="Score moyen",
                    title="⚠️ Top 10 des mots les plus négatifs",
                    color="Score moyen",
                    color_continuous_scale="Reds",
                    text="Score moyen"
                )
                fig_neg.update_traces(texttemplate='%{text:.3f}', textposition='outside')
                st.plotly_chart(fig_neg, use_container_width=True)
    else:
        st.warning("⚠️ Données insuffisantes pour créer la heatmap.")
else:
    st.warning("⚠️ Aucun mot-clé disponible pour l'analyse d'influence.")

# ================================================================
# 🎪 OPPORTUNITÉS MARKETING DYNAMIQUES
# ================================================================
st.write("---")
st.header("🎪 Opportunités Marketing Détectées")

# Vérifier si wc existe dans session state
if hasattr(st.session_state, 'wc') and len(st.session_state.wc) > 0:
    wc = st.session_state.wc
    
    # Paramètres configurables pour les opportunités
    with st.expander("⚙️ Paramètres des opportunités", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            num_opportunities = st.slider(
                "Nombre d'opportunités à afficher",
                min_value=5,
                max_value=30,
                value=15,
                help="Choisissez le nombre d'opportunités marketing à analyser"
            )
        with col2:
            min_frequency = st.slider(
                "Fréquence minimale",
                min_value=1,
                max_value=10,
                value=2,
                help="Filtrez les mots trop peu fréquents"
            )
    
    # Filtrer les mots par fréquence minimale
    filtered_words = {word: freq for word, freq in wc.items() if freq >= min_frequency}
    
    if filtered_words:
        # Trier par fréquence
        top_words = Counter(filtered_words).most_common(num_opportunities)
        total_words_count = sum(filtered_words.values())
        
        # Calculer l'impact sentiment pour chaque mot
        word_opportunities = []
        for mot, freq in top_words:
            # Calculer le score sentiment moyen pour ce mot
            mask = filtered_df["clean_text"].str.contains(r'\b' + mot + r'\b', na=False)
            matching_rows = filtered_df[mask]
            
            if len(matching_rows) > 0:
                avg_score = matching_rows["score_moyen"].mean()
                sentiment_dist = matching_rows["sentiment"].value_counts().to_dict()
                positive_pct = (sentiment_dist.get('positive', 0) / len(matching_rows)) * 100
            else:
                avg_score = 0
                positive_pct = 0
            
            freq_percentage = (freq / total_words_count) * 100
            
            # Déterminer le type d'opportunité
            if freq_percentage > 5:
                opp_type = "🔥 Hot Trend"
                opp_color = "#FF5722"
                opp_icon = "🔥"
            elif freq_percentage > 2:
                opp_type = "📈 Opportunity"
                opp_color = "#FF9800"
                opp_icon = "📈"
            elif positive_pct > 70:
                opp_type = "💎 Gemme Positive"
                opp_color = "#4CAF50"
                opp_icon = "💎"
            elif positive_pct > 50:
                opp_type = "💡 Emerging"
                opp_color = "#2196F3"
                opp_icon = "💡"
            else:
                opp_type = "🔍 Niche"
                opp_color = "#9C27B0"
                opp_icon = "🔍"
            
            word_opportunities.append({
                "mot": mot,
                "freq": freq,
                "freq_percentage": freq_percentage,
                "avg_score": avg_score,
                "positive_pct": positive_pct,
                "opp_type": opp_type,
                "opp_color": opp_color,
                "opp_icon": opp_icon
            })
        
        # Trier par pertinence (combinaison fréquence et positivité)
        word_opportunities.sort(
            key=lambda x: (x['freq_percentage'] * 0.6 + x['positive_pct'] * 0.4), 
            reverse=True
        )
        
        # Afficher les opportunités en grille
        st.subheader(f"🔝 Top {len(word_opportunities)} Opportunités Marketing")
    
        
        # Graphique des opportunités par catégorie
        st.subheader("📊 Répartition des opportunités par catégorie")
        
        # Compter les opportunités par type
        opp_counts = {}
        for opp in word_opportunities:
            opp_type = opp['opp_type'].split()[-1]  # Prendre le dernier mot
            opp_counts[opp_type] = opp_counts.get(opp_type, 0) + 1
        
        if opp_counts:
            fig_opp_cat = px.pie(
                values=list(opp_counts.values()),
                names=list(opp_counts.keys()),
                title="Répartition des types d'opportunités",
                color_discrete_sequence=AIM_PALETTE
            )
            st.plotly_chart(fig_opp_cat, use_container_width=True)
        
        # Graphique Treemap des opportunités
        st.subheader("🗺️ Carte des opportunités marketing")
        
        opp_df = pd.DataFrame(word_opportunities)
        
        fig_opp_treemap = px.treemap(
            opp_df,
            path=["opp_type", "mot"],
            values="freq",
            title="🗺️ Carte des opportunités marketing par importance",
            color="positive_pct",
            color_continuous_scale="YlOrRd",
            hover_data=["freq", "freq_percentage", "avg_score", "positive_pct"]
        )
        
        fig_opp_treemap.update_traces(
            textinfo="label+value",
            texttemplate="<b>%{label}</b><br>%{value} occ."
        )
        
        st.plotly_chart(fig_opp_treemap, use_container_width=True)
        
        # Recommandations synthétiques basées sur les opportunités
        st.subheader("🎯 Recommandations stratégiques basées sur les opportunités")
        
        # Analyser les tendances
        high_freq_words = [opp for opp in word_opportunities if opp['freq_percentage'] > 3]
        high_positive_words = [opp for opp in word_opportunities if opp['positive_pct'] > 80]
        high_negative_words = [opp for opp in word_opportunities if opp['avg_score'] < -0.2]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if high_freq_words:
                st.info(f"""
                **📈 Tendances dominantes ({len(high_freq_words)})**
                - Mots les plus fréquemment utilisés
                - Reflètent les sujets principaux
                - Opportunité de capitalisation
                """)
        
        with col2:
            if high_positive_words:
                st.success(f"""
                **💎 Points forts ({len(high_positive_words)})**
                - Mots associés à des retours très positifs
                - Arguments marketing puissants
                - Atouts à mettre en avant
                """)
        
        with col3:
            if high_negative_words:
                st.warning(f"""
                **⚠️ Points de vigilance ({len(high_negative_words)})**
                - Mots associés à des retours négatifs
                - Zones d'amélioration prioritaires
                - Nécessitent une attention particulière
                """)
        
        # Recommandations détaillées
        st.info("""
        **📋 Synthèse des Opportunités Marketing :**
        
        **🎯 Stratégie recommandée :**
        1. **Capitaliser sur les mots positifs fréquents** : Intégrez-les dans vos campagnes
        2. **Adresser les préoccupations communes** : Travaillez sur les points négatifs récurrents
        3. **Surveiller les tendances émergentes** : Les mots en croissance sont des indicateurs précoces
        4. **Personnaliser le contenu** : Adaptez vos messages aux mots-clés identifiés
        
        **📊 Métriques clés de succès :**
        - **Engagement** : Augmentation des interactions avec le contenu ciblé
        - **Sentiment** : Amélioration du score moyen des retours
        - **Conversion** : Taux de conversion sur les campagnes optimisées
        - **Réputation** : Réduction des mentions négatives sur les points adressés
        """)
        
        # Télécharger les opportunités
        st.download_button(
            label="📥 Télécharger le rapport d'opportunités",
            data=pd.DataFrame(word_opportunities).to_csv(index=False, encoding='utf-8-sig'),
            file_name="opportunites_marketing_aim.csv",
            mime="text/csv"
        )
    else:
        st.warning(f"""
        ⚠️ **Aucune opportunité ne correspond aux critères**
        
        **Raisons possibles :**
        1. Fréquence minimale trop élevée (actuellement : {min_frequency})
        2. Données textuelles insuffisantes
        3. Texte trop diversifié sans mots récurrents
        
        **Suggestions :**
        - Réduisez la fréquence minimale
        - Augmentez le volume de données
        - Vérifiez la qualité du texte nettoyé
        """)
else:
    st.warning("""
    ⚠️ **Aucune opportunité marketing détectée**
    
    **Causes possibles :**
    1. Aucune donnée texte disponible
    2. Texte nettoyé vide ou insuffisant
    3. Problème d'analyse des mots-clés
    
    **Solutions :**
    - Vérifiez que votre dataset contient du texte
    - Assurez-vous que le prétraitement a fonctionné
    - Chargez plus de données pour une analyse significative
    """)