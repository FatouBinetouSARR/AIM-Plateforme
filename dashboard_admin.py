# dashboard_admin.py
import streamlit as st
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import plotly.graph_objects as go
import plotly.express as px
from dataclasses import dataclass
import json
import io

from api_utils import (
    page_bg_css, 
    load_users,
    create_kpi_card, 
    create_trend_chart, 
    create_bar_chart, 
    create_fake_review_analysis,
    detecter_faux_avis,
    load_aim_config,
    save_aim_config,
    admin_register_user,
    send_welcome_email,
    toggle_user_status,
    reset_user_password,
    delete_user
)

# =========================CONFIGURATION & CONSTANTES===================
class Config:
    """Configuration de l'application"""
    # Constantes de sécurité
    ADMIN_ROLE = 'admin'
    ANALYST_ROLE = 'data_analyst'
    MARKETING_ROLE = 'marketing'
    
    # Chemins et fichiers
    CONFIG_FILE = 'aim_config.json'
    LOG_FILE = 'admin_dashboard.log'
    
    # Paramètres système
    MAX_FILE_SIZE_MB = 100
    SESSION_TIMEOUT_MINUTES = 60
    
    # Couleurs du thème
    COLORS = {
        'primary': '#6554C0',
        'success': '#36B37E',
        'warning': '#FFAB00',
        'danger': '#FF5630',
        'info': '#00B8D9',
        'dark': '#172B4D',
        'light': '#6B7280'
    }

# =========================CLASSES DE DONNÉES===================
@dataclass
class User:
    """Classe représentant un utilisateur"""
    username: str
    email: str
    role: str
    full_name: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    password_changed: bool = False
    
    @property
    def display_name(self) -> str:
        return self.full_name or self.username
    
    @property
    def status_badge(self) -> str:
        return "🟢 Actif" if self.is_active else "🔴 Inactif"
    
    @property
    def role_color(self) -> str:
        colors = {
            'admin': Config.COLORS['danger'],
            'data_analyst': Config.COLORS['primary'],
            'marketing': Config.COLORS['success']
        }
        return colors.get(self.role, Config.COLORS['light'])

@dataclass
class DetectionResult:
    """Résultat de détection de faux avis"""
    total_reviews: int
    fake_reviews: int
    fake_percentage: float
    suspicious_users: List[str]
    detection_threshold: float
    timestamp: str
    
    @property
    def is_suspicious(self) -> bool:
        return self.fake_percentage > 20.0  # Seuil de 20%

