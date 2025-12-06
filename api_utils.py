# api_utils.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import hashlib
import json
import os
import uuid
import re
import secrets
import string
from datetime import datetime

# Fichier pour stocker les utilisateurs
USERS_FILE = "users.json"

# Fichier pour la configuration AIM
AIM_CONFIG_FILE = "aim_config.json"

# ==================== FONCTIONS DE GESTION DES UTILISATEURS ====================

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
    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    return True, ""

def create_user_response(user_data):
    """Crée une réponse utilisateur sans informations sensibles"""
    return {
        "id": user_data.get("id"),
        "username": user_data.get("username"),
        "email": user_data.get("email"),
        "full_name": user_data.get("full_name", user_data.get("username")),
        "company": user_data.get("company", ""),
        "role": user_data.get("role", "marketing"),
        "created_at": user_data.get("created_at"),
        "last_login": user_data.get("last_login"),
        "is_active": user_data.get("is_active", True)
    }

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

def generate_random_password(length=12):
    """Génère un mot de passe aléatoire sécurisé"""
    # Définition des caractères
    letters = string.ascii_letters
    digits = string.digits
    special_chars = "!@#$%&*"
    
    # Assurer au moins un caractère de chaque type
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(digits),
        secrets.choice(special_chars)
    ]
    
    # Remplir le reste avec des caractères aléatoires
    all_chars = letters + digits + special_chars
    password += [secrets.choice(all_chars) for _ in range(length - 4)]
    
    # Mélanger
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

def admin_register_user(username, email, role, full_name="", company=""):
    """Fonction d'inscription réservée à l'admin"""
    users = load_users()
    
    if username in users:
        return False, "Ce nom d'utilisateur est déjà pris"
    
    for user in users.values():
        if user['email'].lower() == email.lower():
            return False, "Cet email est déjà enregistré"
    
    if not validate_email(email):
        return False, "Format d'email invalide"
    
    # Générer mot de passe aléatoire
    password = generate_random_password()
    password_hash = hash_password(password)
    
    # Créer l'utilisateur
    user_id = str(uuid.uuid4())
    users[username] = {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name if full_name else username,
        "company": company,
        "role": role,
        "created_by": "admin",
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True,
        "password_changed": False
    }
    
    save_users(users)
    
    # Retourner aussi le mot de passe en clair pour l'envoyer par mail
    return True, {
        "message": "Utilisateur créé avec succès",
        "user": create_user_response(users[username]),
        "generated_password": password
    }

def check_credentials(identifier, password):
    """Vérifie les identifiants de connexion"""
    users = load_users()
    
    user_data = None
    for username, user in users.items():
        if user['email'].lower() == identifier.lower() or username.lower() == identifier.lower():
            user_data = user
            break
    
    if user_data:
        if not user_data.get('is_active', True):
            return False, "Ce compte est désactivé"
        
        if user_data['password_hash'] == hash_password(password):
            user_data['last_login'] = datetime.now().isoformat()
            users[user_data['username']] = user_data
            save_users(users)
            return True, user_data
    
    return False, None

def check_first_login(username):
    """Vérifie si c'est la première connexion (mot de passe temporaire)"""
    users = load_users()
    
    if username in users:
        user = users[username]
        return not user.get('password_changed', False)
    
    return False

def change_password(username, current_password, new_password):
    """Permet à l'utilisateur de changer son mot de passe"""
    users = load_users()
    
    if username not in users:
        return False, "Utilisateur non trouvé"
    
    user = users[username]
    
    # Vérifier le mot de passe actuel
    if user['password_hash'] != hash_password(current_password):
        return False, "Mot de passe actuel incorrect"
    
    # Valider le nouveau mot de passe
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return False, message
    
    # Mettre à jour
    user['password_hash'] = hash_password(new_password)
    user['password_changed'] = True
    users[username] = user
    save_users(users)
    
    return True, "Mot de passe changé avec succès"

def send_welcome_email(email, username, password, full_name=""):
    """Simule l'envoi d'un email de bienvenue"""
    welcome_message = f"""
    ============================================
    BIENVENUE SUR LA PLATEFORME AIM
    ============================================
    
    Cher(e) {full_name or username},
    
    Votre compte a été créé avec succès.
    
    Vos identifiants de connexion :
    • Email / Username : {username}
    • Mot de passe temporaire : {password}
    • URL de connexion : http://localhost:8501
    
    IMPORTANT : 
    1. Connectez-vous dès que possible
    2. Changez votre mot de passe à la première connexion
    3. Conservez ces informations en lieu sûr
    
    Cordialement,
    L'équipe d'administration AIM
    ============================================
    """
    
    # Pour le prototype, on affiche dans les logs
    print(f"\n📧 EMAIL À ENVOYER À: {email}")
    print(welcome_message)
    print("(En production, cet email serait envoyé via SMTP)")
    
    return True

