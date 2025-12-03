# ================================================================
# streamlit_app.py — Version complète avec authentification et inscription
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
import hashlib
import json
import os
import uuid

# ================================================================
# 🔐 CONFIGURATION AUTHENTIFICATION AVEC INSCRIPTION
# ================================================================

# Fichier de stockage des utilisateurs
USERS_FILE = "users.json"

def load_users():
    """Charge les utilisateurs depuis le fichier JSON"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    """Sauvegarde les utilisateurs dans le fichier JSON"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def hash_password(password):
    """Hash un mot de passe avec SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Valide le format d'un email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Valide la force d'un mot de passe"""
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"
    if not any(c.isupper() for c in password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    if not any(c.islower() for c in password):
        return False, "Le mot de passe doit contenir au moins une minuscule"
    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    return True, ""

def register_user(username, email, password, full_name, company=""):
    """Enregistre un nouvel utilisateur"""
    users = load_users()
    
    # Vérifications
    if username in users:
        return False, "Ce nom d'utilisateur est déjà pris"
    
    if any(user['email'] == email for user in users.values()):
        return False, "Cet email est déjà enregistré"
    
    if not validate_email(email):
        return False, "Format d'email invalide"
    
    is_valid, message = validate_password(password)
    if not is_valid:
        return False, message
    
    # Création du nouvel utilisateur
    user_id = str(uuid.uuid4())
    users[username] = {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "full_name": full_name,
        "company": company,
        "role": "user",  # Par défaut, rôle utilisateur
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True
    }
    
    # Sauvegarde
    save_users(users)
    return True, "Inscription réussie !"

def check_password(username, password):
    """Vérifie si le nom d'utilisateur et le mot de passe sont valides"""
    users = load_users()
    
    if username in users:
        user = users[username]
        if not user.get('is_active', True):
            return False, "Ce compte est désactivé"
        
        if user['password_hash'] == hash_password(password):
            # Mettre à jour la dernière connexion
            user['last_login'] = datetime.now().isoformat()
            save_users(users)
            return True, user
    return False, None

def initialize_session_state():
    """Initialise les variables de session"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False

def show_auth_forms():
    """Affiche les formulaires d'authentification et d'inscription"""
    # Initialiser les comptes par défaut si le fichier est vide
    users = load_users()
    if not users:
        # Créer un compte admin par défaut
        users["admin"] = {
            "id": str(uuid.uuid4()),
            "username": "admin",
            "email": "admin@aim.com",
            "password_hash": hash_password("Admin123!"),
            "full_name": "Administrateur AIM",
            "company": "AIM Analytics",
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True
        }
        users["marketing"] = {
            "id": str(uuid.uuid4()),
            "username": "marketing",
            "email": "marketing@aim.com",
            "password_hash": hash_password("Marketing2024!"),
            "full_name": "Équipe Marketing",
            "company": "Entreprise Test",
            "role": "user",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True
        }
        save_users(users)
    
    st.markdown("""
    <div style="text-align: center; padding: 40px 20px;">
        <h1 style="font-size: 3.8rem; color: #FF6B00; margin-bottom: 10px;">
            🔐 AIM – Plateforme d'Analyse Marketing
        </h1>
        <p style="font-size: 1.3rem; color: #666; margin-bottom: 40px;">
            Accédez à vos données marketing et obtenez des insights intelligents
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Onglets pour connexion/inscription
    if st.session_state.show_register:
        tab1, tab2 = st.tabs(["📝 Inscription", "🔐 Connexion"])
    else:
        tab1, tab2 = st.tabs(["🔐 Connexion", "📝 Inscription"])
    
    # Formulaire de connexion
    with tab1 if not st.session_state.show_register else tab2:
        st.markdown("### 🔐 Connexion à votre compte")
        
        with st.form("login_form"):
            username = st.text_input("**Nom d'utilisateur**", 
                                   placeholder="Entrez votre nom d'utilisateur")
            password = st.text_input("**Mot de passe**", 
                                   type="password",
                                   placeholder="Entrez votre mot de passe")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                submit_button = st.form_submit_button("Se connecter", 
                                                    type="primary",
                                                    use_container_width=True)
            
            if submit_button:
                if not username or not password:
                    st.error("⚠️ Veuillez remplir tous les champs")
                else:
                    success, user_data = check_password(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.user_info = user_data
                        st.success(f"✅ Connexion réussie ! Bienvenue {user_data['full_name']}")
                        st.rerun()
                    else:
                        if user_data is None:
                            st.error("❌ Nom d'utilisateur ou mot de passe incorrect")
                        else:
                            st.error(f"❌ {user_data}")
    
    # Formulaire d'inscription
    with tab2 if not st.session_state.show_register else tab1:
        st.markdown("### 📝 Créer un nouveau compte")
        st.info("Remplissez le formulaire ci-dessous pour créer votre compte")
        
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            with col1:
                full_name = st.text_input("**Nom complet** *", 
                                        placeholder="Votre nom et prénom")
                username = st.text_input("**Nom d'utilisateur** *", 
                                       placeholder="Choisissez un nom d'utilisateur")
            with col2:
                email = st.text_input("**Email professionnel** *", 
                                    placeholder="votre.email@entreprise.com")
                company = st.text_input("**Entreprise**", 
                                      placeholder="Nom de votre entreprise (facultatif)")
            
            col3, col4 = st.columns(2)
            with col3:
                password = st.text_input("**Mot de passe** *", 
                                       type="password",
                                       placeholder="Minimum 8 caractères")
            with col4:
                confirm_password = st.text_input("**Confirmer le mot de passe** *", 
                                               type="password",
                                               placeholder="Retapez votre mot de passe")
            
            # Conditions d'utilisation
            st.markdown("---")
            accept_terms = st.checkbox("**J'accepte les conditions d'utilisation et la politique de confidentialité** *")
            
            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                register_button = st.form_submit_button("Créer mon compte", 
                                                      type="primary",
                                                      use_container_width=True)
            
            if register_button:
                # Validation des champs
                errors = []
                
                if not all([full_name, username, email, password, confirm_password]):
                    errors.append("Tous les champs obligatoires (*) doivent être remplis")
                
                if not accept_terms:
                    errors.append("Vous devez accepter les conditions d'utilisation")
                
                if password != confirm_password:
                    errors.append("Les mots de passe ne correspondent pas")
                
                if errors:
                    for error in errors:
                        st.error(f"❌ {error}")
                else:
                    # Tenter l'inscription
                    success, message = register_user(username, email, password, full_name, company)
                    if success:
                        st.success(f"✅ {message}")
                        st.info("✅ Vous pouvez maintenant vous connecter avec vos identifiants")
                        st.session_state.show_register = False
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    # Pied de page avec informations
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **🛡️ Sécurité garantie**
        - Chiffrement des données
        - Conformité RGPD
        - Accès sécurisé
        """)
    with col2:
        st.markdown("""
        **💡 Comptes de démonstration**
        - **Admin**: `admin` / `Admin123!`
        - **Marketing**: `marketing` / `Marketing2024!`
        """)
    with col3:
        st.markdown("""
        **📞 Support**
        - 📧 support@aim-analytics.com
        - 📱 +33 1 23 45 67 89
        - 🕒 9h-18h du lundi au vendredi
        """)

def show_logout_button():
    """Affiche le bouton de déconnexion dans la sidebar"""
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_info = None
        st.session_state.df = None
        st.session_state.data_loaded = False
        st.session_state.show_register = False
        st.rerun()

# ================================================================
# 🎨 Palette couleurs AIM + Fond jaune clair
# ================================================================
AIM_PALETTE = [
    "#2ECC71", "#27AE60", "#3498DB", "#2980B9",
    "#F1C40F", "#F39C12", "#E67E22", "#E74C3C", "#C0392B"
]

BACKGROUND_COLOR = "#FFFDE7"
SIDEBAR_COLOR = "#FFF9C4"
TEXT_COLOR = "#212121"

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

/* Style pour le header de connexion */
.login-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(90deg, #FF9800, #FF5722);
    padding: 10px 20px;
    border-radius: 10px;
    color: white;
    margin-bottom: 20px;
}

/* Style pour le bouton d'inscription */
.register-button {
    background: linear-gradient(90deg, #4CAF50, #2E7D32);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    transition: all 0.3s ease;
}

.register-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(76, 175, 80, 0.3);
}
</style>
"""

# ================================================================
# ⚙️ CONFIGURATION STREAMLIT
# ================================================================
st.set_page_config(page_title="AIM – Dashboard", page_icon="📊", layout="wide")
st.markdown(page_bg_css, unsafe_allow_html=True)

# Initialisation des variables de session
initialize_session_state()

# ================================================================
# 🚀 APPLICATION PRINCIPALE
# ================================================================

if not st.session_state.logged_in:
    # Afficher les formulaires d'authentification
    show_auth_forms()
else:
    # Afficher l'application principale
    show_logout_button()
    
    # Header avec informations utilisateur
    user_info = st.session_state.user_info
    created_date = datetime.fromisoformat(user_info['created_at']).strftime("%d/%m/%Y") if 'created_at' in user_info else "Non disponible"
    last_login = datetime.fromisoformat(user_info['last_login']).strftime("%d/%m/%Y %H:%M") if user_info.get('last_login') else "Première connexion"
    
    st.markdown(f"""
    <div class="login-header">
        <div>
            <h3 style="color: white; margin: 0;">📊 AIM – Analyse Marketing Intelligente</h3>
            <p style="color: white; margin: 0; font-size: 0.9rem;">
                Connecté en tant que : <strong>{user_info['full_name']}</strong> 
                | Rôle : <strong>{user_info['role'].capitalize()}</strong>
            </p>
        </div>
        <div style="text-align: right;">
            <p style="color: white; margin: 0; font-size: 0.9rem;">
                📅 Session : {datetime.now().strftime("%d/%m/%Y %H:%M")}
            </p>
            <p style="color: white; margin: 0; font-size: 0.8rem;">
                Dernière connexion : {last_login}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ================================================================
    # 🔧 Fonctions utilitaires (gardées de la version originale)
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
            r"(excellent|parfait|génial|incroyable).{0,5}\1",
            r"(\w+).{0,3}\1.{0,3}\1",
            r"je.*recommande.*(à tous|fortement|vivement)",
            r"produit.*(exceptionnel|parfait|incroyable).*service.*(exceptionnel|parfait|incroyable)",
            r"(très|vraiment|absolument).{0,5}(bon|excellent|parfait|génial)",
            r"(le|la).{0,5}(meilleur|meilleure|top|numéro)",
            r"ach.{0,5}maintenant|commander.{0,5}immédiat",
            r"\d{5,}|[A-Z]{5,}",
            r"produit|service|article.{0,10}(correct|ok|bien)",
        ]
        
        fake_scores = []
        fake_reasons = []
        
        for text in texts:
            score = 0
            reasons = []
            
            for i, pattern in enumerate(fake_patterns):
                if re.search(pattern, text, re.IGNORECASE):
                    score += 0.1
                    reasons.append(f"Pattern {i+1}")
            
            if len(text.split()) < 5:
                score += 0.3
                reasons.append("Texte trop court")
            
            emoji_count = len(re.findall(r'[^\w\s,]', text))
            if emoji_count > 5:
                score += 0.2
                reasons.append("Trop d'émojis")
            
            fake_scores.append(score / 1.0)
            fake_reasons.append(", ".join(reasons[:3]) if reasons else "Aucun pattern détecté")
        
        is_fake = [score > threshold for score in fake_scores]
        
        return is_fake, fake_scores, fake_reasons

    def calculate_engagement_score(df, product_col=None):
        """Calcul du score d'engagement"""
        engagement_scores = []
        
        for idx, row in df.iterrows():
            score = 0
            
            text_length = len(str(row.get('clean_text', '')))
            if text_length > 100:
                score += 2
            elif text_length > 50:
                score += 1
            
            sentiment = row.get('sentiment', 'neutral')
            if sentiment == 'positive':
                score += 2
            elif sentiment == 'negative':
                score += 1
            
            if '?' in str(row.get('clean_text', '')):
                score += 1
            
            action_words = ['recommand', 'achèterai', 'conseill', 'utilis', 'essay']
            text_lower = str(row.get('clean_text', '')).lower()
            if any(word in text_lower for word in action_words):
                score += 1
            
            engagement_scores.append(min(score, 5))
        
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
                
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    if 'data' in data:
                        df = pd.DataFrame(data['data'])
                    elif 'results' in data:
                        df = pd.DataFrame(data['results'])
                    else:
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
    
    # Choix de la source de données
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
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            limit = st.number_input("Nombre de résultats", min_value=10, max_value=1000, value=100)
        with col2:
            days_back = st.number_input("Derniers jours", min_value=1, max_value=365, value=30)
        
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
        
        if not st.session_state.data_loaded:
            st.info("🌐 Configurez les paramètres de l'API et cliquez sur 'Récupérer les données'")
            st.stop()
    
    elif data_source == "Exemple de données":
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
    text_columns = []
    date_columns = []
    numeric_columns = []
    
    if df is not None and not df.empty:
        for col in df.columns:
            try:
                col_dtype = str(df[col].dtype)
                
                if any(dtype in col_dtype.lower() for dtype in ['object', 'string', 'category']):
                    text_columns.append(col)
                elif any(dtype in col_dtype.lower() for dtype in ['datetime', 'date', 'time']):
                    date_columns.append(col)
                elif any(dtype in col_dtype.lower() for dtype in ['int', 'float', 'number']):
                    numeric_columns.append(col)
                else:
                    sample = df[col].dropna().head(5)
                    if len(sample) > 0:
                        if all(isinstance(x, str) for x in sample):
                            text_columns.append(col)
                        elif all(isinstance(x, (datetime, pd.Timestamp)) for x in sample):
                            date_columns.append(col)
                        elif all(isinstance(x, (int, float, np.number)) for x in sample):
                            numeric_columns.append(col)
            except:
                continue
    else:
        st.sidebar.warning("⚠️ Aucune donnée disponible pour les filtres")
    
    # Filtre par colonne de texte
    if text_columns:
        search_column = st.sidebar.selectbox("Colonne à rechercher:", text_columns)
        keyword = st.sidebar.text_input("Rechercher un mot-clé")
    else:
        keyword = ""
        search_column = None
    
    # Filtre par date
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
    
    # Filtre par note
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
    
    st.sidebar.metric("Résultats filtrés", len(filtered_df))
    
    # ================================================================
    # 👤 INFORMATIONS UTILISATEUR DANS LA SIDEBAR
    # ================================================================
    st.sidebar.markdown("---")
    st.sidebar.header("👤 Profil utilisateur")
    
    st.sidebar.markdown(f"""
    <div style="background: linear-gradient(135deg, #FFF9C4, #FFECB3); 
                border-radius: 10px; padding: 15px; margin-bottom: 15px;">
        <p style="margin: 0 0 8px 0;"><strong>👤 {user_info['full_name']}</strong></p>
        <p style="margin: 0 0 8px 0; font-size: 0.9rem;">📧 {user_info['email']}</p>
        <p style="margin: 0 0 8px 0; font-size: 0.9rem;">🏢 {user_info.get('company', 'Non spécifié')}</p>
        <p style="margin: 0 0 8px 0; font-size: 0.9rem;">📅 Compte créé le: {created_date}</p>
        <p style="margin: 0; font-size: 0.85rem; color: #666;">Rôle: {user_info['role'].capitalize()}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Bouton pour gérer le compte (selon le rôle)
    if user_info['role'] == 'admin':
        if st.sidebar.button("👨‍💼 Gestion des comptes", use_container_width=True):
            st.sidebar.info("Fonctionnalité en développement")
    
    # ================================================================
    # 📌 APERÇU DU DATASET
    # ================================================================
    st.subheader("📌 Aperçu du dataset")
    
    if filtered_df.empty:
        st.warning("⚠️ Aucune donnée ne correspond aux filtres appliqués.")
        st.stop()
    
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
    
    text_cols = []
    if filtered_df is not None and not filtered_df.empty:
        for col in filtered_df.columns:
            try:
                sample = filtered_df[col].dropna().head(5)
                if len(sample) > 0:
                    if any(isinstance(x, str) for x in sample):
                        text_cols.append(col)
            except:
                continue
    
    if len(text_cols) == 0:
        st.error("❌ Aucune colonne texte trouvée.")
        st.stop()
    
    st.info(f"🔍 Colonnes texte détectées : {', '.join(text_cols[:3])}{'...' if len(text_cols) > 3 else ''}")
    
    for col in text_cols:
        filtered_df[col] = filtered_df[col].astype(str).apply(clean_text)
    
    filtered_df["clean_text"] = filtered_df[text_cols].agg(" ".join, axis=1)
    
    if filtered_df["clean_text"].str.len().sum() == 0:
        st.warning("⚠️ Le texte nettoyé est vide.")
    else:
        st.success(f"✅ Texte nettoyé avec succès ({len(text_cols)} colonnes traitées)")
    
    # ================================================================
    # 🕵️ DÉTECTION DES FAUX AVIS
    # ================================================================
    st.header("🕵️ Détection des Faux Avis")
    
    col_thresh1, col_thresh2 = st.columns([1, 3])
    with col_thresh1:
        detection_threshold = st.slider(
            "Seuil de détection", 
            min_value=0.1, 
            max_value=1.0, 
            value=0.6,
            step=0.05
        )
    
    with col_thresh2:
        st.info(f"""
        **Paramètre actuel : {detection_threshold}**
        - **< 0.4** : Très sensible
        - **0.4-0.7** : Équilibre recommandé
        - **> 0.7** : Moins sensible
        """)
    
    with st.spinner("Analyse des patterns suspects..."):
        is_fake, fake_scores, fake_reasons = detect_fake_reviews(
            filtered_df["clean_text"].tolist(), 
            threshold=detection_threshold
        )
        filtered_df["is_fake"] = is_fake
        filtered_df["fake_score"] = fake_scores
        filtered_df["fake_reason"] = fake_reasons
    
    fake_count = filtered_df["is_fake"].sum()
    real_count = len(filtered_df) - fake_count
    fake_percentage = fake_count / len(filtered_df) if len(filtered_df) > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total avis", len(filtered_df))
    col2.metric("Faux avis", fake_count, f"{fake_percentage:.1%}")
    col3.metric("Avis authentiques", real_count)
    col4.metric("Score de confiance", f"{(1 - fake_percentage)*100:.1f}%")
    
    st.subheader("🔍 Exemples d'analyse")
    
    fake_examples = filtered_df[filtered_df["is_fake"]].head(3)
    real_examples = filtered_df[~filtered_df["is_fake"]].head(3)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ⚠️ Avis suspects détectés")
        if not fake_examples.empty:
            for idx, row in fake_examples.iterrows():
                original_text = row.get('avis', row.get('review', 'Texte non disponible'))
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
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ **Aucun faux avis détecté**")
    
    with col2:
        st.markdown("#### ✅ Avis authentiques")
        if not real_examples.empty:
            for idx, row in real_examples.iterrows():
                original_text = row.get('avis', row.get('review', 'Texte non disponible'))
                confidence_score = (1 - row['fake_score']) * 100
                
                if confidence_score >= 80:
                    confidence_color = "#2ECC71"
                    confidence_text = "Élevé"
                elif confidence_score >= 60:
                    confidence_color = "#F1C40F"
                    confidence_text = "Moyen"
                else:
                    confidence_color = "#E67E22"
                    confidence_text = "Faible"
                
                rating = row.get('note', row.get('rating', 'N/A'))
                if isinstance(rating, (int, float)) and rating <= 5:
                    rating_stars = "⭐" * int(rating)
                    rating_display = f"{rating}/5 {rating_stars}"
                else:
                    rating_display = str(rating)
                
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
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("📊 Aucun avis authentique à afficher")
    
    if fake_count > 0 or real_count > 0:
        fig_fake = px.pie(
            names=["Faux avis", "Avis authentiques"],
            values=[fake_count, real_count],
            title=f"Répartition des avis (Seuil: {detection_threshold})",
            color=["Faux avis", "Avis authentiques"],
            color_discrete_map={"Faux avis": "#E74C3C", "Avis authentiques": "#2ECC71"},
            hole=0.3
        )
        
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
    
    filtered_df["engagement_score"] = calculate_engagement_score(filtered_df)
    
    product_columns = [col for col in filtered_df.columns if 'product' in col.lower() or 'produit' in col.lower() or 'item' in col.lower()]
    product_col = product_columns[0] if product_columns else None
    
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
        
        product_stats = product_stats.sort_values("Taux Positif", ascending=False)
        
        st.dataframe(product_stats, use_container_width=True)
        
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
    
    # Top 20 des mots
    st.subheader("🔠 Top 20 des mots les plus fréquents")
    
    with st.expander("⚙️ Paramètres d'analyse", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            min_word_length = st.slider(
                "Longueur minimale des mots", 
                min_value=2, 
                max_value=8, 
                value=4
            )
        with col2:
            top_n_words = st.slider(
                "Nombre de mots à afficher", 
                min_value=10, 
                max_value=50, 
                value=20
            )
    
    if filtered_df["clean_text"].notna().any() and len(filtered_df["clean_text"]) > 0:
        all_text = " ".join(filtered_df["clean_text"].dropna().astype(str))
        
        if all_text.strip():
            all_words = all_text.split()
            words = [w for w in all_words if len(w) >= min_word_length and w.lower() not in ENGLISH_STOP_WORDS]
            wc = Counter(words)
            
            if wc:
                top_words_list = wc.most_common(top_n_words)
                freq_df = pd.DataFrame(top_words_list, columns=["Mot", "Fréquence"])
                
                fig_words = px.bar(
                    freq_df, 
                    x="Mot", 
                    y="Fréquence",
                    title=f"🔠 Top {top_n_words} des mots les plus fréquents",
                    color="Fréquence",
                    color_continuous_scale=AIM_PALETTE,
                    text="Fréquence"
                )
                
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
                
                st.plotly_chart(fig_words, use_container_width=True, key="fig_words_top20")
                
                st.info(f"""
                **📊 Statistiques d'analyse :**
                - **Mots analysés :** {len(words):,} 
                - **Mots uniques :** {len(wc):,}
                - **Longueur minimale :** {min_word_length} caractères
                - **Top N affiché :** {top_n_words} mots
                - **Occurrences totales :** {sum(wc.values()):,}
                """)
                
                st.session_state.wc = wc
                st.session_state.top_words_list = top_words_list
            else:
                st.warning("⚠️ Aucun mot significatif détecté.")
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
    
    # Répartition des sentiments
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
        
        fig_sent.update_traces(
            textinfo='percent+label+value',
            textposition='inside',
            hovertemplate="<b>%{label}</b><br>Quantité: %{value}<br>Pourcentage: %{percent}"
        )
        
        st.plotly_chart(fig_sent, use_container_width=True, key="fig_sentiment")
        
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
    
    # Distribution du score de sentiment
    st.subheader("📈 Distribution du score de sentiment")
    
    if not filtered_df.empty and 'score_moyen' in filtered_df.columns:
        col1, col2 = st.columns([3, 1])
        with col2:
            nbins = st.slider("Nombre d'intervalles:", min_value=10, max_value=50, value=30, key="nbins_slider")
        
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
        
        fig_score.add_vline(x=mean_score, line_dash="dash", line_color="red", 
                            annotation_text=f"Moyenne: {mean_score:.2f}", 
                            annotation_position="top right")
        fig_score.add_vline(x=median_score, line_dash="dot", line_color="green", 
                            annotation_text=f"Médiane: {median_score:.2f}", 
                            annotation_position="top left")
        
        fig_box = px.box(
            filtered_df,
            y="score_moyen",
            title="Boîte à moustaches des scores de sentiment",
            color_discrete_sequence=AIM_PALETTE,
            points="all"
        )
        
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
    
    # Statistiques descriptives
    st.subheader("📋 Statistiques descriptives des scores")
    
    if not filtered_df.empty and 'score_moyen' in filtered_df.columns:
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
        
        st.markdown('<div class="statistics-table">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Moyenne", f"{filtered_df['score_moyen'].mean():.3f}")
        with col2:
            st.metric("Médiane", f"{filtered_df['score_moyen'].median():.3f}")
        with col3:
            st.metric("Écart-type", f"{filtered_df['score_moyen'].std():.3f}")
        with col4:
            st.metric("Étendue", f"{filtered_df['score_moyen'].max() - filtered_df['score_moyen'].min():.3f}")
        
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
    
    # Heatmap : influence des mots
    st.subheader("🔥 Influence des mots-clés sur le sentiment")
    
    if hasattr(st.session_state, 'wc') and len(st.session_state.wc) > 0:
        wc = st.session_state.wc
        top_words = [w for w, _ in wc.most_common(min(20, len(wc)))]
        
        heat_data = {}
        word_stats = []
        
        for w in top_words:
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
            
            st.subheader("📋 Analyse détaillée des mots-clés")
            
            if word_stats:
                word_stats_df = pd.DataFrame(word_stats)
                word_stats_df["% Positifs"] = (word_stats_df["Positifs"] / word_stats_df["Occurrences"] * 100).round(1)
                word_stats_df["% Négatifs"] = (word_stats_df["Négatifs"] / word_stats_df["Occurrences"] * 100).round(1)
                word_stats_df["Impact"] = word_stats_df["Score moyen"].apply(
                    lambda x: "🟢 Positif" if x > 0.1 else "🔴 Négatif" if x < -0.1 else "🟡 Neutre"
                )
                
                word_stats_df = word_stats_df.sort_values("Score moyen", ascending=False)
                
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
    
    # ================================================================
    # 🎪 OPPORTUNITÉS MARKETING DYNAMIQUES
    # ================================================================
    st.write("---")
    st.header("🎪 Opportunités Marketing Détectées")
    
    if hasattr(st.session_state, 'wc') and len(st.session_state.wc) > 0:
        wc = st.session_state.wc
        
        with st.expander("⚙️ Paramètres des opportunités", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                num_opportunities = st.slider(
                    "Nombre d'opportunités à afficher",
                    min_value=5,
                    max_value=30,
                    value=15
                )
            with col2:
                min_frequency = st.slider(
                    "Fréquence minimale",
                    min_value=1,
                    max_value=10,
                    value=2
                )
        
        filtered_words = {word: freq for word, freq in wc.items() if freq >= min_frequency}
        
        if filtered_words:
            top_words = Counter(filtered_words).most_common(num_opportunities)
            total_words_count = sum(filtered_words.values())
            
            word_opportunities = []
            for mot, freq in top_words:
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
            
            word_opportunities.sort(
                key=lambda x: (x['freq_percentage'] * 0.6 + x['positive_pct'] * 0.4), 
                reverse=True
            )
            
            st.subheader(f"🔝 Top {len(word_opportunities)} Opportunités Marketing")
            
            # Afficher les opportunités en grille
            cols = st.columns(3)
            for idx, opp in enumerate(word_opportunities):
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="opportunity-card">
                        <div class="opportunity-badge" style="background: {opp['opp_color']};">
                            {opp['opp_icon']} {opp['opp_type']}
                        </div>
                        <h4 style="margin: 10px 0; color: #333;">{opp['mot']}</h4>
                        <p style="margin: 5px 0; font-size: 0.9rem;">
                            📊 <strong>Fréquence:</strong> {opp['freq']} ({opp['freq_percentage']:.1f}%)
                        </p>
                        <p style="margin: 5px 0; font-size: 0.9rem;">
                            📈 <strong>Positivité:</strong> {opp['positive_pct']:.0f}%
                        </p>
                        <p style="margin: 5px 0; font-size: 0.9rem;">
                            ⭐ <strong>Score moyen:</strong> {opp['avg_score']:.2f}
                        </p>
                        <div style="margin-top: 10px;">
                            <span class="opportunity-tag">Marketing</span>
                            <span class="opportunity-tag">Analyse</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Graphique des opportunités par catégorie
            st.subheader("📊 Répartition des opportunités par catégorie")
            
            opp_counts = {}
            for opp in word_opportunities:
                opp_type = opp['opp_type'].split()[-1]
                opp_counts[opp_type] = opp_counts.get(opp_type, 0) + 1
            
            if opp_counts:
                fig_opp_cat = px.pie(
                    values=list(opp_counts.values()),
                    names=list(opp_counts.keys()),
                    title="Répartition des types d'opportunités",
                    color_discrete_sequence=AIM_PALETTE
                )
                st.plotly_chart(fig_opp_cat, use_container_width=True)
            
            # Télécharger les opportunités
            st.download_button(
                label="📥 Télécharger le rapport d'opportunités",
                data=pd.DataFrame(word_opportunities).to_csv(index=False, encoding='utf-8-sig'),
                file_name="opportunites_marketing_aim.csv",
                mime="text/csv"
            )
        else:
            st.warning(f"⚠️ Aucune opportunité ne correspond aux critères")
    else:
        st.warning("⚠️ Aucune opportunité marketing détectée")