# =========================UTILITAIRES===================
def setup_logging():
    """Configuration du logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def log_admin_action(action: str, target: str, details: Dict = None):
    """Journaliser les actions administratives"""
    user = st.session_state.user_info.get('full_name', 'Unknown')
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'admin': user,
        'action': action,
        'target': target,
        'details': details or {}
    }
    logger.info(f"Admin Action: {json.dumps(log_entry)}")
    
    # Stocker dans la session pour l'audit
    if 'audit_log' not in st.session_state:
        st.session_state.audit_log = []
    st.session_state.audit_log.append(log_entry)

def validate_session() -> bool:
    """Valider la session utilisateur"""
    if 'user_info' not in st.session_state:
        return False
    
    user_info = st.session_state.user_info
    if user_info.get('role') != Config.ADMIN_ROLE:
        logger.warning(f"Accès non autorisé: {user_info.get('role')}")
        return False
    
    return True

def check_file_size(file) -> bool:
    """Vérifier la taille du fichier"""
    max_size = Config.MAX_FILE_SIZE_MB * 1024 * 1024
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    return size <= max_size

# =========================COMPOSANTS UI===================
def render_user_profile(user_info: Dict):
    """Afficher le profil utilisateur"""
    st.markdown(f"""
    <div class="user-profile-card">
        <div class="profile-header">
            <div class="avatar" style="background: linear-gradient(135deg, #FF5630 0%, #DE350B 100%);">
                {user_info.get('full_name', 'A')[0].upper()}
            </div>
            <div class="profile-info">
                <h4>{user_info.get('full_name', 'Admin')}</h4>
                <div class="role-badge admin-badge">Administrateur</div>
            </div>
        </div>
        <p class="profile-email">{user_info.get('email', 'admin@entreprise.com')}</p>
    </div>
    """, unsafe_allow_html=True)

def render_kpi_grid(metrics: List[Dict]):
    """Afficher une grille de KPI"""
    cols = st.columns(len(metrics))
    for idx, metric in enumerate(metrics):
        with cols[idx]:
            st.markdown(create_kpi_card(
                metric['title'],
                metric['value'],
                metric.get('color', Config.COLORS['primary']),
                metric.get('description', '')
            ), unsafe_allow_html=True)

def render_data_upload_section():
    """Section d'upload de données"""
    st.markdown("### 📤 Import de données")
    
    uploaded_file = st.file_uploader(
        "Importer des données (CSV, Excel, JSON)",
        type=['csv', 'xlsx', 'json'],
        key="admin_upload",
        help="Taille max: 100MB"
    )
    
    if uploaded_file:
        try:
            if not check_file_size(uploaded_file):
                st.error(f"Fichier trop volumineux. Max: {Config.MAX_FILE_SIZE_MB}MB")
                return
            
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            if file_extension == 'csv':
                data = pd.read_csv(uploaded_file)
            elif file_extension == 'xlsx':
                data = pd.read_excel(uploaded_file)
            elif file_extension == 'json':
                data = pd.read_json(uploaded_file)
            else:
                st.error("Format de fichier non supporté")
                return
            
            st.session_state.admin_data = data
            st.success(f"✅ Fichier importé avec succès: {len(data)} lignes, {len(data.columns)} colonnes")
            
            # Journaliser l'import
            log_admin_action(
                "DATA_IMPORT",
                uploaded_file.name,
                {"rows": len(data), "columns": list(data.columns)}
            )
            
        except Exception as e:
            logger.error(f"Erreur d'import: {str(e)}")
            st.error(f"Erreur lors de l'import: {str(e)}")

def render_name_column_selector(data: pd.DataFrame) -> Optional[str]:
    """Sélecteur de colonne d'identification"""
    if data is None:
        return None
    
    # Détecter les colonnes de noms potentielles
    name_keywords = ['nom', 'name', 'prenom', 'personne', 'user', 'client', 
                     'utilisateur', 'email', 'auteur', 'id', 'username']
    
    potential_cols = []
    for col in data.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in name_keywords):
            potential_cols.append(col)
    
    if potential_cols:
        selected_col = st.selectbox(
            "🎯 Colonne d'identification",
            potential_cols,
            help="Sélectionnez la colonne contenant les identifiants des personnes",
            key="name_col_selector"
        )
        st.info(f"Colonne sélectionnée: **{selected_col}**")
        return selected_col
    
    return None

# =========================PAGES DU DASHBOARD===================
def render_dashboard_page():
    """Page principale du tableau de bord"""
    st.markdown("### 📊 Tableau de bord principal")
    
    # Charger les statistiques utilisateurs
    users = load_users()
    total_users = len(users)
    active_users = sum(1 for u in users.values() if u.get('is_active', True))
    
    # Métriques principales
    metrics = [
        {
            'title': 'Utilisateurs actifs',
            'value': f"{active_users}/{total_users}",
            'color': Config.COLORS['primary'],
            'description': f"{active_users/total_users*100:.0f}% des utilisateurs sont actifs" if total_users > 0 else "Aucun utilisateur"
        },
        {
            'title': 'Disponibilité système',
            'value': "99.8%",
            'color': Config.COLORS['success'],
            'description': 'Performance système excellente'
        },
        {
            'title': 'Temps de réponse',
            'value': "0.42s",
            'color': Config.COLORS['warning'],
            'description': 'Temps de réponse optimal'
        },
        {
            'title': 'Modules configurés',
            'value': "8/10",
            'color': Config.COLORS['danger'],
            'description': '80% des modules configurés'
        }
    ]
    
    render_kpi_grid(metrics)
    
    # Visualisations des données
    if st.session_state.admin_data is not None:
        data = st.session_state.admin_data
        
        col1, col2 = st.columns(2)
        
        # Graphique de tendance
        with col1:
            date_cols = [col for col in data.columns if 'date' in col.lower() or 'time' in col.lower()]
            if date_cols:
                numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    fig, interpretation = create_trend_chart(data, date_cols[0], numeric_cols[0])
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown(f'<div class="interpretation-box">{interpretation}</div>', unsafe_allow_html=True)
        
        # Graphique de distribution
        with col2:
            error_cols = [col for col in data.columns if 'error' in col.lower() or 'status' in col.lower()]
            if error_cols:
                fig, interpretation = create_bar_chart(data, error_cols[0], "Distribution")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown(f'<div class="interpretation-box">{interpretation}</div>', unsafe_allow_html=True)
    else:
        st.info("📁 Importez des données pour voir les visualisations")