def toggle_user_status(username, current_admin):
    """Active/désactive un utilisateur (sauf l'admin actuel)"""
    users = load_users()
    
    if username == current_admin:
        return False, "Vous ne pouvez pas désactiver votre propre compte"
    
    if username in users:
        users[username]['is_active'] = not users[username].get('is_active', True)
        save_users(users)
        status = "activé" if users[username]['is_active'] else "désactivé"
        return True, f"Utilisateur {username} {status}"
    
    return False, "Utilisateur non trouvé"

def reset_user_password(username):
    """Réinitialise le mot de passe d'un utilisateur"""
    users = load_users()
    
    if username in users:
        new_password = generate_random_password()
        users[username]['password_hash'] = hash_password(new_password)
        users[username]['password_changed'] = False
        save_users(users)
        return True, {
            "message": f"Mot de passe réinitialisé pour {username}",
            "new_password": new_password
        }
    
    return False, "Utilisateur non trouvé"

def delete_user(username, current_admin):
    """Supprime un utilisateur (sauf l'admin actuel)"""
    users = load_users()
    
    if username == current_admin:
        return False, "Vous ne pouvez pas supprimer votre propre compte"
    
    if username in users:
        del users[username]
        save_users(users)
        return True, f"Utilisateur {username} supprimé avec succès"
    
    return False, "Utilisateur non trouvé"

# ==================== FONCTIONS D'INTERFACE ET VISUALISATION ====================

# CSS pour le background
def page_bg_css():
    """CSS pour le background"""
    return """
    <style>
    .stApp {
        background: #f8f9fa;
    }
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
    }
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1.5rem;
    }
    .interpretation-box {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #6554C0;
        margin-top: 1rem;
        font-size: 0.9em;
        color: #495057;
    }
    .recommendation-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #e5e7eb;
    }
    .role-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 600;
        margin-top: 5px;
    }
    .analyst-badge {
        background: rgba(101, 84, 192, 0.1);
        color: #6554C0;
    }
    .marketing-badge {
        background: rgba(54, 179, 126, 0.1);
        color: #36B37E;
    }
    .admin-badge {
        background: rgba(255, 86, 48, 0.1);
        color: #FF5630;
    }
    /* Nouveau CSS pour la gestion des utilisateurs */
    .user-table-row {
        background: white;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 8px;
        border-left: 4px solid #6554C0;
        transition: all 0.3s ease;
    }
    .user-table-row:hover {
        box-shadow: 0 4px 12px rgba(101, 84, 192, 0.15);
        transform: translateY(-2px);
    }
    .user-role-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75em;
        font-weight: 600;
        text-transform: uppercase;
    }
    .role-admin {
        background: #FFEBEE;
        color: #C62828;
    }
    .role-analyst {
        background: #E8EAF6;
        color: #3949AB;
    }
    .role-marketing {
        background: #E8F5E9;
        color: #2E7D32;
    }
    .status-active {
        color: #4CAF50;
        font-weight: bold;
    }
    .status-inactive {
        color: #F44336;
        font-weight: bold;
    }
    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }
    .modal-content {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        max-width: 500px;
        width: 90%;
        max-height: 90vh;
        overflow-y: auto;
    }
    </style>
    """

def create_kpi_card(title, value, color, subtitle):
    """Crée une carte KPI avec design moderne"""
    return f"""
    <div style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #E5E7EB; text-align: center;">
        <div style="font-size: 0.9em; color: #6B7280; margin-bottom: 8px;">{title}</div>
        <div style="font-size: 2em; font-weight: 700; color: {color}; margin-bottom: 5px;">{value}</div>
        <div style="font-size: 0.8em; color: #9CA3AF;">{subtitle}</div>
    </div>
    """

def create_trend_chart(data, date_col, metric_col):
    """Crée un graphique de tendance"""
    try:
        # Trier par date
        sorted_data = data.sort_values(date_col)
        
        fig = px.line(
            sorted_data,
            x=date_col,
            y=metric_col,
            title=f"Évolution de {metric_col}",
            markers=True
        )
        
        # Calculer la tendance
        if len(sorted_data) > 1:
            first_val = sorted_data[metric_col].iloc[0]
            last_val = sorted_data[metric_col].iloc[-1]
            change = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0
            
            interpretation = f"Tendance : {change:+.1f}% de changement"
        else:
            interpretation = "Données insuffisantes pour analyser la tendance"
        
        return fig, interpretation
    except Exception as e:
        return None, f"Erreur dans la création du graphique: {str(e)}"

def create_bar_chart(data, column, title):
    """Crée un graphique en barres"""
    try:
        value_counts = data[column].value_counts().head(10)
        
        fig = px.bar(
            x=value_counts.index,
            y=value_counts.values,
            title=title,
            labels={'x': column, 'y': 'Count'}
        )
        
        interpretation = f"Top {len(value_counts)} valeurs pour {column}"
        return fig, interpretation
    except Exception as e:
        return None, f"Erreur dans la création du graphique: {str(e)}"