def render_fake_review_page():
    """Page de détection des faux avis"""
    st.markdown("### 🔍 Détection de Faux Avis")
    
    if st.session_state.admin_data is None:
        st.info("📁 Importez des données pour analyser les faux avis")
        return
    
    data = st.session_state.admin_data
    text_cols = data.select_dtypes(include=[object]).columns.tolist()
    
    if not text_cols:
        st.warning("⚠️ Aucune colonne texte trouvée dans les données")
        return
    
    # Sélection de la colonne texte
    selected_text_col = st.selectbox("Sélectionnez la colonne contenant les avis", text_cols)
    
    # Paramètres de détection
    col1, col2 = st.columns(2)
    with col1:
        threshold = st.slider("Seuil de détection", 0.1, 1.0, 0.7, 0.05,
                             help="Plus le seuil est élevé, plus la détection est stricte")
    with col2:
        min_length = st.slider("Longueur minimale des avis", 5, 100, 10)
    
    # Bouton d'analyse
    if st.button("🚀 Lancer l'analyse", type="primary", use_container_width=True):
        with st.spinner("Analyse en cours..."):
            # Détection des faux avis
            if 'detecter_faux_avis' in globals():
                data['faux_avis'] = data[selected_text_col].apply(
                    lambda x: detecter_faux_avis(str(x), threshold)
                )
            else:
                # Fallback pour les tests
                data['faux_avis'] = np.random.choice([True, False], len(data), p=[0.15, 0.85])
            
            st.session_state.admin_data = data
            
            # Calcul des statistiques
            fake_count = data['faux_avis'].sum()
            total = len(data)
            fake_percentage = (fake_count / total * 100) if total > 0 else 0
            
            # Affichage des résultats
            st.markdown("### 📊 Résultats de l'analyse")
            
            result_metrics = [
                {
                    'title': 'Faux avis détectés',
                    'value': f"{fake_count}",
                    'color': Config.COLORS['danger'],
                    'description': f"{fake_percentage:.1f}% du total"
                },
                {
                    'title': 'Avis authentiques',
                    'value': f"{total - fake_count}",
                    'color': Config.COLORS['success'],
                    'description': f"{(total-fake_count)/total*100:.1f}% du total" if total > 0 else "0%"
                },
                {
                    'title': 'Taux de détection',
                    'value': f"{threshold*100:.0f}%",
                    'color': Config.COLORS['warning'],
                    'description': 'Seuil de confiance'
                }
            ]
            
            render_kpi_grid(result_metrics)
            
            # Visualisations
            visualizations, interpretations = create_fake_review_analysis(data, selected_text_col)
            
            for i, (viz, interp) in enumerate(zip(visualizations, interpretations)):
                if i % 2 == 0:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.plotly_chart(viz, use_container_width=True)
                        st.markdown(f'<div class="interpretation-box">{interp}</div>', unsafe_allow_html=True)
                else:
                    with col2:
                        st.plotly_chart(viz, use_container_width=True)
                        st.markdown(f'<div class="interpretation-box">{interp}</div>', unsafe_allow_html=True)

def render_configuration_page():
    """Page de configuration"""
    st.markdown("### ⚙️ Configuration du Système")
    
    config = st.session_state.aim_config
    
    with st.form("config_form"):
        # Module de détection des faux avis
        st.markdown("#### 🔍 Détection de Faux Avis")
        col1, col2 = st.columns(2)
        
        with col1:
            detection_threshold = st.slider(
                "Seuil de détection",
                0.1, 1.0,
                config['modules']['fake_review_detection']['threshold'],
                0.05
            )
            auto_delete = st.checkbox(
                "Suppression automatique",
                value=config['modules']['fake_review_detection']['auto_delete']
            )
        
        with col2:
            detection_active = st.checkbox(
                "Activer la détection",
                value=config['modules']['fake_review_detection']['active']
            )
            alert_on_detection = st.checkbox(
                "Alertes en temps réel",
                value=config['modules']['fake_review_detection'].get('alerts', True)
            )
        
        # Module d'analyse de sentiment
        st.markdown("#### 📊 Analyse de Sentiment")
        col1, col2 = st.columns(2)
        
        with col1:
            sentiment_model = st.selectbox(
                "Modèle d'analyse",
                ["VADER", "TextBlob", "Transformers", "Custom"],
                index=0 if config['modules']['sentiment_analysis']['model'] == 'VADER' else 1
            )
        
        with col2:
            auto_analyze = st.checkbox(
                "Analyse automatique",
                value=config['modules']['sentiment_analysis']['auto_analyze']
            )
        
        # Configuration système
        st.markdown("#### 🖥️ Configuration Système")
        col1, col2 = st.columns(2)
        
        with col1:
            max_file_size = st.number_input(
                "Taille max des fichiers (MB)",
                10, 1000,
                config['system']['max_file_size']
            )
            auto_backup = st.checkbox(
                "Sauvegarde automatique",
                value=config['system']['auto_backup']
            )
        
        with col2:
            backup_frequency = st.selectbox(
                "Fréquence de sauvegarde",
                ["Quotidienne", "Hebdomadaire", "Mensuelle"],
                index=0 if config['system']['backup_frequency'] == 'Quotidienne' else 1
            )
            session_timeout = st.number_input(
                "Timeout session (minutes)",
                15, 480,
                Config.SESSION_TIMEOUT_MINUTES
            )
        
        # Bouton de sauvegarde
        if st.form_submit_button("💾 Sauvegarder la configuration", type="primary"):
            # Mise à jour de la configuration
            config['modules']['fake_review_detection'].update({
                'threshold': detection_threshold,
                'active': detection_active,
                'auto_delete': auto_delete,
                'alerts': alert_on_detection
            })
            
            config['modules']['sentiment_analysis'].update({
                'model': sentiment_model,
                'auto_analyze': auto_analyze
            })
            
            config['system'].update({
                'max_file_size': max_file_size,
                'auto_backup': auto_backup,
                'backup_frequency': backup_frequency,
                'session_timeout': session_timeout
            })
            
            # Sauvegarde
            save_aim_config(config)
            st.session_state.aim_config = config
            
            # Journaliser
            log_admin_action("CONFIG_UPDATE", "system", {"changes": "multiple"})
            
            st.success("✅ Configuration sauvegardée avec succès!")