def create_sentiment_chart(data):
    """Crée un graphique de répartition des sentiments"""
    if 'sentiment' not in data.columns:
        return None, "Aucune donnée de sentiment disponible"
    
    sentiment_counts = data['sentiment'].value_counts()
    
    fig = px.pie(
        values=sentiment_counts.values,
        names=sentiment_counts.index,
        title="Répartition des sentiments",
        color_discrete_sequence=['#36B37E', '#FF5630', '#FFAB00', '#6554C0']
    )
    
    interpretation = f"Analyse des {len(data)} avis. {sentiment_counts.get('positif', 0)} positifs, {sentiment_counts.get('négatif', 0)} négatifs."
    return fig, interpretation

def create_fake_review_analysis(data, text_col):
    """Analyse des faux avis"""
    if 'faux_avis' not in data.columns:
        return [], []
    
    fake_count = data['faux_avis'].sum()
    total = len(data)
    
    # Graphique 1: Répartition faux vs vrais
    labels = ['Vrais Avis', 'Faux Avis']
    values = [total - fake_count, fake_count]
    
    fig1 = px.pie(
        values=values,
        names=labels,
        title="Répartition Faux vs Vrais Avis",
        color_discrete_sequence=['#36B37E', '#FF5630']
    )
    
    interp1 = f"{fake_count} faux avis détectés ({fake_count/total*100:.1f}%)"
    
    # Graphique 2: Faux avis par sentiment (si disponible)
    visualizations = [fig1]
    interpretations = [interp1]
    
    if 'sentiment' in data.columns:
        fake_by_sentiment = data[data['faux_avis'] == True]['sentiment'].value_counts()
        if len(fake_by_sentiment) > 0:
            fig2 = px.bar(
                x=fake_by_sentiment.index,
                y=fake_by_sentiment.values,
                title="Faux avis par sentiment",
                color=fake_by_sentiment.index,
                color_discrete_sequence=['#FF5630', '#FFAB00', '#6554C0']
            )
            fig2.update_layout(showlegend=False)
            visualizations.append(fig2)
            interpretations.append("Répartition des faux avis par catégorie de sentiment")
    
    return visualizations, interpretations

# ==================== FONCTIONS AIM (SIMULÉES) ====================

def analyser_sentiment(text):
    """Analyse le sentiment d'un texte (version simulée)"""
    if not text or pd.isna(text):
        return "neutre"
    
    text = str(text).lower()
    positif_words = ['bon', 'excellent', 'super', 'génial', 'parfait', 'recommandé']
    negatif_words = ['mauvais', 'nul', 'horrible', 'déçu', 'décevant', 'éviter']
    
    if any(word in text for word in positif_words):
        return "positif"
    elif any(word in text for word in negatif_words):
        return "négatif"
    else:
        return "neutre"

def detecter_faux_avis(text, seuil=0.7):
    """Détecte si un avis est faux (version simulée)"""
    if not text or pd.isna(text):
        return False
    
    text = str(text)
    # Simuler une détection basée sur la longueur et la répétition
    if len(text) < 10:
        return True
    if text.count('!') > 3:
        return True
    if any(word*3 in text for word in ['très', 'super', 'incroyable']):
        return True
    
    return np.random.random() < 0.1  # 10% de faux avis aléatoires

def generer_recommandations(data, text_col):
    """Génère des recommandations marketing (version simulée)"""
    recommendations = [
        "Mettre en avant les avis positifs sur la page d'accueil",
        "Créer un FAQ basé sur les points négatifs récurrents",
        "Implémenter un système de vérification des avis",
        "Segmenter les clients par sentiment pour des campagnes ciblées",
        "Former l'équipe support sur les retours négatifs fréquents",
        "Créer du contenu éducatif basé sur les questions des clients"
    ]
    
    return recommendations[:4]  # Retourne 4 recommandations

# ==================== FONCTIONS DE CONFIGURATION AIM ====================

def load_aim_config():
    """Charge la configuration AIM depuis le fichier JSON"""
    if os.path.exists(AIM_CONFIG_FILE):
        try:
            with open(AIM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            # Configuration par défaut
            return {
                'modules': {
                    'fake_review_detection': {
                        'threshold': 0.7,
                        'active': True,
                        'auto_delete': False
                    },
                    'sentiment_analysis': {
                        'model': 'VADER (recommandé)',
                        'auto_analyze': True
                    },
                    'recommendations': {
                        'frequency': 'Hebdomadaire',
                        'auto_generate': True,
                        'alert_threshold': 0.3
                    }
                },
                'system': {
                    'max_file_size': 100,
                    'auto_backup': True,
                    'backup_frequency': 'Hebdomadaire'
                }
            }
    else:
        # Retourner la configuration par défaut
        return {
            'modules': {
                'fake_review_detection': {
                    'threshold': 0.7,
                    'active': True,
                    'auto_delete': False
                },
                'sentiment_analysis': {
                    'model': 'VADER (recommandé)',
                    'auto_analyze': True
                },
                'recommendations': {
                    'frequency': 'Hebdomadaire',
                    'auto_generate': True,
                    'alert_threshold': 0.3
                }
            },
            'system': {
                'max_file_size': 100,
                'auto_backup': True,
                'backup_frequency': 'Hebdomadaire'
            }
        }

def save_aim_config(config):
    """Sauvegarde la configuration AIM dans le fichier JSON"""
    with open(AIM_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)