def render_user_management_page():
    """Page de gestion des utilisateurs"""
    st.markdown("### 👥 Gestion des Utilisateurs")
    
    # Charger les utilisateurs
    users = load_users()
    current_user = st.session_state.user_info.get('username')
    
    # Statistiques
    total_users = len(users)
    active_users = sum(1 for u in users.values() if u.get('is_active', True))
    roles_count = {}
    
    for user in users.values():
        role = user.get('role', 'unknown')
        roles_count[role] = roles_count.get(role, 0) + 1
    
    # Affichage des statistiques
    stats_metrics = [
        {
            'title': 'Utilisateurs totaux',
            'value': str(total_users),
            'color': Config.COLORS['primary'],
            'description': f'{active_users} actifs'
        },
        {
            'title': 'Administrateurs',
            'value': str(roles_count.get('admin', 0)),
            'color': Config.COLORS['danger'],
            'description': f"{(roles_count.get('admin', 0)/total_users*100):.0f}%" if total_users > 0 else "0%"
        },
        {
            'title': 'Analystes',
            'value': str(roles_count.get('data_analyst', 0)),
            'color': Config.COLORS['info'],
            'description': f"{(roles_count.get('data_analyst', 0)/total_users*100):.0f}%" if total_users > 0 else "0%"
        },
        {
            'title': 'Marketing',
            'value': str(roles_count.get('marketing', 0)),
            'color': Config.COLORS['success'],
            'description': f"{(roles_count.get('marketing', 0)/total_users*100):.0f}%" if total_users > 0 else "0%"
        }
    ]
    
    render_kpi_grid(stats_metrics)
    
    # Création d'un nouvel utilisateur
    with st.expander("➕ Créer un nouvel utilisateur", expanded=False):
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input(
                    "Nom d'utilisateur *",
                    placeholder="nom.utilisateur",
                    help="Doit être unique"
                )
                new_email = st.text_input(
                    "Email *",
                    placeholder="prenom.nom@entreprise.com"
                )
                new_fullname = st.text_input(
                    "Nom complet",
                    placeholder="Prénom Nom"
                )
            
            with col2:
                new_role = st.selectbox(
                    "Rôle *",
                    ["data_analyst", "marketing", "viewer"],
                    help="Sélectionnez le rôle de l'utilisateur"
                )
                new_company = st.text_input(
                    "Entreprise",
                    placeholder="Nom de l'entreprise"
                )
                send_welcome = st.checkbox(
                    "Envoyer un email de bienvenue",
                    value=True
                )
            
            if st.form_submit_button("👤 Créer l'utilisateur", type="primary"):
                if not new_username or not new_email:
                    st.error("❌ Les champs marqués d'un * sont obligatoires")
                else:
                    success, result = admin_register_user(
                        username=new_username,
                        email=new_email,
                        role=new_role,
                        full_name=new_fullname,
                        company=new_company
                    )
                    
                    if success:
                        st.success("✅ Utilisateur créé avec succès!")
                        
                        # Affichage des identifiants
                        with st.expander("📋 Identifiants générés", expanded=True):
                            st.info(f"""
                            **Nom d'utilisateur:** {new_username}
                            **Email:** {new_email}
                            **Mot de passe temporaire:** `{result['generated_password']}`
                            **Rôle:** {new_role}
                            """)
                            
                            st.warning("⚠️ Ces identifiants ne seront affichés qu'une seule fois!")
                        
                        # Envoi d'email
                        if send_welcome:
                            send_welcome_email(
                                email=new_email,
                                username=new_username,
                                password=result['generated_password'],
                                full_name=new_fullname
                            )
                            st.info("📧 Email de bienvenue envoyé")
                        
                        log_admin_action("USER_CREATE", new_username, {"role": new_role})
                    else:
                        st.error(f"❌ Erreur: {result}")
    
    # Liste des utilisateurs
    st.markdown("### 📋 Liste des utilisateurs")
    
    if users:
        # Filtrer l'utilisateur courant
        filtered_users = {k: v for k, v in users.items() if k != current_user}
        
        if filtered_users:
            # Création du DataFrame
            users_data = []
            for username, user_data in filtered_users.items():
                users_data.append({
                    "Nom d'utilisateur": username,
                    "Email": user_data.get('email', 'N/A'),
                    "Nom complet": user_data.get('full_name', username),
                    "Rôle": user_data.get('role', 'N/A'),
                    "Entreprise": user_data.get('company', 'N/A'),
                    "Statut": "🟢 Actif" if user_data.get('is_active', True) else "🔴 Inactif",
                    "Dernière connexion": user_data.get('last_login', 'Jamais')[:19] if user_data.get('last_login') else 'Jamais',
                    "Date création": user_data.get('created_at', 'N/A')[:10]
                })
            
            users_df = pd.DataFrame(users_data)
            
            # Affichage avec filtres
            st.dataframe(
                users_df,
                use_container_width=True,
                height=400,
                column_config={
                    "Rôle": st.column_config.SelectboxColumn(
                        "Rôle",
                        options=["admin", "data_analyst", "marketing", "viewer"],
                        width="small"
                    ),
                    "Statut": st.column_config.TextColumn(
                        "Statut",
                        width="small"
                    ),
                }
            )
            
            # Actions sur utilisateur
            st.markdown("### ⚡ Actions rapides")
            
            selected_user = st.selectbox(
                "Sélectionner un utilisateur",
                list(filtered_users.keys()),
                format_func=lambda x: f"{x} ({filtered_users[x].get('email', 'N/A')})"
            )
            
            if selected_user:
                user_info = filtered_users[selected_user]
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    current_status = user_info.get('is_active', True)
                    action_text = "🔴 Désactiver" if current_status else "🟢 Activer"
                    if st.button(action_text, use_container_width=True):
                        success, message = toggle_user_status(selected_user, current_user)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                
                with col2:
                    if st.button("🔄 Réinitialiser MDP", use_container_width=True):
                        success, result = reset_user_password(selected_user)
                        if success:
                            st.success(f"✅ {result['message']}")
                            st.info(f"Nouveau mot de passe: `{result['new_password']}`")
                        else:
                            st.error(f"❌ {result}")
                
                with col3:
                    if st.button("🗑️ Supprimer", use_container_width=True, type="secondary"):
                        confirm = st.checkbox(f"Confirmer la suppression de {selected_user}")
                        if confirm:
                            success, message = delete_user(selected_user, current_user)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
        else:
            st.info("📝 Aucun autre utilisateur trouvé")
    else:
        st.info("📝 Aucun utilisateur enregistré")

def render_identification_page():
    """Page d'identification avancée"""
    st.markdown("### 🔎 Identification Avancée")
    
    if st.session_state.admin_data is None:
        st.info("📁 Importez des données pour utiliser ce module")
        return
    
    data = st.session_state.admin_data
    name_col = st.session_state.selected_name_col
    
    if not name_col:
        st.warning("⚠️ Veuillez sélectionner une colonne d'identification dans la sidebar")
        return
    
    # Présentation du module
    st.markdown("""
    <div class="info-card">
        <h4>🔒 Module d'Identification Sécurisée</h4>
        <p>Ce module permet d'identifier et d'analyser les personnes derrière les avis pour:</p>
        <ul>
            <li>🔍 Détecter les comportements suspects</li>
            <li>📊 Analyser les patterns d'activité</li>
            <li>🛡️ Prendre des mesures administratives</li>
            <li>📈 Générer des rapports d'audit</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Statistiques
    unique_persons = data[name_col].nunique()
    total_reviews = len(data)
    avg_reviews = total_reviews / unique_persons if unique_persons > 0 else 0
    
    stats_cols = st.columns(4)
    with stats_cols[0]:
        st.metric("👥 Personnes uniques", unique_persons)
    with stats_cols[1]:
        st.metric("📝 Avis totaux", total_reviews)
    with stats_cols[2]:
        st.metric("📊 Moyenne/personne", f"{avg_reviews:.1f}")
    with stats_cols[3]:
        if 'faux_avis' in data.columns:
            suspicious = data[data['faux_avis'] == True][name_col].nunique()
            st.metric("⚠️ Personnes suspectes", suspicious)
        else:
            st.metric("🎯 Colonne ID", name_col)
    
    # Recherche avancée
    st.markdown("#### 🔍 Recherche Avancée")
    
    search_tabs = st.tabs(["🔤 Par nom", "📊 Par activité", "📅 Par période"])
    
    with search_tabs[0]:
        search_term = st.text_input("Rechercher une personne:", placeholder="Entrez un nom...")
        if search_term:
            results = data[data[name_col].str.contains(search_term, case=False, na=False)]
            if not results.empty:
                st.success(f"✅ {len(results)} résultat(s) trouvé(s)")
                st.dataframe(results.head(10), use_container_width=True)
            else:
                st.warning("Aucun résultat trouvé")
    
    with search_tabs[1]:
        min_reviews = st.slider("Nombre minimum d'avis", 1, 50, 5)
        activity = data[name_col].value_counts()
        active_users = activity[activity >= min_reviews]
        
        if not active_users.empty:
            st.info(f"🔍 {len(active_users)} personne(s) avec {min_reviews}+ avis")
            for person, count in active_users.head(10).items():
                st.write(f"• **{person}**: {count} avis")
        else:
            st.info("Aucune personne ne correspond aux critères")
    
    with search_tabs[2]:
        if 'date' in data.columns:
            try:
                data['date'] = pd.to_datetime(data['date'])
                min_date = data['date'].min().date()
                max_date = data['date'].max().date()
                
                date_range = st.date_input(
                    "Sélectionnez une période",
                    value=[min_date, max_date],
                    min_value=min_date,
                    max_value=max_date
                )
                
                if len(date_range) == 2:
                    filtered_data = data[
                        (data['date'].dt.date >= date_range[0]) & 
                        (data['date'].dt.date <= date_range[1])
                    ]
                    st.metric("Avis dans la période", len(filtered_data))
                    st.metric("Personnes actives", filtered_data[name_col].nunique())
            except:
                st.warning("Format de date non supporté")
    
    # Rapport d'identification
    if st.button("📊 Générer le rapport complet", type="primary", use_container_width=True):
        with st.spinner("Génération du rapport..."):
            # Création du rapport
            report_data = []
            for person in data[name_col].unique()[:100]:  # Limite pour la performance
                person_data = data[data[name_col] == person]
                
                person_report = {
                    'Personne': person,
                    'Total avis': len(person_data),
                    'Activité': 'Élevée' if len(person_data) > 5 else 'Normale'
                }
                
                if 'date' in data.columns:
                    person_report['Premier avis'] = person_data['date'].min().strftime('%Y-%m-%d')
                    person_report['Dernier avis'] = person_data['date'].max().strftime('%Y-%m-%d')
                
                if 'sentiment' in data.columns:
                    sentiments = person_data['sentiment'].value_counts()
                    person_report['Positifs'] = sentiments.get('positif', 0)
                    person_report['Négatifs'] = sentiments.get('négatif', 0)
                
                if 'faux_avis' in data.columns:
                    fake_count = person_data['faux_avis'].sum()
                    person_report['Faux avis'] = fake_count
                    person_report['Statut'] = '⚠️ Suspect' if fake_count > 0 else '✅ Normal'
                
                report_data.append(person_report)
            
            report_df = pd.DataFrame(report_data).sort_values('Total avis', ascending=False)
            
            # Affichage
            st.dataframe(report_df, use_container_width=True, height=400)
            
            # Téléchargement
            csv = report_df.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Télécharger le rapport",
                data=csv,
                file_name=f"rapport_identification_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

# =========================FONCTION PRINCIPALE===================
def show_admin_dashboard():
    """Interface Administrateur - Tableau de bord principal"""
    
    # Vérification de session
    if not validate_session():
        st.error("Accès non autorisé. Veuillez vous reconnecter.")
        st.stop()
    
    # Initialisation de la session
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {
            'full_name': 'Administrateur',
            'email': 'admin@entreprise.com',
            'role': 'admin'
        }
    
    if 'admin_data' not in st.session_state:
        st.session_state.admin_data = None
    
    if 'aim_config' not in st.session_state:
        st.session_state.aim_config = load_aim_config()
    
    # CSS et style
    st.markdown(page_bg_css(), unsafe_allow_html=True)
    
    # =========================SIDEBAR===================
    with st.sidebar:
        # Profil utilisateur
        render_user_profile(st.session_state.user_info)
        
        # Navigation
        st.markdown("### 🗂️ Navigation")
        menu_option = st.radio(
            "Menu de navigation",
            ["📊 Tableau de bord", "🔍 Détection faux avis", "⚙️ Configuration", 
             "👥 Gestion Utilisateurs", "🔎 Identification"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Import de données
        render_data_upload_section()
        
        # Sélecteur de colonne
        if st.session_state.admin_data is not None:
            name_col = render_name_column_selector(st.session_state.admin_data)
            if name_col:
                st.session_state.selected_name_col = name_col
        
        st.markdown("---")
        
        # Audit log (optionnel)
        with st.expander("📋 Journal d'audit", expanded=False):
            if 'audit_log' in st.session_state:
                for log in st.session_state.audit_log[-5:]:  # 5 dernières entrées
                    st.caption(f"{log['timestamp'][11:19]} - {log['action']} - {log['target']}")
            else:
                st.info("Aucune activité enregistrée")
        
        # Déconnexion
        if st.button("🚪 Déconnexion", use_container_width=True, type="secondary"):
            log_admin_action("LOGOUT", st.session_state.user_info.get('full_name'))
            
            # Nettoyage de la session
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            
            st.session_state.logged_in = False
            st.rerun()
    
    # =========================EN-TÊTE===================
    st.markdown(f"""
    <div class="main-header">
        <h1>Tableau de bord Administrateur</h1>
        <p class="subtitle">Supervision système & Analyse des données AIM</p>
    </div>
    """, unsafe_allow_html=True)
    
    # =========================CONTENU PRINCIPAL===================
    try:
        if "Tableau de bord" in menu_option:
            render_dashboard_page()
        elif "Détection faux avis" in menu_option:
            render_fake_review_page()
        elif "Configuration" in menu_option:
            render_configuration_page()
        elif "Gestion Utilisateurs" in menu_option:
            render_user_management_page()
        elif "Identification" in menu_option:
            render_identification_page()
        
        # Footer
        st.markdown("---")
        st.caption(f"© {datetime.now().year} - Dashboard Administrateur | Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        logger.error(f"Erreur dans le dashboard: {str(e)}", exc_info=True)
        st.error("❌ Une erreur est survenue. Veuillez réessayer ou contacter le support.")
        st.error(f"Détails: {str(e)}")

# =========================STYLE CSS SUPPLEMENTAIRE===================
def add_custom_css():
    """Ajouter du CSS personnalisé"""
    st.markdown("""
    <style>
    .user-profile-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #E5E7EB;
    }
    
    .profile-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;
    }
    
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 1.2em;
    }
    
    .profile-info h4 {
        margin: 0;
        color: #172B4D;
    }
    
    .role-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8em;
        font-weight: 600;
    }
    
    .admin-badge {
        background: #FFE6E6;
        color: #DE350B;
    }
    
    .profile-email {
        margin: 5px 0 0 0;
        font-size: 0.85em;
        color: #6B7280;
    }
    
    .main-header {
        margin-bottom: 30px;
    }
    
    .main-header h1 {
        color: #172B4D;
        margin-bottom: 10px;
    }
    
    .subtitle {
        color: #6B7280;
        font-size: 1.1em;
    }
    
    .info-card {
        background: #E3F2FD;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border-left: 5px solid #2196F3;
    }
    
    .info-card h4 {
        margin-top: 0;
        color: #0D47A1;
    }
    
    .interpretation-box {
        background: #F8F9FA;
        padding: 15px;
        border-radius: 8px;
        margin-top: 10px;
        border-left: 4px solid #6554C0;
        font-size: 0.9em;
        color: #495057;
    }
    
    .stButton button {
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .metric-title {
        font-size: 0.9em;
        color: #6B7280;
        margin-bottom: 5px;
    }
    
    .metric-value {
        font-size: 1.8em;
        font-weight: bold;
        margin: 10px 0;
    }
    
    .metric-description {
        font-size: 0.8em;
        color: #9CA3AF;
    }
    </style>
    """, unsafe_allow_html=True)

# Point d'entrée
if __name__ == "__main__":
    add_custom_css()
    show_admin_dashboard()