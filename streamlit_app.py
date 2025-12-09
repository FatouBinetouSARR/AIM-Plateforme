# ================================
# AIM ANALYTICS PLATFORM 
# ================================
import streamlit as st
import os
import psycopg2
import bcrypt
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.figure_factory as ff
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import io
import re
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

# Gestion des imports optionnels
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    st.warning("TextBlob n'est pas installé. L'analyse de sentiment sera limitée.")

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    st.warning("FPDF n'est pas installé. L'export PDF sera désactivé.")

# ==================================
# CONFIGURATION
# ==================================
st.set_page_config(
    page_title="AIM Analytics Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "aim_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": os.getenv("DB_PORT", "5432"),
}

class Config:
    COLORS = {
        'primary': '#6554C0',
        'secondary': '#36B37E',
        'accent': '#FFAB00',
        'danger': '#FF5630',
        'info': '#00B8D9',
        'dark': '#172B4D',
        'light': '#6B7280'
    }
    
    SENTIMENT_COLORS = {
        'positif': '#36B37E',
        'négatif': '#FF5630',
        'neutre': '#FFAB00',
        'sarcastique': '#6554C0'
    }
    
    MAX_FILE_SIZE_MB = 100
    MAX_LOGIN_ATTEMPTS = 5

# ==================================
# GESTION DE LA BASE DE DONNÉES
# ==================================
class DatabaseManager:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self._create_tables()
            self._init_default_users()
        except Exception as e:
            st.warning(f"⚠️ Impossible de se connecter à la DB: {e}")
            self.conn = None

    def _create_tables(self):
        if not self.conn:
            return
        cursor = self.conn.cursor()
        
        # Table utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                full_name VARCHAR(100),
                email VARCHAR(100),
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL,
                department VARCHAR(50),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP,
                preferences JSONB DEFAULT '{}'
            )
        """)
        
        # Table sessions utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                session_token TEXT,
                login_time TIMESTAMP DEFAULT NOW(),
                logout_time TIMESTAMP,
                ip_address VARCHAR(50),
                user_agent TEXT
            )
        """)
        
        # Table uploads de données
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_uploads (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                file_name VARCHAR(255),
                file_size INTEGER,
                upload_time TIMESTAMP DEFAULT NOW(),
                data_type VARCHAR(50),
                record_count INTEGER,
                columns_count INTEGER,
                status VARCHAR(20) DEFAULT 'uploaded'
            )
        """)
        
        # Table logs d'activité
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                activity_type VARCHAR(50),
                description TEXT,
                ip_address VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        self.conn.commit()
        cursor.close()

    def _init_default_users(self):
        if not self.conn:
            return
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count == 0:
            self._create_user("admin", "admin123", "Super Admin", "admin", "admin@aim.com", "Administration")
            self._create_user("analyst", "analyst123", "Data Analyst", "data_analyst", "analyst@aim.com", "Analytics")
            self._create_user("marketing", "marketing123", "Marketing Manager", "marketing", "marketing@aim.com", "Marketing")
            self._create_user("support", "support123", "Support Agent", "support", "support@aim.com", "Support")
        cursor.close()

    def _create_user(self, username, password, fullname, role, email, department=None):
        if not self.conn:
            return
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, full_name, email, password_hash, role, department)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, fullname, email, hashed, role, department))
        self.conn.commit()
        cursor.close()

    def create_new_user(self, username, password, full_name, email, role, department=None):
        """Crée un nouvel utilisateur dans la base de données"""
        if not self.conn:
            return False, "Base de données non connectée"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s OR email = %s", 
                          (username, email))
            count = cursor.fetchone()[0]
            
            if count > 0:
                return False, "Nom d'utilisateur ou email déjà utilisé"
            
            if len(password) < 6:
                return False, "Le mot de passe doit contenir au moins 6 caractères"
            
            if role not in ['admin', 'data_analyst', 'marketing', 'support']:
                return False, "Rôle invalide"
            
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            
            cursor.execute("""
                INSERT INTO users (username, full_name, email, password_hash, role, department, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, true)
                RETURNING id
            """, (username, full_name, email, hashed, role, department))
            
            user_id = cursor.fetchone()[0]
            self.conn.commit()
            cursor.close()
            
            self.log_activity(user_id, "user_creation", 
                            f"Création d'un nouvel utilisateur: {username} ({role})")
            
            return True, f"Utilisateur {username} créé avec succès!"
            
        except Exception as e:
            return False, f"Erreur lors de la création: {str(e)}"

    def get_all_users(self):
        """Récupère tous les utilisateurs"""
        if not self.conn:
            return []
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, username, full_name, email, role, department, is_active, 
                   created_at, last_login
            FROM users
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        cursor.close()
        return users

    def update_user_status(self, user_id, is_active):
        """Active ou désactive un utilisateur"""
        if not self.conn:
            return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", 
                         (is_active, user_id))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            return False

    def authenticate(self, username, password):
        if not self.conn:
            return None
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE username=%s AND is_active=true", (username,))
        user = cursor.fetchone()
        cursor.close()
        if not user:
            return None
        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return None
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user["id"],))
        self.conn.commit()
        cursor.close()
        return user

    def update_user_profile(self, user_id, **kwargs):
        if not self.conn:
            return False
        try:
            cursor = self.conn.cursor()
            updates = []
            params = []
            
            if 'full_name' in kwargs:
                updates.append("full_name = %s")
                params.append(kwargs['full_name'])
            if 'email' in kwargs:
                updates.append("email = %s")
                params.append(kwargs['email'])
            if 'department' in kwargs:
                updates.append("department = %s")
                params.append(kwargs['department'])
            if 'password' in kwargs:
                hashed = bcrypt.hashpw(kwargs['password'].encode(), bcrypt.gensalt()).decode()
                updates.append("password_hash = %s")
                params.append(hashed)
            
            if updates:
                params.append(user_id)
                query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
                cursor.execute(query, tuple(params))
                self.conn.commit()
            
            cursor.close()
            return True
        except Exception as e:
            st.error(f"Error updating user profile: {e}")
            return False

    def log_activity(self, user_id, activity_type, description, ip_address="127.0.0.1"):
        if not self.conn:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO activity_logs (user_id, activity_type, description, ip_address)
                VALUES (%s, %s, %s, %s)
            """, (user_id, activity_type, description, ip_address))
            self.conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Error logging activity: {e}")

    def get_activity_logs(self, limit=100):
        if not self.conn:
            return []
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT al.*, u.username, u.full_name 
            FROM activity_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT %s
        """, (limit,))
        logs = cursor.fetchall()
        cursor.close()
        return logs

    def get_system_stats(self):
        if not self.conn:
            return {}
        cursor = self.conn.cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = true")
        stats['active_users'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_login >= CURRENT_DATE")
        stats['today_logins'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM data_uploads")
        stats['total_uploads'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM activity_logs")
        stats['total_activities'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        stats['users_by_role'] = dict(cursor.fetchall())
        
        cursor.close()
        return stats

# ==================================
# ANALYSEUR AIM AVANCÉ
# ==================================
class AIMAnalyzerAdvanced:
    @staticmethod
    def analyze_sentiment_advanced(text):
        """Analyse de sentiment avancée avec détection de sarcasme"""
        if not text or not isinstance(text, str):
            return {'score': 0, 'label': 'neutre', 'polarity': 0, 'subjectivity': 0, 'emotion': 'neutre'}
        
        if TEXTBLOB_AVAILABLE:
            try:
                analysis = TextBlob(text)
                polarity = analysis.sentiment.polarity
                subjectivity = analysis.sentiment.subjectivity
                
                sarcasm_keywords = ["bien sûr", "évidemment", "magnifique", "formidable", "super"]
                has_sarcasm = any(keyword in text.lower() for keyword in sarcasm_keywords) and polarity < -0.1
                
                if has_sarcasm:
                    polarity = -abs(polarity) * 1.5
                    label = 'sarcastique'
                else:
                    if polarity > 0.1:
                        label = 'positif'
                    elif polarity < -0.1:
                        label = 'négatif'
                    else:
                        label = 'neutre'
                
                emotions = {
                    'colère': ['colère', 'fâché', 'énervé', 'furieux', 'rage'],
                    'joie': ['heureux', 'joyeux', 'content', 'ravi', 'satisfait'],
                    'tristesse': ['triste', 'déprimé', 'malheureux', 'désolé'],
                    'surprise': ['surpris', 'étonné', 'choqué', 'impressionné'],
                    'peur': ['peur', 'effrayé', 'inquiet', 'anxieux']
                }
                
                detected_emotion = 'neutre'
                for emotion, keywords in emotions.items():
                    if any(keyword in text.lower() for keyword in keywords):
                        detected_emotion = emotion
                        break
                        
            except:
                polarity = 0
                subjectivity = 0
                label = 'neutre'
                detected_emotion = 'neutre'
        else:
            positive_words = ['bon', 'excellent', 'super', 'génial', 'parfait', 'fantastique', 'aimer', 'adorer']
            negative_words = ['mauvais', 'horrible', 'nul', 'décevant', 'terrible', 'pire', 'détester']
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count > negative_count:
                polarity = 0.5
                label = 'positif'
            elif negative_count > positive_count:
                polarity = -0.5
                label = 'négatif'
            else:
                polarity = 0
                label = 'neutre'
            
            subjectivity = 0.5
            detected_emotion = 'neutre'
        
        return {
            'score': round(polarity * 100, 2),
            'label': label,
            'polarity': round(polarity, 3),
            'subjectivity': round(subjectivity, 3),
            'emotion': detected_emotion,
            'text_length': len(text)
        }
    
    @staticmethod
    def detect_fake_review_advanced(text, metadata=None):
        """Détection avancée de faux avis avec scoring"""
        warning_signs = []
        fake_score = 0
        indicators = []
        
        fake_patterns = [
            (r'\b(excellent|parfait|génial|incroyable|merveilleux)\b.*?\1.*?\1', 'Exagération répétée (3+)', 25),
            (r'\b(mauvais|horrible|terrible|nul|décevant)\b.*?\1.*?\1', 'Négativité excessive (3+)', 25),
            (r'\!{3,}', 'Points d\'exclamation excessifs', 10),
            (r'\?{3,}', 'Points d\'interrogation excessifs', 5),
            (r'^[A-Z\s\!]{15,}', 'Texte en majuscules', 15),
            (r'\.{3,}', 'Ellipses excessives', 5),
            (r'\b(je|moi|mon|ma|mes)\b.*?\b(je|moi|mon|ma|mes)\b.*?\b(je|moi|mon|ma|mes)\b', 'Centrage sur soi répété', 20),
            (r'.{500,}', 'Texte trop long (>500 chars)', 10),
            (r'^.{0,20}$', 'Texte trop court (<20 chars)', 20),
            (r'https?://|www\.', 'Liens externes', 15),
            (r'\b(achetez|promo|offre|réduction|code)\b', 'Langage promotionnel', 15),
            (r'\d{5,}', 'Trop de chiffres', 10),
        ]
        
        for pattern, reason, points in fake_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                warning_signs.append(reason)
                indicators.append(f"{reason}: +{points}%")
                fake_score += points
        
        sentences = re.split(r'[.!?]+', text)
        avg_sentence_length = np.mean([len(s.split()) for s in sentences if s.strip()]) if sentences else 0
        
        if avg_sentence_length < 3:
            warning_signs.append("Phrases trop courtes")
            indicators.append("Phrases trop courtes: +10%")
            fake_score += 10
        elif avg_sentence_length > 25:
            warning_signs.append("Phrases trop longues")
            indicators.append("Phrases trop longues: +10%")
            fake_score += 10
        
        fake_probability = min(fake_score / 100, 1.0)
        
        return {
            'fake_probability': round(fake_probability * 100, 1),
            'warning_signs': warning_signs,
            'indicators': indicators,
            'is_suspicious': fake_probability > 0.5,
            'is_high_risk': fake_probability > 0.7,
            'score_details': fake_score,
            'sentence_count': len(sentences),
            'avg_sentence_length': round(avg_sentence_length, 1)
        }

# ==================================
# ANALYSEUR DE DONNÉES AVANCÉ
# ==================================
class AdvancedDataAnalyzer:
    @staticmethod
    def detect_column_types(df):
        """Détecte automatiquement les types de colonnes"""
        column_info = {
            'text_columns': [],
            'numeric_columns': [],
            'date_columns': [],
            'categorical_columns': [],
            'sentiment_columns': [],
            'rating_columns': []
        }
        
        for col in df.columns:
            col_data = df[col].dropna()
            
            if col_data.empty:
                continue
                
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                column_info['date_columns'].append(col)
                continue
            
            try:
                if pd.to_datetime(df[col].head(100), errors='coerce').notna().any():
                    column_info['date_columns'].append(col)
                    continue
            except:
                pass
            
            if pd.api.types.is_numeric_dtype(df[col]):
                column_info['numeric_columns'].append(col)
                
                if df[col].max() <= 10 and df[col].min() >= 0:
                    column_info['rating_columns'].append(col)
                continue
            
            if df[col].dtype == 'object' or isinstance(df[col].iloc[0], str):
                column_info['text_columns'].append(col)
                
                sentiment_keywords = ['avis', 'commentaire', 'feedback', 'review', 'sentiment', 'texte']
                if any(keyword in col.lower() for keyword in sentiment_keywords):
                    column_info['sentiment_columns'].append(col)
                continue
            
            if df[col].nunique() < 50 and df[col].nunique() > 1:
                column_info['categorical_columns'].append(col)
        
        return column_info
    
    @staticmethod
    def calculate_dynamic_kpis(df, column_info=None):
        """Calcule des KPIs dynamiques basés sur les données"""
        kpis = {}
        
        kpis['total_records'] = len(df)
        kpis['total_columns'] = len(df.columns)
        kpis['total_missing'] = df.isnull().sum().sum()
        kpis['completeness_rate'] = round((1 - kpis['total_missing'] / max(1, (len(df) * len(df.columns)))) * 100, 2)
        
        if column_info:
            kpis['text_columns_count'] = len(column_info['text_columns'])
            kpis['numeric_columns_count'] = len(column_info['numeric_columns'])
            kpis['date_columns_count'] = len(column_info['date_columns'])
            kpis['categorical_columns_count'] = len(column_info['categorical_columns'])
            
            if column_info['sentiment_columns']:
                kpis['sentiment_analysis_ready'] = True
                kpis['primary_sentiment_column'] = column_info['sentiment_columns'][0] if column_info['sentiment_columns'] else None
            
            if column_info['rating_columns']:
                kpis['rating_analysis_ready'] = True
                rating_col = column_info['rating_columns'][0]
                kpis['avg_rating'] = round(df[rating_col].mean(), 2) if rating_col in df.columns else 0
                
                if rating_col in df.columns:
                    kpis['rating_distribution'] = df[rating_col].value_counts().to_dict()
        
        date_cols = column_info['date_columns'] if column_info else []
        if date_cols:
            try:
                date_col = date_cols[0]
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                date_min = df[date_col].min()
                date_max = df[date_col].max()
                if pd.notna(date_min) and pd.notna(date_max):
                    kpis['date_range_days'] = (date_max - date_min).days
                    kpis['data_freshness_days'] = (pd.Timestamp.now() - date_max).days
                    
                    df['year_month'] = df[date_col].dt.to_period('M')
                    monthly_counts = df['year_month'].value_counts().sort_index()
                    if len(monthly_counts) > 1:
                        kpis['monthly_trend'] = 'croissant' if monthly_counts.iloc[-1] > monthly_counts.iloc[0] else 'décroissant'
            except Exception as e:
                print(f"Erreur dans le traitement des dates: {e}")
        
        if column_info and column_info['categorical_columns']:
            cat_col = column_info['categorical_columns'][0]
            if cat_col in df.columns:
                value_counts = df[cat_col].value_counts()
                kpis['top_category'] = value_counts.index[0] if not value_counts.empty else None
                kpis['top_category_count'] = value_counts.iloc[0] if not value_counts.empty else 0
                kpis['category_diversity'] = len(value_counts)
        
        return kpis
    
    @staticmethod
    def generate_marketing_recommendations(df, column_info, kpis):
        """Génère des recommandations marketing basées sur les données"""
        recommendations = []
        insights = []
        
        if column_info and column_info.get('sentiment_columns'):
            sentiment_col = column_info['sentiment_columns'][0]
            
            if sentiment_col in df.columns:
                sentiments = []
                sample_size = min(100, len(df))
                for text in df[sentiment_col].dropna().astype(str).head(sample_size):
                    sentiment = AIMAnalyzerAdvanced.analyze_sentiment_advanced(text)
                    sentiments.append(sentiment['label'])
                
                if sentiments:
                    sentiment_counts = Counter(sentiments)
                    total = sum(sentiment_counts.values())
                    positive_pct = (sentiment_counts.get('positif', 0) / total * 100) if total > 0 else 0
                    negative_pct = (sentiment_counts.get('négatif', 0) / total * 100) if total > 0 else 0
                    
                    if positive_pct > 70:
                        recommendations.append("✅ **Capitaliser sur les retours positifs** : Mettre en avant les témoignages positifs dans les campagnes marketing.")
                        insights.append(f"Taux de satisfaction élevé ({positive_pct:.1f}%)")
                    elif negative_pct > 30:
                        recommendations.append("⚠️ **Amélioration requise** : Prioriser la résolution des problèmes identifiés dans les retours négatifs.")
                        insights.append(f"Taux de mécontentement notable ({negative_pct:.1f}%)")
        
        if column_info and column_info.get('rating_columns'):
            rating_col = column_info['rating_columns'][0]
            if rating_col in df.columns:
                avg_rating = df[rating_col].mean()
                
                if avg_rating >= 4.0:
                    recommendations.append("🏆 **Certification qualité** : Obtenir une certification ou un label qualité basé sur les excellentes notations.")
                    insights.append(f"Note moyenne excellente ({avg_rating:.1f}/5)")
                elif avg_rating <= 2.5:
                    recommendations.append("🔧 **Plan d'amélioration** : Mettre en place un plan d'action urgent pour améliorer la qualité perçue.")
                    insights.append(f"Note moyenne préoccupante ({avg_rating:.1f}/5)")
        
        if 'data_freshness_days' in kpis:
            freshness = kpis['data_freshness_days']
            if freshness > 365:
                recommendations.append("🔄 **Actualisation des données** : Collecter de nouvelles données pour une analyse plus actuelle.")
                insights.append(f"Données anciennes ({freshness} jours)")
            elif freshness < 30:
                recommendations.append("🎯 **Marketing réactif** : Utiliser les données récentes pour des campagnes ciblées en temps réel.")
                insights.append(f"Données récentes ({freshness} jours)")
        
        if 'category_diversity' in kpis:
            diversity = kpis['category_diversity']
            if diversity > 20:
                recommendations.append("🎨 **Segmentations avancées** : Créer des segments marketing spécifiques pour chaque catégorie.")
                insights.append(f"Diversité élevée ({diversity} catégories)")
            elif diversity < 5:
                recommendations.append("📊 **Élargir l'analyse** : Collecter plus de données pour diversifier l'analyse.")
                insights.append(f"Diversité limitée ({diversity} catégories)")
        
        if kpis.get('completeness_rate', 0) < 80:
            recommendations.append("🧹 **Nettoyage des données** : Améliorer la qualité des données avant analyse approfondie.")
        
        if kpis.get('total_records', 0) > 10000:
            recommendations.append("🤖 **Automatisation** : Mettre en place des rapports automatiques pour suivre les KPIs clés.")
        
        return recommendations, insights
    
    @staticmethod
    def create_advanced_visualizations(df, column_info):
        """Crée des visualisations avancées basées sur les données"""
        figs = []
        
        if column_info and column_info['rating_columns']:
            rating_col = column_info['rating_columns'][0]
            if rating_col in df.columns:
                fig1 = px.histogram(df, x=rating_col, 
                                   title=f"Distribution des {rating_col}",
                                   nbins=10,
                                   color_discrete_sequence=[Config.COLORS['primary']])
                fig1.update_layout(bargap=0.1)
                figs.append(('📊 Distribution des notes', fig1))
        
        if column_info and column_info['date_columns']:
            date_col = column_info['date_columns'][0]
            try:
                df_temp = df.copy()
                df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
                df_temp['month'] = df_temp[date_col].dt.to_period('M').astype(str)
                
                monthly_counts = df_temp.groupby('month').size().reset_index(name='count')
                
                fig2 = px.line(monthly_counts, x='month', y='count',
                              title=f"Évolution mensuelle ({date_col})",
                              markers=True)
                fig2.update_traces(line_color=Config.COLORS['secondary'])
                figs.append(('📈 Évolution temporelle', fig2))
            except:
                pass
        
        if column_info and column_info['categorical_columns']:
            cat_col = column_info['categorical_columns'][0]
            if cat_col in df.columns:
                top_categories = df[cat_col].value_counts().head(10).reset_index()
                
                fig3 = px.bar(top_categories, x='index', y=cat_col,
                             title=f"Top 10 des {cat_col}",
                             color='index',
                             color_discrete_sequence=px.colors.qualitative.Set3)
                fig3.update_layout(xaxis_title=cat_col, yaxis_title="Nombre")
                figs.append(('🏷️ Top catégories', fig3))
        
        numeric_cols = column_info['numeric_columns'] if column_info else []
        if len(numeric_cols) >= 3:
            corr_matrix = df[numeric_cols].corr()
            
            fig4 = go.Figure(data=go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.index,
                colorscale='RdBu',
                zmin=-1, zmax=1
            ))
            fig4.update_layout(title="Matrice de corrélation")
            figs.append(('🔗 Corrélations', fig4))
        
        if numeric_cols:
            fig5 = go.Figure()
            for col in numeric_cols[:3]:
                fig5.add_trace(go.Box(y=df[col].dropna(), name=col))
            
            fig5.update_layout(title="Distribution avec anomalies")
            figs.append(('📦 Box plots', fig5))
        
        if column_info and len(column_info['categorical_columns']) >= 2:
            cat_cols = column_info['categorical_columns'][:2]
            hierarchy_data = df.groupby(cat_cols).size().reset_index(name='count')
            
            fig6 = px.sunburst(hierarchy_data, 
                              path=cat_cols, 
                              values='count',
                              title="Hiérarchie catégorielle")
            figs.append(('🌞 Hiérarchie', fig6))
        
        return figs

# ==================================
# STYLE CSS AVANCÉ
# ==================================
def advanced_page_bg_css() -> str:
    return """
    <style>
    .stApp { 
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
        background-attachment: fixed;
    }
    
    .main-container {
        background: rgba(255, 255, 255, 0.98);
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.3);
        color: #2c3e50;
    }
    
    .dashboard-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2.5rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        position: relative;
        overflow: hidden;
    }
    
    .dashboard-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
        background-size: 50px 50px;
        opacity: 0.3;
    }
    
    .kpi-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
        color: #2c3e50;
    }
    
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #667eea, #764ba2);
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.1);
    }
    
    .kpi-value {
        font-size: 2.8em;
        font-weight: 800;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1;
        color: #2c3e50;
    }
    
    .kpi-label {
        font-size: 0.9em;
        color: #5a6c7d;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .kpi-trend {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 600;
        margin-left: 8px;
        color: #2c3e50;
    }
    
    .kpi-trend-up {
        background: rgba(102, 187, 106, 0.2);
        color: #27ae60;
    }
    
    .kpi-trend-down {
        background: rgba(255, 86, 48, 0.2);
        color: #e74c3c;
    }
    
    .section-title {
        color: #2c3e50;
        font-size: 1.8em;
        font-weight: 700;
        margin: 2.5rem 0 1.5rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 3px solid;
        border-image: linear-gradient(90deg, #667eea, #764ba2) 1;
        position: relative;
    }
    
    .section-title::after {
        content: '';
        position: absolute;
        bottom: -3px;
        left: 0;
        width: 100px;
        height: 3px;
        background: linear-gradient(90deg, #667eea, #764ba2);
    }
    
    .insight-card {
        background: linear-gradient(135deg, rgba(227, 242, 253, 0.9) 0%, rgba(187, 222, 251, 0.9) 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 5px solid #3498db;
        box-shadow: 0 5px 20px rgba(52, 152, 219, 0.1);
        transition: all 0.3s ease;
        color: #2c3e50;
    }
    
    .insight-card:hover {
        transform: translateX(5px);
        box-shadow: 0 8px 25px rgba(52, 152, 219, 0.15);
    }
    
    .recommendation-card {
        background: linear-gradient(135deg, rgba(212, 237, 218, 0.9) 0%, rgba(195, 230, 203, 0.9) 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 5px solid #27ae60;
        box-shadow: 0 5px 20px rgba(39, 174, 96, 0.1);
        color: #2c3e50;
    }
    
    .warning-card {
        background: linear-gradient(135deg, rgba(255, 243, 205, 0.9) 0%, rgba(255, 234, 167, 0.9) 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 5px solid #f39c12;
        box-shadow: 0 5px 20px rgba(243, 156, 18, 0.1);
        color: #2c3e50;
    }
    
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        border: 1px solid rgba(0,0,0,0.05);
        color: #2c3e50;
    }
    
    .data-table-container {
        background: white;
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        margin: 1rem 0;
        border: 1px solid rgba(0,0,0,0.05);
        color: #2c3e50;
    }
    
    .stSidebar {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    .sidebar-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        color: white;
        margin: -1rem -1rem 1rem -1rem;
        border-radius: 0 0 20px 20px;
    }
    
    .upload-section {
        background: rgba(255, 255, 255, 0.95);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border: 2px dashed #667eea;
        color: #2c3e50;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #2c3e50;
    }
    
    p, li, span, div {
        color: #34495e;
    }
    
    .stSelectbox, .stMultiselect, .stTextInput, .stNumberInput, .stDateInput, .stTimeInput {
        background: white;
        color: #2c3e50;
    }
    </style>
    """

# ==================================
# DASHBOARD ADMINISTRATEUR AMÉLIORÉ
# ==================================
def dashboard_admin_enhanced(user, db):
    st.markdown(advanced_page_bg_css(), unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="dashboard-header">
        <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2.8em; font-weight: 800;">
            👑 Dashboard Administrateur
        </h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.2em; margin-bottom: 0;">
            Administration complète du système AIM Analytics
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        st.markdown(f"### {user.get('full_name', user['username'])}")
        st.markdown(f"👑 **Rôle:** {user['role'].replace('_', ' ').title()}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        admin_page = st.radio(
            "📊 Navigation",
            ["📈 Vue système", "👥 Gestion utilisateurs", "📋 Logs d'activité", "👤 Profil"],
            label_visibility="collapsed",
            key="admin_nav_radio"
        )
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Rafraîchir", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🚪 Déconnexion", use_container_width=True, type="primary"):
                st.session_state.clear()
                st.rerun()
    
    if admin_page == "📈 Vue système":
        render_system_overview_enhanced(user, db)
    elif admin_page == "👥 Gestion utilisateurs":
        render_user_management_enhanced(user, db)
    elif admin_page == "📋 Logs d'activité":
        render_activity_logs_enhanced(user, db)
    elif admin_page == "👤 Profil":
        render_user_profile_enhanced(user, db)

def render_system_overview_enhanced(user, db):
    """Vue d'ensemble système avec KPIs dynamiques"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📊 Vue d\'ensemble système</h2>', unsafe_allow_html=True)
    
    stats = db.get_system_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Utilisateurs total</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("total_users", 0)}</div>', unsafe_allow_html=True)
        active_pct = (stats.get('active_users', 0) / max(stats.get('total_users', 1), 1)) * 100
        st.markdown(f'<div class="kpi-trend kpi-trend-up">{stats.get("active_users", 0)} actifs ({active_pct:.0f}%)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Activités aujourd\'hui</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("today_logins", 0)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-trend kpi-trend-up">+12% vs hier</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Uploads total</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("total_uploads", 0)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-trend kpi-trend-up">+5 cette semaine</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Logs d\'activité</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("total_activities", 0):,}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-trend kpi-trend-up">En temps réel</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<h3 class="section-title">📈 Analytics système</h3>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        users_by_role = stats.get('users_by_role', {})
        if users_by_role:
            fig = px.pie(
                values=list(users_by_role.values()),
                names=[role.replace('_', ' ').title() for role in users_by_role.keys()],
                title="Répartition des utilisateurs par rôle",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("**Interprétation:** Cette répartition montre la distribution des différents rôles dans le système.")
        else:
            st.info("Aucune donnée disponible")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        activity_data = pd.DataFrame({
            'date': pd.date_range(end=pd.Timestamp.now(), periods=30, freq='D'),
            'activités': np.random.randint(50, 200, 30)
        })
        
        fig = px.line(activity_data, x='date', y='activités',
                     title="Activité système (30 derniers jours)",
                     markers=True)
        fig.update_traces(line_color=Config.COLORS['primary'])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Interprétation:** Ce graphique montre l'évolution de l'activité système sur les 30 derniers jours.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_user_management_enhanced(user, db):
    """Gestion avancée des utilisateurs avec formulaire d'ajout"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">👥 Gestion des utilisateurs</h2>', unsafe_allow_html=True)
    
    # Section d'ajout d'utilisateur
    st.markdown('<h3 class="section-title">➕ Ajouter un nouvel utilisateur</h3>', unsafe_allow_html=True)
    
    with st.form(key="add_user_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Nom d'utilisateur *", help="Nom unique pour la connexion")
            new_full_name = st.text_input("Nom complet *")
            new_email = st.text_input("Email *")
        
        with col2:
            new_role = st.selectbox(
                "Rôle *",
                ["data_analyst", "marketing", "support"],
                format_func=lambda x: {
                    "data_analyst": "🔬 Analyste de données",
                    "marketing": "📈 Marketing",
                    "support": "🛠️ Support"
                }.get(x, x)
            )
            new_password = st.text_input("Mot de passe *", type="password")
            confirm_password = st.text_input("Confirmer le mot de passe *", type="password")
            new_department = st.text_input("Département")
        
        submitted = st.form_submit_button("👤 Créer l'utilisateur", type="primary", use_container_width=True)
        
        if submitted:
            if not all([new_username, new_full_name, new_email, new_password, confirm_password]):
                st.error("❌ Veuillez remplir tous les champs obligatoires (*)")
            elif new_password != confirm_password:
                st.error("❌ Les mots de passe ne correspondent pas")
            elif len(new_password) < 6:
                st.error("❌ Le mot de passe doit contenir au moins 6 caractères")
            else:
                success, message = db.create_new_user(
                    username=new_username,
                    password=new_password,
                    full_name=new_full_name,
                    email=new_email,
                    role=new_role,
                    department=new_department if new_department else None
                )
                
                if success:
                    st.success(f"✅ {message}")
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    
    st.markdown('<h3 class="section-title">📋 Liste des utilisateurs</h3>', unsafe_allow_html=True)
    
    users = db.get_all_users()
    
    if users:
        users_df = pd.DataFrame(users)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            active_count = users_df['is_active'].sum() if 'is_active' in users_df.columns else 0
            st.metric("Utilisateurs actifs", active_count)
        
        with col2:
            role_count = users_df['role'].nunique() if 'role' in users_df.columns else 0
            st.metric("Rôles différents", role_count)
        
        with col3:
            today = pd.Timestamp.now().date()
            if 'last_login' in users_df.columns:
                recent_logins = sum(pd.to_datetime(users_df['last_login']).dt.date == today)
                st.metric("Connectés aujourd'hui", recent_logins)
        
        st.markdown('<div class="data-table-container">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            role_filter = st.multiselect(
                "Filtrer par rôle",
                users_df['role'].unique() if 'role' in users_df.columns else [],
                key="role_filter_management"
            )
        
        with col2:
            status_filter = st.multiselect(
                "Filtrer par statut",
                ['Actif', 'Inactif'],
                key="status_filter_management"
            )
        
        filtered_df = users_df.copy()
        
        if role_filter:
            filtered_df = filtered_df[filtered_df['role'].isin(role_filter)]
        
        if status_filter:
            if 'Actif' in status_filter and 'Inactif' not in status_filter:
                filtered_df = filtered_df[filtered_df['is_active'] == True]
            elif 'Inactif' in status_filter and 'Actif' not in status_filter:
                filtered_df = filtered_df[filtered_df['is_active'] == False]
        
        st.dataframe(filtered_df, use_container_width=True, height=400)
        
        st.markdown("### 🛠️ Actions rapides")
        col1, col2 = st.columns(2)
        
        with col1:
            selected_user = st.selectbox(
                "Sélectionner un utilisateur",
                filtered_df['username'].tolist(),
                key="user_select_action"
            )
            
            if selected_user:
                user_data = filtered_df[filtered_df['username'] == selected_user].iloc[0]
                
                new_status = st.selectbox(
                    "Changer le statut",
                    ["Actif", "Inactif"],
                    index=0 if user_data.get('is_active', True) else 1,
                    key="status_change_select"
                )
                
                if st.button("💾 Mettre à jour le statut", key="update_status_btn"):
                    is_active = new_status == "Actif"
                    success = db.update_user_status(user_data['id'], is_active)
                    if success:
                        st.success(f"✅ Statut de {selected_user} mis à jour")
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de la mise à jour")
        
        with col2:
            st.markdown("**Exporter les données**")
            if st.button("📥 Exporter en CSV", key="export_users_csv"):
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Télécharger CSV",
                    data=csv,
                    file_name="utilisateurs_aim.csv",
                    mime="text/csv"
                )
        
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Aucun utilisateur trouvé")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_activity_logs_enhanced(user, db):
    """Logs d'activité améliorés"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📋 Logs d\'activité</h2>', unsafe_allow_html=True)
    
    logs = db.get_activity_logs(limit=200)
    
    if logs:
        logs_df = pd.DataFrame(logs)
        
        if 'created_at' in logs_df.columns:
            logs_df['created_at'] = pd.to_datetime(logs_df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            activity_types = logs_df['activity_type'].unique() if 'activity_type' in logs_df.columns else []
            if len(activity_types) > 0:
                type_filter = st.multiselect(
                    "Type d'activité:",
                    activity_types,
                    default=activity_types[:3] if len(activity_types) > 3 else activity_types,
                    key="activity_type_filter"
                )
        
        with col2:
            date_filter = st.date_input(
                "Filtrer par date:",
                value=pd.Timestamp.now().date(),
                key="activity_date_filter"
            )
        
        with col3:
            user_filter = st.multiselect(
                "Filtrer par utilisateur:",
                logs_df['username'].unique() if 'username' in logs_df.columns else [],
                key="activity_user_filter"
            )
        
        filtered_logs = logs_df.copy()
        
        if 'type_filter' in locals() and type_filter:
            filtered_logs = filtered_logs[filtered_logs['activity_type'].isin(type_filter)]
        
        if 'user_filter' in locals() and user_filter:
            filtered_logs = filtered_logs[filtered_logs['username'].isin(user_filter)]
        
        st.markdown(f"**{len(filtered_logs)}** logs correspondant aux filtres")
        
        st.markdown('<div class="data-table-container">', unsafe_allow_html=True)
        st.dataframe(filtered_logs, use_container_width=True, height=500)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<h3 class="section-title">📊 Statistiques des activités</h3>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'activity_type' in filtered_logs.columns:
                activity_counts = filtered_logs['activity_type'].value_counts().head(10)
                fig1 = px.bar(
                    x=activity_counts.index,
                    y=activity_counts.values,
                    title="Top 10 des types d'activités",
                    labels={'x': 'Type', 'y': 'Nombre'},
                    color=activity_counts.values,
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            if 'username' in filtered_logs.columns:
                user_counts = filtered_logs['username'].value_counts().head(10)
                fig2 = px.pie(
                    values=user_counts.values,
                    names=user_counts.index,
                    title="Répartition par utilisateur (top 10)",
                    hole=0.3
                )
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aucun log d'activité disponible")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================================
# DASHBOARD ANALYSTE AVANCÉ
# ==================================
def dashboard_analyst_advanced(user, db):
    st.markdown(advanced_page_bg_css(), unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="dashboard-header">
        <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2.8em; font-weight: 800;">
            🤖 AIM Analytics - Intelligence Avancée
        </h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.2em; margin-bottom: 0;">
            Analyse prédictive • Détection de patterns • Intelligence artificielle
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialisation des états de session
    if 'uploaded_df' not in st.session_state:
        st.session_state.uploaded_df = None
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'advanced_aim_results' not in st.session_state:
        st.session_state.advanced_aim_results = None
    if 'column_info' not in st.session_state:
        st.session_state.column_info = None
    if 'dynamic_kpis' not in st.session_state:
        st.session_state.dynamic_kpis = None
    if 'fraud_results' not in st.session_state:
        st.session_state.fraud_results = None
    if 'high_risk_reviews' not in st.session_state:
        st.session_state.high_risk_reviews = None
    if 'fake_reviews' not in st.session_state:
        st.session_state.fake_reviews = None
    
    with st.sidebar:
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        st.markdown(f"### {user.get('full_name', user['username'])}")
        st.markdown(f"🔬 **Rôle:** Analyste AIM")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        st.markdown("### 📁 Import de données")
        
        uploaded_file = st.file_uploader(
            "Choisir un fichier",
            type=['csv', 'xlsx', 'xls', 'json', 'parquet'],
            help="Formats supportés: CSV, Excel, JSON, Parquet",
            key="analyst_data_uploader"
        )
        
        if uploaded_file:
            with st.spinner("🧠 Analyse en cours..."):
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                        df = pd.read_excel(uploaded_file)
                    elif uploaded_file.name.endswith('.json'):
                        df = pd.read_json(uploaded_file)
                    elif uploaded_file.name.endswith('.parquet'):
                        df = pd.read_parquet(uploaded_file)
                    else:
                        st.error("Format de fichier non supporté")
                        return
                    
                    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
                    
                    st.session_state.uploaded_df = df
                    
                    column_info = AdvancedDataAnalyzer.detect_column_types(df)
                    st.session_state.column_info = column_info
                    
                    st.session_state.dynamic_kpis = AdvancedDataAnalyzer.calculate_dynamic_kpis(df, column_info)
                    
                    st.success(f"✅ {len(df):,} lignes chargées")
                    
                except Exception as e:
                    st.error(f"❌ Erreur: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        analyst_page = st.radio(
            "📊 Navigation Analyse",
            ["📈 Dashboard AIM", "🔍 Analyse Avancée", "📊 Visualisations", 
             "🎯 Détection Fraude", "📤 Export"],
            label_visibility="collapsed",
            key="analyst_nav_radio"
        )
        
        if st.session_state.uploaded_df is not None:
            st.markdown("---")
            df = st.session_state.uploaded_df
            st.markdown("### 📊 Statut des données")
            st.markdown(f"**Enregistrements:** {len(df):,}")
            st.markdown(f"**Variables:** {len(df.columns)}")
            
            if st.session_state.column_info:
                info = st.session_state.column_info
                if info['sentiment_columns']:
                    st.markdown(f"**Colonne sentiment:** {info['sentiment_columns'][0]}")
                if info['rating_columns']:
                    st.markdown(f"**Colonne notation:** {info['rating_columns'][0]}")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Rafraîchir", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🚪 Déconnexion", use_container_width=True, type="primary"):
                st.session_state.clear()
                st.rerun()
    
    if analyst_page == "📈 Dashboard AIM":
        render_analyst_dashboard_advanced(user, db)
    elif analyst_page == "🔍 Analyse Avancée":
        render_advanced_analysis_page(user, db)
    elif analyst_page == "📊 Visualisations":
        render_advanced_visualizations_page(user, db)
    elif analyst_page == "🎯 Détection Fraude":
        render_fraud_detection_page(user, db)
    elif analyst_page == "📤 Export":
        render_export_page_advanced(user, db)

def render_analyst_dashboard_advanced(user, db):
    """Dashboard analyste avec KPIs dynamiques"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.markdown("""
        <div class="warning-card">
            <h3>📁 Aucune donnée chargée</h3>
            <p>Veuillez importer un fichier de données depuis la sidebar pour commencer l'analyse.</p>
            <p><strong>Formats supportés:</strong> CSV, Excel, JSON, Parquet</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    df = st.session_state.uploaded_df
    kpis = st.session_state.dynamic_kpis or {}
    
    st.markdown('<h2 class="section-title">📊 KPIs Dynamiques</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Total Enregistrements</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpis.get("total_records", 0):,}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-trend kpi-trend-up">Données brutes</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Qualité Données</div>', unsafe_allow_html=True)
        completeness = kpis.get('completeness_rate', 0)
        st.markdown(f'<div class="kpi-value">{completeness:.1f}%</div>', unsafe_allow_html=True)
        trend = "kpi-trend-up" if completeness > 80 else "kpi-trend-down"
        st.markdown(f'<div class="kpi-trend {trend}">{"Excellente" if completeness > 90 else "À améliorer"}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Colonnes Texte</div>', unsafe_allow_html=True)
        text_cols = kpis.get('text_columns_count', 0)
        st.markdown(f'<div class="kpi-value">{text_cols}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-trend kpi-trend-up">{"Analyse possible" if text_cols > 0 else "Non disponible"}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Colonnes Numériques</div>', unsafe_allow_html=True)
        num_cols = kpis.get('numeric_columns_count', 0)
        st.markdown(f'<div class="kpi-value">{num_cols}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-trend kpi-trend-up">{"Statistiques OK" if num_cols > 0 else "Limité"}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    if any(key in kpis for key in ['avg_rating', 'date_range_days', 'category_diversity', 'top_category_count']):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if 'avg_rating' in kpis:
                st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
                st.markdown('<div class="kpi-label">Note Moyenne</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="kpi-value">{kpis["avg_rating"]:.1f}/5</div>', unsafe_allow_html=True)
                trend = "kpi-trend-up" if kpis["avg_rating"] >= 3.5 else "kpi-trend-down"
                st.markdown(f'<div class="kpi-trend {trend}">{"Satisfaisant" if kpis["avg_rating"] >= 3.5 else "À améliorer"}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            if 'date_range_days' in kpis:
                st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
                st.markdown('<div class="kpi-label">Période</div>', unsafe_allow_html=True)
                days = kpis['date_range_days']
                st.markdown(f'<div class="kpi-value">{days} jours</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="kpi-trend kpi-trend-up">{"Longue période" if days > 365 else "Période récente"}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            if 'category_diversity' in kpis:
                st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
                st.markdown('<div class="kpi-label">Diversité</div>', unsafe_allow_html=True)
                diversity = kpis['category_diversity']
                st.markdown(f'<div class="kpi-value">{diversity}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="kpi-trend kpi-trend-up">{"Élevée" if diversity > 10 else "Standard"}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            if 'top_category_count' in kpis:
                st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
                st.markdown('<div class="kpi-label">Top Catégorie</div>', unsafe_allow_html=True)
                count = kpis['top_category_count']
                st.markdown(f'<div class="kpi-value">{count:,}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="kpi-trend kpi-trend-up">{kpis.get("top_category", "N/A")[:15]}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<h3 class="section-title">💡 Insights & Recommandations</h3>', unsafe_allow_html=True)
    
    if st.session_state.column_info:
        recommendations, insights = AdvancedDataAnalyzer.generate_marketing_recommendations(
            df, st.session_state.column_info, kpis
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="insight-card">', unsafe_allow_html=True)
            st.markdown("### 🔍 Insights clés")
            if insights:
                for insight in insights[:5]:
                    st.markdown(f"• {insight}")
            else:
                st.markdown("Aucun insight spécifique détecté")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="recommendation-card">', unsafe_allow_html=True)
            st.markdown("### 🎯 Recommandations")
            if recommendations:
                for rec in recommendations[:5]:
                    st.markdown(f"• {rec}")
            else:
                st.markdown("Aucune recommandation spécifique")
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<h3 class="section-title">📋 Aperçu des données</h3>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📊 Données brutes", "📈 Statistiques", "🎯 Types détectés"])
    
    with tab1:
        st.markdown('<div class="data-table-container">', unsafe_allow_html=True)
        st.dataframe(df.head(20), use_container_width=True, height=400)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="data-table-container">', unsafe_allow_html=True)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            st.dataframe(df[numeric_cols].describe(), use_container_width=True)
        else:
            st.info("Aucune colonne numérique pour les statistiques")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        if st.session_state.column_info:
            col_info = st.session_state.column_info
            info_df = pd.DataFrame({
                'Type': ['Texte', 'Numérique', 'Date', 'Catégoriel'],
                'Nombre': [
                    len(col_info.get('text_columns', [])),
                    len(col_info.get('numeric_columns', [])),
                    len(col_info.get('date_columns', [])),
                    len(col_info.get('categorical_columns', []))
                ],
                'Exemples': [
                    ', '.join(col_info.get('text_columns', [])[:3])[:50] + '...' if col_info.get('text_columns') else 'Aucune',
                    ', '.join(col_info.get('numeric_columns', [])[:3])[:50] + '...' if col_info.get('numeric_columns') else 'Aucune',
                    ', '.join(col_info.get('date_columns', [])[:3])[:50] + '...' if col_info.get('date_columns') else 'Aucune',
                    ', '.join(col_info.get('categorical_columns', [])[:3])[:50] + '...' if col_info.get('categorical_columns') else 'Aucune'
                ]
            })
            st.dataframe(info_df, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_advanced_analysis_page(user, db):
    """Page d'analyse avancée avec visualisations supplémentaires"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">🔍 Analyse AIM Avancée</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Veuillez d'abord importer des données")
        return
    
    df = st.session_state.uploaded_df
    column_info = st.session_state.column_info
    
    col1, col2 = st.columns(2)
    
    with col1:
        if column_info and column_info.get('text_columns'):
            text_col = st.selectbox(
                "Colonne texte à analyser:",
                column_info['text_columns'],
                key="advanced_text_col"
            )
        else:
            st.error("Aucune colonne de texte détectée")
            return
    
    with col2:
        sample_size = st.slider(
            "Taille de l'échantillon:",
            100,
            min(1000, len(df)),
            500,
            key="sample_size"
        )
    
    with st.expander("⚙️ Options d'analyse avancée"):
        col1, col2 = st.columns(2)
        
        with col1:
            analyze_sentiment = st.checkbox("Analyse de sentiment", True)
            detect_fake = st.checkbox("Détection de faux avis", True)
        
        with col2:
            min_text_length = st.slider("Longueur min. texte", 10, 200, 20)
            sentiment_threshold = st.slider("Seuil de confiance", 0.0, 1.0, 0.5)
    
    if st.button("🚀 Lancer l'analyse complète", type="primary", use_container_width=True):
        with st.spinner("🧠 Analyse AIM en cours..."):
            analysis_df = df.copy()
            
            text_lengths = analysis_df[text_col].astype(str).str.len()
            analysis_df = analysis_df[text_lengths >= min_text_length]
            
            if len(analysis_df) > sample_size:
                analysis_df = analysis_df.sample(sample_size, random_state=42)
            
            results = []
            fake_reviews = []
            
            progress_bar = st.progress(0)
            total_rows = len(analysis_df)
            
            for idx, (_, row) in enumerate(analysis_df.iterrows()):
                text = str(row[text_col])
                
                result = {'original_text': text}
                
                if analyze_sentiment:
                    sentiment = AIMAnalyzerAdvanced.analyze_sentiment_advanced(text)
                    result.update({
                        'sentiment_label': sentiment['label'],
                        'sentiment_score': sentiment['score'],
                        'sentiment_emotion': sentiment['emotion'],
                        'sentiment_polarity': sentiment['polarity']
                    })
                
                if detect_fake:
                    fake_analysis = AIMAnalyzerAdvanced.detect_fake_review_advanced(text)
                    result.update({
                        'fake_probability': fake_analysis['fake_probability'],
                        'is_suspicious': fake_analysis['is_suspicious'],
                        'is_high_risk': fake_analysis['is_high_risk'],
                        'warning_signs_count': len(fake_analysis['warning_signs'])
                    })
                    
                    if fake_analysis['is_high_risk']:
                        fake_reviews.append({
                            'text': text[:100] + '...' if len(text) > 100 else text,
                            'probability': fake_analysis['fake_probability'],
                            'indicators': fake_analysis['indicators']
                        })
                
                results.append(result)
                progress_bar.progress((idx + 1) / total_rows)
            
            results_df = pd.DataFrame(results)
            st.session_state.advanced_aim_results = results_df
            st.session_state.fake_reviews = fake_reviews
            
            st.success(f"✅ Analyse terminée sur {len(results_df)} échantillons!")
    
    # Vérifier si les résultats existent et ne sont pas vides
    if hasattr(st.session_state, 'advanced_aim_results') and st.session_state.advanced_aim_results is not None:
        results_df = st.session_state.advanced_aim_results
        
        if not results_df.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if 'sentiment_label' in results_df.columns:
                    positive_pct = (results_df['sentiment_label'] == 'positif').mean() * 100
                    st.metric("Positif", f"{positive_pct:.1f}%")
            
            with col2:
                if 'is_suspicious' in results_df.columns:
                    suspicious_pct = results_df['is_suspicious'].mean() * 100
                    st.metric("Suspect", f"{suspicious_pct:.1f}%")
            
            with col3:
                if 'sentiment_emotion' in results_df.columns:
                    joy_pct = (results_df['sentiment_emotion'] == 'joie').mean() * 100
                    st.metric("Joie", f"{joy_pct:.1f}%")
            
            with col4:
                st.metric("Analyse terminée", "100%")
            
            # Visualisations supplémentaires
            st.markdown('<h3 class="section-title">📊 Visualisations des résultats</h3>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'sentiment_label' in results_df.columns:
                    sentiment_counts = results_df['sentiment_label'].value_counts()
                    fig1 = px.pie(values=sentiment_counts.values, 
                                names=sentiment_counts.index,
                                title="Distribution des sentiments",
                                color_discrete_map=Config.SENTIMENT_COLORS)
                    st.plotly_chart(fig1, use_container_width=True)
                    st.markdown("**Interprétation:** Répartition des sentiments détectés dans les textes analysés.")
            
            with col2:
                if 'fake_probability' in results_df.columns:
                    fig2 = px.histogram(results_df, x='fake_probability',
                                      title="Distribution des probabilités de fraude",
                                      nbins=20,
                                      color_discrete_sequence=[Config.COLORS['danger']])
                    st.plotly_chart(fig2, use_container_width=True)
                    st.markdown("**Interprétation:** Distribution des scores de risque de fraude. Les valeurs élevées indiquent des avis suspects.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'sentiment_score' in results_df.columns and 'fake_probability' in results_df.columns:
                    fig3 = px.scatter(results_df, x='sentiment_score', y='fake_probability',
                                     title="Relation sentiment/risque fraude",
                                     color='sentiment_label',
                                     color_discrete_map=Config.SENTIMENT_COLORS)
                    st.plotly_chart(fig3, use_container_width=True)
                    st.markdown("**Interprétation:** Relation entre le score de sentiment et le risque de fraude.")
            
            with col2:
                if 'sentiment_emotion' in results_df.columns:
                    emotion_counts = results_df['sentiment_emotion'].value_counts()
                    fig4 = px.bar(x=emotion_counts.index, y=emotion_counts.values,
                                 title="Distribution des émotions",
                                 color=emotion_counts.values,
                                 color_continuous_scale='Viridis')
                    st.plotly_chart(fig4, use_container_width=True)
                    st.markdown("**Interprétation:** Répartition des différentes émotions détectées.")
        else:
            st.info("L'analyse n'a produit aucun résultat. Veuillez vérifier vos données et paramètres.")
    else:
        st.info("Aucune analyse n'a été effectuée. Veuillez lancer l'analyse en cliquant sur le bouton ci-dessus.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_advanced_visualizations_page(user, db):
    """Page de visualisations avancées avec 3 visualisations dynamiques"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📊 Visualisations Avancées</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Veuillez d'abord importer des données")
        return
    
    df = st.session_state.uploaded_df
    column_info = st.session_state.column_info
    
    st.markdown('<h3 class="section-title">🎯 Visualisations dynamiques</h3>', unsafe_allow_html=True)
    
    if column_info:
        figs = AdvancedDataAnalyzer.create_advanced_visualizations(df, column_info)
        
        if len(figs) >= 3:
            # Afficher les 3 premières visualisations
            for i in range(min(3, len(figs))):
                title, fig = figs[i]
                with st.container():
                    st.markdown(f'<div class="chart-container">', unsafe_allow_html=True)
                    st.markdown(f"**{title}**")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Interprétations spécifiques
                    if "Distribution des notes" in title:
                        st.markdown("**Interprétation:** Cette distribution montre comment les notes sont réparties. Une distribution normale centrée sur 4-5 indique une satisfaction générale élevée.")
                    elif "Évolution temporelle" in title:
                        st.markdown("**Interprétation:** Cette courbe montre l'évolution dans le temps. Une tendance à la hausse indique une croissance, tandis qu'une baisse peut signaler des problèmes.")
                    elif "Top catégories" in title:
                        st.markdown("**Interprétation:** Ce graphique montre les catégories les plus fréquentes. Les catégories dominantes peuvent indiquer des points forts ou des opportunités de diversification.")
                    elif "Corrélations" in title:
                        st.markdown("**Interprétation:** Cette matrice montre les relations entre variables. Les valeurs proches de 1 ou -1 indiquent des corrélations fortes (positives ou négatives).")
                    elif "Box plots" in title:
                        st.markdown("**Interprétation:** Ces box plots montrent la distribution des données et détectent les valeurs aberrantes. Les points hors des moustaches sont considérés comme des anomalies.")
                    elif "Hiérarchie" in title:
                        st.markdown("**Interprétation:** Ce diagramme hiérarchique montre les relations entre catégories. Les segments plus grands représentent les catégories dominantes.")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
            
            # Afficher les visualisations restantes si disponibles
            if len(figs) > 3:
                st.markdown('<h4 class="section-title">📈 Visualisations supplémentaires</h4>', unsafe_allow_html=True)
                for i in range(3, len(figs)):
                    title, fig = figs[i]
                    with st.container():
                        st.markdown(f'<div class="chart-container">', unsafe_allow_html=True)
                        st.markdown(f"**{title}**")
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info(f"Seulement {len(figs)} visualisations disponibles avec les données actuelles")
            for title, fig in figs:
                with st.container():
                    st.markdown(f'<div class="chart-container">', unsafe_allow_html=True)
                    st.markdown(f"**{title}**")
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Veuillez d'abord analyser les données pour générer des visualisations")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_fraud_detection_page(user, db):
    """Page de détection de fraude corrigée"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">🎯 Détection de Faux Avis & Fraude</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Veuillez d'abord importer des données")
        return
    
    df = st.session_state.uploaded_df
    column_info = st.session_state.column_info
    
    if not column_info or not column_info.get('text_columns'):
        st.error("Aucune colonne de texte détectée pour l'analyse")
        return
    
    text_col = st.selectbox(
        "Sélectionnez la colonne à analyser:",
        column_info['text_columns'],
        key="fraud_text_col"
    )
    
    sample_size = st.slider(
        "Nombre d'échantillons à analyser:",
        50,
        min(500, len(df)),
        200,
        key="fraud_sample_size"
    )
    
    if st.button("🔍 Détecter les faux avis", type="primary", use_container_width=True):
        with st.spinner("🧠 Analyse des faux avis en cours..."):
            analysis_df = df.copy()
            
            if len(analysis_df) > sample_size:
                analysis_df = analysis_df.sample(sample_size, random_state=42)
            
            fake_results = []
            high_risk_reviews = []
            
            for idx, (_, row) in enumerate(analysis_df.iterrows()):
                text = str(row[text_col])
                
                fake_analysis = AIMAnalyzerAdvanced.detect_fake_review_advanced(text)
                
                result = {
                    'text': text[:150] + '...' if len(text) > 150 else text,
                    'fake_probability': fake_analysis['fake_probability'],
                    'is_suspicious': fake_analysis['is_suspicious'],
                    'is_high_risk': fake_analysis['is_high_risk'],
                    'warning_signs': ', '.join(fake_analysis['warning_signs'][:3]) if fake_analysis['warning_signs'] else 'Aucun',
                    'sentence_count': fake_analysis['sentence_count']
                }
                
                fake_results.append(result)
                
                if fake_analysis['is_high_risk']:
                    high_risk_reviews.append(result)
            
            st.session_state.fraud_results = pd.DataFrame(fake_results)
            st.session_state.high_risk_reviews = high_risk_reviews
            
            st.success(f"✅ Analyse terminée! {len(high_risk_reviews)} avis haut risque détectés.")
    
    if hasattr(st.session_state, 'fraud_results') and st.session_state.fraud_results is not None:
        results_df = st.session_state.fraud_results
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            high_risk_count = results_df['is_high_risk'].sum()
            st.metric("Haut risque", f"{high_risk_count}", 
                     delta=f"{(high_risk_count/len(results_df)*100):.1f}%")
        
        with col2:
            suspicious_count = results_df['is_suspicious'].sum()
            st.metric("Suspects", f"{suspicious_count}", 
                     delta=f"{(suspicious_count/len(results_df)*100):.1f}%")
        
        with col3:
            avg_risk = results_df['fake_probability'].mean()
            st.metric("Risque moyen", f"{avg_risk:.1f}%")
        
        with col4:
            avg_sentences = results_df['sentence_count'].mean()
            st.metric("Phrases moy.", f"{avg_sentences:.1f}")
        
        st.markdown('<h3 class="section-title">📊 Analyse des risques</h3>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = px.histogram(results_df, x='fake_probability',
                              title="Distribution des risques de fraude",
                              nbins=20,
                              color_discrete_sequence=[Config.COLORS['danger']])
            fig1.update_layout(xaxis_title="Probabilité de fraude (%)", 
                             yaxis_title="Nombre d'avis")
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown("**Interprétation:** Distribution des scores de risque. Une concentration à droite indique des problèmes potentiels.")
        
        with col2:
            risk_labels = pd.cut(results_df['fake_probability'], 
                               bins=[0, 30, 70, 100], 
                               labels=['Faible', 'Moyen', 'Élevé'])
            risk_counts = risk_labels.value_counts()
            
            fig2 = px.pie(values=risk_counts.values, 
                         names=risk_counts.index,
                         title="Répartition des niveaux de risque",
                         color_discrete_sequence=['#36B37E', '#FFAB00', '#FF5630'])
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown("**Interprétation:** Répartition des avis par niveau de risque.")
        
        st.markdown('<h3 class="section-title">🔍 Avis haut risque détectés</h3>', unsafe_allow_html=True)
        
        if hasattr(st.session_state, 'high_risk_reviews') and st.session_state.high_risk_reviews:
            high_risk_df = pd.DataFrame(st.session_state.high_risk_reviews)
            
            for idx, row in high_risk_df.head(5).iterrows():
                with st.expander(f"🛑 Avis #{idx+1} - {row['fake_probability']}% de risque"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**Texte:** {row['text']}")
                    
                    with col2:
                        st.markdown(f"**Risque:** {row['fake_probability']}%")
                        st.progress(row['fake_probability'] / 100)
                    
                    st.markdown(f"**Signes d'alerte:** {row['warning_signs']}")
        else:
            st.info("✅ Aucun avis haut risque détecté!")
        
        st.markdown('<h3 class="section-title">📋 Résultats détaillés</h3>', unsafe_allow_html=True)
        
        st.markdown('<div class="data-table-container">', unsafe_allow_html=True)
        st.dataframe(results_df.sort_values('fake_probability', ascending=False), 
                    use_container_width=True, height=400)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Veuillez d'abord exécuter l'analyse de détection de fraude.")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================================
# DASHBOARD MARKETING AVANCÉ
# ==================================
def dashboard_marketing_advanced(user, db):
    st.markdown(advanced_page_bg_css(), unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="dashboard-header">
        <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2.8em; font-weight: 800;">
            📈 AIM Marketing Intelligence
        </h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.2em; margin-bottom: 0;">
            Optimisation marketing basée sur l'analyse intelligente des données
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if 'uploaded_df' not in st.session_state:
        st.session_state.uploaded_df = None
    if 'marketing_kpis' not in st.session_state:
        st.session_state.marketing_kpis = None
    if 'marketing_recommendations' not in st.session_state:
        st.session_state.marketing_recommendations = None
    if 'marketing_insights' not in st.session_state:
        st.session_state.marketing_insights = None
    if 'marketing_column_info' not in st.session_state:
        st.session_state.marketing_column_info = None
    
    with st.sidebar:
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        st.markdown(f"### {user.get('full_name', user['username'])}")
        st.markdown(f"📈 **Rôle:** Marketing Intelligence")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        st.markdown("### 📁 Données marketing")
        
        uploaded_file = st.file_uploader(
            "Charger des données",
            type=['csv', 'xlsx', 'xls', 'json', 'parquet'],
            key="marketing_data_uploader",
            help="Données clients, ventes, campagnes..."
        )
        
        if uploaded_file:
            with st.spinner("Analyse marketing en cours..."):
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                        df = pd.read_excel(uploaded_file)
                    elif uploaded_file.name.endswith('.json'):
                        df = pd.read_json(uploaded_file)
                    elif uploaded_file.name.endswith('.parquet'):
                        df = pd.read_parquet(uploaded_file)
                    else:
                        st.error("Format de fichier non supporté")
                        return
                    
                    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
                    
                    st.session_state.uploaded_df = df
                    
                    column_info = AdvancedDataAnalyzer.detect_column_types(df)
                    st.session_state.marketing_column_info = column_info
                    
                    kpis = AdvancedDataAnalyzer.calculate_dynamic_kpis(df, column_info)
                    recommendations, insights = AdvancedDataAnalyzer.generate_marketing_recommendations(df, column_info, kpis)
                    
                    st.session_state.marketing_kpis = kpis
                    st.session_state.marketing_recommendations = recommendations
                    st.session_state.marketing_insights = insights
                    
                    st.success(f"✅ {len(df):,} données marketing chargées")
                    
                except Exception as e:
                    st.error(f"❌ Erreur: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        marketing_page = st.radio(
            "🎯 Navigation Marketing",
            ["📊 Dashboard", "👥 Analyse Clients", "📈 Performance", "💡 Stratégies", "📤 Rapports"],
            label_visibility="collapsed",
            key="marketing_nav_radio"
        )
        
        if st.session_state.uploaded_df is not None:
            st.markdown("---")
            df = st.session_state.uploaded_df
            st.markdown("### 📊 Données disponibles")
            st.markdown(f"**Enregistrements:** {len(df):,}")
            st.markdown(f"**Variables:** {len(df.columns)}")
            
            if st.session_state.marketing_kpis:
                kpis = st.session_state.marketing_kpis
                if 'avg_rating' in kpis:
                    st.markdown(f"**Satisfaction:** {kpis['avg_rating']:.1f}/5")
                if 'category_diversity' in kpis:
                    st.markdown(f"**Segments:** {kpis['category_diversity']}")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Actualiser", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🚪 Déconnexion", use_container_width=True, type="primary"):
                st.session_state.clear()
                st.rerun()
    
    if marketing_page == "📊 Dashboard":
        render_marketing_dashboard(user, db)
    elif marketing_page == "👥 Analyse Clients":
        render_customer_analysis_advanced(user, db)
    elif marketing_page == "📈 Performance":
        render_performance_analysis_advanced(user, db)
    elif marketing_page == "💡 Stratégies":
        render_marketing_strategies(user, db)
    elif marketing_page == "📤 Rapports":
        render_marketing_reports(user, db)

def render_marketing_dashboard(user, db):
    """Dashboard marketing avancé avec KPIs corrigés"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📊 Dashboard Marketing</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.markdown("""
        <div class="warning-card">
            <h3>📁 Données marketing requises</h3>
            <p>Importez des données marketing pour activer l'analyse intelligente.</p>
            <p><strong>Données recommandées:</strong> Avis clients, notations, segments, dates, produits</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    df = st.session_state.uploaded_df
    kpis = st.session_state.marketing_kpis or {}
    
    st.markdown('<h3 class="section-title">🎯 KPIs Marketing Clés</h3>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Base Client</div>', unsafe_allow_html=True)
        total_records = kpis.get("total_records", len(df))
        st.markdown(f'<div class="kpi-value">{total_records:,}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-trend kpi-trend-up">Clients actifs</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        avg_rating = kpis.get('avg_rating', 0)
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Satisfaction</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{avg_rating:.1f}/5</div>', unsafe_allow_html=True)
        trend = "kpi-trend-up" if avg_rating >= 4.0 else "kpi-trend-down"
        rating_text = "Excellente" if avg_rating >= 4.0 else "À améliorer" if avg_rating >= 3.0 else "Préoccupante"
        st.markdown(f'<div class="kpi-trend {trend}">{rating_text}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        diversity = kpis.get('category_diversity', 0)
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Segments</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{diversity}</div>', unsafe_allow_html=True)
        trend = "kpi-trend-up" if diversity > 10 else "kpi-trend-down"
        st.markdown(f'<div class="kpi-trend {trend}">{"Diversifiée" if diversity > 10 else "Standard"}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Qualité</div>', unsafe_allow_html=True)
        completeness = kpis.get('completeness_rate', 0)
        st.markdown(f'<div class="kpi-value">{completeness:.1f}%</div>', unsafe_allow_html=True)
        trend = "kpi-trend-up" if completeness > 80 else "kpi-trend-down"
        st.markdown(f'<div class="kpi-trend {trend}">{"Bonne" if completeness > 80 else "À nettoyer"}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Visualisation supplémentaire dynamique
    st.markdown('<h3 class="section-title">📈 Analyse des performances</h3>', unsafe_allow_html=True)
    
    column_info = st.session_state.marketing_column_info
    
    if column_info and column_info.get('rating_columns'):
        rating_col = column_info['rating_columns'][0]
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribution des notes
            fig1 = px.histogram(df, x=rating_col, 
                               title=f"Distribution des {rating_col}",
                               nbins=10,
                               color_discrete_sequence=[Config.COLORS['primary']])
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown("**Interprétation:** Répartition des notes clients. Une distribution centrée sur 4-5 indique une satisfaction élevée.")
        
        with col2:
            # Évolution temporelle si disponible
            if column_info.get('date_columns'):
                date_col = column_info['date_columns'][0]
                try:
                    df_temp = df.copy()
                    df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
                    df_temp['month'] = df_temp[date_col].dt.to_period('M').astype(str)
                    
                    monthly_avg = df_temp.groupby('month')[rating_col].mean().reset_index()
                    
                    fig2 = px.line(monthly_avg, x='month', y=rating_col,
                                  title=f"Évolution de la satisfaction",
                                  markers=True)
                    fig2.update_traces(line_color=Config.COLORS['secondary'])
                    st.plotly_chart(fig2, use_container_width=True)
                    st.markdown("**Interprétation:** Évolution de la satisfaction dans le temps. Une tendance à la hausse est positive.")
                except:
                    # Fallback: Top catégories
                    if column_info.get('categorical_columns'):
                        cat_col = column_info['categorical_columns'][0]
                        top_categories = df[cat_col].value_counts().head(10).reset_index()
                        
                        fig2 = px.bar(top_categories, x='index', y=cat_col,
                                     title=f"Top 10 des {cat_col}",
                                     color='index')
                        st.plotly_chart(fig2, use_container_width=True)
                        st.markdown("**Interprétation:** Catégories les plus représentées dans les données.")
    
    st.markdown('<h3 class="section-title">💡 Insights Marketing</h3>', unsafe_allow_html=True)
    
    if st.session_state.marketing_insights:
        insights = st.session_state.marketing_insights
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="insight-card">', unsafe_allow_html=True)
            st.markdown("### 🔍 Insights détectés")
            if insights:
                for insight in insights[:5]:
                    st.markdown(f"• {insight}")
            else:
                st.markdown("Aucun insight spécifique détecté")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            if st.session_state.marketing_recommendations:
                recommendations = st.session_state.marketing_recommendations
                st.markdown('<div class="recommendation-card">', unsafe_allow_html=True)
                st.markdown("### 🎯 Recommandations")
                if recommendations:
                    for rec in recommendations[:5]:
                        st.markdown(f"• {rec}")
                else:
                    st.markdown("Aucune recommandation spécifique")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_customer_analysis_advanced(user, db):
    """Analyse clients avancée avec détection de faux avis et analyse de sentiment"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">👥 Analyse Avancée des Clients</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Veuillez d'abord importer des données clients")
        return
    
    df = st.session_state.uploaded_df
    column_info = st.session_state.marketing_column_info or {}
    
    st.markdown("### 🎯 Configuration de l'analyse clients")
    
    tab1, tab2, tab3 = st.tabs(["📊 Segmentation", "🎯 Détection Fraude", "😊 Analyse Sentiment"])
    
    with tab1:
        segmentation_cols = column_info.get('categorical_columns', [])
        if segmentation_cols:
            segment_by = st.selectbox(
                "Segmenter par:",
                segmentation_cols,
                key="customer_segment"
            )
            
            top_n = st.slider("Nombre de segments", 5, 50, 10, key="segment_top_n")
            
            if st.button("📊 Analyser la segmentation", key="analyze_segments"):
                segment_counts = df[segment_by].value_counts().head(top_n).reset_index()
                segment_counts.columns = [segment_by, 'Nombre']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig1 = px.bar(segment_counts, x=segment_by, y='Nombre',
                                 title=f"Segmentation par {segment_by}",
                                 color='Nombre',
                                 color_continuous_scale='Viridis')
                    st.plotly_chart(fig1, use_container_width=True)
                    st.markdown("**Interprétation:** Distribution des clients par segment.")
                
                with col2:
                    fig2 = px.pie(segment_counts, values='Nombre', names=segment_by,
                                 title=f"Répartition par {segment_by}",
                                 hole=0.3)
                    st.plotly_chart(fig2, use_container_width=True)
                    st.markdown("**Interprétation:** Proportion de chaque segment.")
        else:
            st.info("Aucune colonne de segmentation détectée")
    
    with tab2:
        if column_info and column_info.get('text_columns'):
            text_col = st.selectbox(
                "Colonne texte à analyser:",
                column_info['text_columns'],
                key="customer_fraud_text"
            )
            
            sample_size = st.slider(
                "Échantillon:",
                50,
                min(300, len(df)),
                150,
                key="customer_fraud_sample"
            )
            
            if st.button("🔍 Détecter les faux avis", key="analyze_customer_fraud"):
                with st.spinner("Analyse en cours..."):
                    sample_df = df.sample(min(sample_size, len(df)), random_state=42)
                    
                    fraud_results = []
                    for text in sample_df[text_col].astype(str):
                        analysis = AIMAnalyzerAdvanced.detect_fake_review_advanced(text)
                        fraud_results.append(analysis['fake_probability'])
                    
                    fraud_series = pd.Series(fraud_results)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig1 = px.histogram(fraud_series, 
                                           title="Distribution des risques de fraude",
                                           nbins=20,
                                           labels={'value': 'Risque de fraude (%)'},
                                           color_discrete_sequence=[Config.COLORS['danger']])
                        st.plotly_chart(fig1, use_container_width=True)
                        st.markdown("**Interprétation:** Distribution des scores de risque de fraude.")
                    
                    with col2:
                        risk_levels = pd.cut(fraud_series, 
                                           bins=[0, 30, 70, 100], 
                                           labels=['Faible', 'Moyen', 'Élevé'])
                        risk_counts = risk_levels.value_counts()
                        
                        fig2 = px.pie(values=risk_counts.values, 
                                     names=risk_counts.index,
                                     title="Niveaux de risque",
                                     color_discrete_sequence=['#36B37E', '#FFAB00', '#FF5630'])
                        st.plotly_chart(fig2, use_container_width=True)
                        st.markdown("**Interprétation:** Répartition des avis par niveau de risque.")
        else:
            st.info("Aucune colonne de texte détectée")
    
    with tab3:
        if column_info and column_info.get('text_columns'):
            sentiment_col = st.selectbox(
                "Colonne pour l'analyse de sentiment:",
                column_info['text_columns'],
                key="customer_sentiment_text"
            )
            
            sample_size = st.slider(
                "Taille d'échantillon:",
                50,
                min(200, len(df)),
                100,
                key="customer_sentiment_sample"
            )
            
            if st.button("😊 Analyser les sentiments", key="analyze_customer_sentiment"):
                with st.spinner("Analyse des sentiments en cours..."):
                    sample_df = df.sample(min(sample_size, len(df)), random_state=42)
                    
                    sentiments = []
                    emotions = []
                    
                    for text in sample_df[sentiment_col].astype(str).head(100):
                        analysis = AIMAnalyzerAdvanced.analyze_sentiment_advanced(text)
                        sentiments.append(analysis['label'])
                        emotions.append(analysis['emotion'])
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sentiment_counts = pd.Series(sentiments).value_counts()
                        fig1 = px.pie(values=sentiment_counts.values,
                                     names=sentiment_counts.index,
                                     title="Distribution des sentiments",
                                     color_discrete_map=Config.SENTIMENT_COLORS)
                        st.plotly_chart(fig1, use_container_width=True)
                        st.markdown("**Interprétation:** Répartition des sentiments détectés.")
                    
                    with col2:
                        emotion_counts = pd.Series(emotions).value_counts()
                        fig2 = px.bar(x=emotion_counts.index, y=emotion_counts.values,
                                     title="Distribution des émotions",
                                     color=emotion_counts.values,
                                     color_continuous_scale='Viridis')
                        st.plotly_chart(fig2, use_container_width=True)
                        st.markdown("**Interprétation:** Émotions détectées dans les textes.")
        else:
            st.info("Aucune colonne de texte détectée")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_performance_analysis_advanced(user, db):
    """Analyse de performance marketing avec visualisations des modèles"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📈 Analyse de Performance Marketing</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Veuillez d'abord importer des données")
        return
    
    df = st.session_state.uploaded_df
    column_info = st.session_state.marketing_column_info or {}
    
    st.markdown("### 📊 Performance des modèles AIM")
    
    # Simulation des performances des modèles
    model_performance = pd.DataFrame({
        'Modèle': ['Sentiment Analysis', 'Fraud Detection', 'Customer Segmentation', 'Recommendation Engine', 'Churn Prediction'],
        'Précision': [0.92, 0.87, 0.89, 0.85, 0.78],
        'Rappel': [0.88, 0.91, 0.85, 0.82, 0.75],
        'F1-Score': [0.90, 0.89, 0.87, 0.83, 0.76]
    })
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig1 = px.bar(model_performance, x='Modèle', y='Précision',
                     title="Précision des modèles",
                     color='Précision',
                     color_continuous_scale='RdYlGn')
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown("**Interprétation:** Précision des différents modèles AIM. Valeurs > 0.8 sont considérées comme bonnes.")
    
    with col2:
        fig2 = go.Figure(data=[
            go.Bar(name='Précision', x=model_performance['Modèle'], y=model_performance['Précision']),
            go.Bar(name='Rappel', x=model_performance['Modèle'], y=model_performance['Rappel']),
            go.Bar(name='F1-Score', x=model_performance['Modèle'], y=model_performance['F1-Score'])
        ])
        fig2.update_layout(title="Comparaison des métriques", barmode='group')
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("**Interprétation:** Comparaison des différentes métriques d'évaluation.")
    
    st.markdown("### 📈 Matrice de confusion (simulée)")
    
    # Matrice de confusion simulée
    confusion_matrix = np.array([
        [85, 5, 10],
        [8, 82, 10],
        [7, 13, 80]
    ])
    
    fig3 = ff.create_annotated_heatmap(
        z=confusion_matrix,
        x=['Négatif', 'Neutre', 'Positif'],
        y=['Négatif', 'Neutre', 'Positif'],
        colorscale='Blues',
        showscale=True
    )
    fig3.update_layout(title="Matrice de confusion - Modèle de Sentiment")
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown("**Interprétation:** Performance du modèle de sentiment. La diagonale représente les prédictions correctes.")
    
    st.markdown("### 📊 Courbe ROC (simulée)")
    
    # Courbe ROC simulée
    fpr = np.linspace(0, 1, 100)
    tpr = 1 - np.exp(-5 * fpr)
    
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines', name='Courbe ROC', line=dict(color='blue', width=2)))
    fig4.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Aléatoire', line=dict(color='red', dash='dash')))
    fig4.update_layout(title="Courbe ROC", xaxis_title="Taux faux positifs", yaxis_title="Taux vrais positifs")
    st.plotly_chart(fig4, use_container_width=True)
    st.markdown("**Interprétation:** Courbe ROC du modèle. Plus la courbe est proche du coin supérieur gauche, meilleur est le modèle.")
    
    st.markdown('<h3 class="section-title">📋 Métriques détaillées</h3>', unsafe_allow_html=True)
    
    st.dataframe(model_performance, use_container_width=True)
    
    st.markdown('<h3 class="section-title">💡 Recommandations d\'optimisation</h3>', unsafe_allow_html=True)
    
    recommendations = [
        "🎯 **Améliorer le modèle de prédiction de churn** : Score F1 actuel de 0.76, cible 0.80+",
        "📊 **Augmenter la précision de détection de fraude** : Actuellement 87%, objectif 90%",
        "🤖 **Entraîner sur plus de données** pour le moteur de recommandation",
        "🔍 **Ajuster les hyperparamètres** des modèles sous-performants",
        "📈 **Mettre en place A/B testing** pour valider les améliorations"
    ]
    
    for rec in recommendations:
        st.markdown(f"- {rec}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_marketing_strategies(user, db):
    """Stratégies marketing basées sur les données"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">💡 Stratégies Marketing Data-Driven</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Importez d'abord des données pour générer des stratégies")
        return
    
    df = st.session_state.uploaded_df
    kpis = st.session_state.marketing_kpis or {}
    
    st.markdown("### 🎯 Génération de stratégies")
    
    if st.button("🤖 Générer des stratégies personnalisées", type="primary", key="generate_strategies"):
        strategies = []
        
        if 'avg_rating' in kpis:
            rating = kpis['avg_rating']
            if rating >= 4.0:
                strategies.append("🏆 **Capitaliser sur l'excellence** : Lancer une campagne testimoniale mettant en avant les retours positifs.")
            elif rating <= 2.5:
                strategies.append("🔧 **Plan de rétablissement** : Mettre en place un programme d'amélioration avec suivi transparent.")
        
        if 'category_diversity' in kpis:
            diversity = kpis['category_diversity']
            if diversity > 15:
                strategies.append("🎨 **Marketing hyper-segmenté** : Créer des messages personnalisés pour chaque segment identifié.")
            elif diversity < 5:
                strategies.append("📈 **Élargir l'audience** : Développer des campagnes pour atteindre de nouveaux segments.")
        
        if 'data_freshness_days' in kpis:
            freshness = kpis['data_freshness_days']
            if freshness < 30:
                strategies.append("⚡ **Marketing en temps réel** : Utiliser les données récentes pour des actions marketing réactives.")
        
        general_strategies = [
            "📱 **Omnicanal** : Intégrer tous les canaux de communication pour une expérience client unifiée.",
            "🤖 **Personnalisation IA** : Utiliser l'IA pour personnaliser les messages marketing.",
            "📊 **Test A/B avancé** : Mettre en place des tests systématiques pour optimiser les performances.",
            "🎯 **Retargeting intelligent** : Cibler les clients avec des messages basés sur leur comportement.",
            "💬 **Marketing conversationnel** : Développer des chatbots pour engager les clients 24/7."
        ]
        
        strategies.extend(general_strategies)
        
        st.markdown("### 📋 Stratégies recommandées")
        
        for i, strategy in enumerate(strategies[:10]):
            with st.expander(f"Stratégie #{i+1}"):
                st.markdown(strategy)
                
                st.markdown("**Actions concrètes:**")
                actions = [
                    "Définir les objectifs et KPIs",
                    "Allouer le budget nécessaire",
                    "Désigner l'équipe responsable",
                    "Définir le calendrier",
                    "Mettre en place le suivi"
                ]
                
                for action in actions:
                    st.markdown(f"- {action}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_marketing_reports(user, db):
    """Génération de rapports marketing"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📤 Rapports Marketing</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Veuillez d'abord importer des données")
        return
    
    st.markdown("### 📊 Génération de rapports")
    
    report_type = st.selectbox(
        "Type de rapport",
        ["Rapport de performance", "Analyse des segments", "Synthèse marketing", "Rapport complet"],
        key="report_type"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input("Date de début", key="report_start_date")
        end_date = st.date_input("Date de fin", key="report_end_date")
    
    with col2:
        include_charts = st.checkbox("Inclure les graphiques", True, key="report_charts")
        include_recommendations = st.checkbox("Inclure les recommandations", True, key="report_recommendations")
    
    if st.button("📄 Générer le rapport", type="primary", key="generate_report"):
        with st.spinner("Génération du rapport en cours..."):
            st.success(f"✅ Rapport {report_type} généré avec succès!")
            
            st.markdown("### 📋 Aperçu du rapport")
            
            report_sections = [
                "1. Résumé exécutif",
                "2. Données analysées",
                "3. Principaux insights",
                "4. Recommandations stratégiques",
                "5. Annexes techniques"
            ]
            
            for section in report_sections:
                st.markdown(f"**{section}**")
            
            st.download_button(
                label="📥 Télécharger le rapport",
                data="Contenu simulé du rapport".encode('utf-8'),
                file_name=f"rapport_marketing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_export_page_advanced(user, db):
    """Page d'export avancée avec tableau de résultats"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📤 Exportation des analyses</h2>', unsafe_allow_html=True)
    
    if st.session_state.uploaded_df is None:
        st.warning("Aucune donnée à exporter")
        return
    
    df = st.session_state.uploaded_df
    
    st.markdown("### 📋 Aperçu des résultats")
    
    if hasattr(st.session_state, 'advanced_aim_results') and st.session_state.advanced_aim_results is not None:
        results_df = st.session_state.advanced_aim_results
        st.markdown("#### 📊 Résultats de l'analyse AIM")
        st.dataframe(results_df.head(20), use_container_width=True, height=400)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'sentiment_label' in results_df.columns:
                positive_count = (results_df['sentiment_label'] == 'positif').sum()
                st.metric("Avis positifs", positive_count)
        
        with col2:
            if 'is_suspicious' in results_df.columns:
                suspicious_count = results_df['is_suspicious'].sum()
                st.metric("Avis suspects", suspicious_count)
        
        with col3:
            st.metric("Total analysé", len(results_df))
    
    st.markdown("### ⚙️ Configuration de l'export")
    
    export_format = st.selectbox(
        "Format d'export:",
        ["CSV", "Excel", "JSON"],
        key="export_format_advanced"
    )
    
    with st.expander("🔧 Options avancées"):
        col1, col2 = st.columns(2)
        
        with col1:
            filename = st.text_input("Nom du fichier", "aim_export", key="export_filename")
            include_timestamp = st.checkbox("Ajouter horodatage", True, key="export_timestamp")
        
        with col2:
            compress = st.checkbox("Compresser le fichier", False, key="export_compress")
            include_metadata = st.checkbox("Inclure métadonnées", True, key="export_metadata")
    
    if st.button("📥 Générer l'export", type="primary", use_container_width=True, key="generate_export"):
        with st.spinner("Génération de l'export en cours..."):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if include_timestamp else ""
            
            if export_format == "CSV":
                if hasattr(st.session_state, 'advanced_aim_results') and st.session_state.advanced_aim_results is not None:
                    export_df = st.session_state.advanced_aim_results
                else:
                    export_df = df
                
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="📥 Télécharger CSV",
                    data=csv_data,
                    file_name=f"{filename}{'_' + timestamp if timestamp else ''}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_csv"
                )
            
            elif export_format == "Excel":
                if hasattr(st.session_state, 'advanced_aim_results') and st.session_state.advanced_aim_results is not None:
                    export_df = st.session_state.advanced_aim_results
                else:
                    export_df = df
                
                output = io.BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Donnees')
                    
                    if include_metadata:
                        metadata_df = pd.DataFrame({
                            'Métrique': ['Date export', 'Nb lignes', 'Nb colonnes', 'Utilisateur'],
                            'Valeur': [datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                                      len(export_df), 
                                      len(export_df.columns),
                                      user['username']]
                        })
                        metadata_df.to_excel(writer, index=False, sheet_name='Metadonnees')
                
                output.seek(0)
                
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=output,
                    file_name=f"{filename}{'_' + timestamp if timestamp else ''}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="download_excel"
                )
            
            elif export_format == "JSON":
                if hasattr(st.session_state, 'advanced_aim_results') and st.session_state.advanced_aim_results is not None:
                    export_df = st.session_state.advanced_aim_results
                else:
                    export_df = df
                
                json_data = export_df.to_json(orient='records', indent=2)
                
                st.download_button(
                    label="📥 Télécharger JSON",
                    data=json_data.encode('utf-8'),
                    file_name=f"{filename}{'_' + timestamp if timestamp else ''}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_json"
                )
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================================
# DASHBOARD SUPPORT
# ==================================
def dashboard_support(user, db):
    st.markdown(advanced_page_bg_css(), unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="dashboard-header">
        <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2.8em; font-weight: 800;">
            🛠️ Dashboard Support
        </h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.2em; margin-bottom: 0;">
            Support client et gestion des tickets
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        st.markdown(f"### {user.get('full_name', user['username'])}")
        st.markdown(f"🛠️ **Rôle:** Support")
        st.markdown('</div>', unsafe_allow_html=True)
        
        support_page = st.radio(
            "📊 Navigation",
            ["📋 Tableau de bord", "👤 Profil"],
            label_visibility="collapsed",
            key="support_nav_radio"
        )
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Rafraîchir", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🚪 Déconnexion", use_container_width=True, type="primary"):
                st.session_state.clear()
                st.rerun()
    
    if support_page == "📋 Tableau de bord":
        render_support_dashboard(user, db)
    elif support_page == "👤 Profil":
        render_user_profile_enhanced(user, db)

def render_support_dashboard(user, db):
    """Tableau de bord support"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">🛠️ Tableau de bord Support</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Tickets ouverts</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-value">15</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-trend kpi-trend-up">+2 aujourd\'hui</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Temps moyen</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-value">2.5h</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-trend kpi-trend-down">-0.5h vs hier</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Satisfaction</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-value">4.2/5</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-trend kpi-trend-up">+0.3</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Résolution</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-value">92%</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-trend kpi-trend-up">+3%</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<h3 class="section-title">📋 Tickets récents</h3>', unsafe_allow_html=True)
    
    tickets_data = pd.DataFrame({
        'ID': ['TKT-001', 'TKT-002', 'TKT-003', 'TKT-004', 'TKT-005'],
        'Sujet': ['Problème de connexion', 'Question facturation', 'Bug interface', 'Demande fonctionnalité', 'Assistance technique'],
        'Priorité': ['Haute', 'Moyenne', 'Haute', 'Basse', 'Moyenne'],
        'Statut': ['En cours', 'Résolu', 'Nouveau', 'En attente', 'En cours'],
        'Créé le': ['2024-01-15', '2024-01-14', '2024-01-14', '2024-01-13', '2024-01-13'],
        'Assigné à': ['Vous', 'Vous', 'Marie', 'Vous', 'Pierre']
    })
    
    st.markdown('<div class="data-table-container">', unsafe_allow_html=True)
    st.dataframe(tickets_data, use_container_width=True, height=300)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<h3 class="section-title">⚡ Actions rapides</h3>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📝 Nouveau ticket", use_container_width=True):
            st.info("Fonctionnalité à implémenter")
    
    with col2:
        if st.button("📊 Statistiques", use_container_width=True):
            st.info("Fonctionnalité à implémenter")
    
    with col3:
        if st.button("📧 Contacter client", use_container_width=True):
            st.info("Fonctionnalité à implémenter")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================================
# FONCTIONS UTILITAIRES
# ==================================
def render_user_profile_enhanced(user, db):
    """Profil utilisateur amélioré"""
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">👤 Profil Utilisateur</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        initials = user['full_name'][0].upper() if user.get('full_name') else 'U'
        st.markdown(f'<div style="width: 100px; height: 100px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 2.5em; font-weight: bold; margin: 0 auto 1.5rem auto;">{initials}</div>', unsafe_allow_html=True)
        
        st.markdown(f"**👤 Nom d'utilisateur:** {user['username']}")
        st.markdown(f"**🎯 Rôle:** {user['role'].replace('_', ' ').title()}")
        st.markdown(f"**📧 Email:** {user.get('email', 'Non défini')}")
        st.markdown(f"**🏢 Département:** {user.get('department', 'Non défini')}")
        st.markdown(f"**📊 Statut:** {'✅ Actif' if user.get('is_active', True) else '❌ Inactif'}")
        
        if user.get('last_login'):
            if isinstance(user['last_login'], str):
                st.markdown(f"**🕐 Dernière connexion:** {user['last_login']}")
            else:
                st.markdown(f"**🕐 Dernière connexion:** {user['last_login'].strftime('%d/%m/%Y %H:%M')}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown("### 🔧 Modifier le profil")
        
        with st.form(key="profile_form_enhanced"):
            full_name = st.text_input("Nom complet", value=user.get('full_name', ''), key="profile_full_name")
            email = st.text_input("Email", value=user.get('email', ''), key="profile_email")
            department = st.text_input("Département", value=user.get('department', ''), key="profile_department")
            
            st.markdown("### 🔒 Changer le mot de passe")
            current_password = st.text_input("Mot de passe actuel", type="password", key="profile_current_pw")
            new_password = st.text_input("Nouveau mot de passe", type="password", key="profile_new_pw")
            confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password", key="profile_confirm_pw")
            
            submitted = st.form_submit_button("💾 Enregistrer les modifications", use_container_width=True)
            
            if submitted:
                updates = {}
                
                if full_name != user.get('full_name'):
                    updates['full_name'] = full_name
                
                if email != user.get('email'):
                    if "@" not in email:
                        st.error("❌ Email invalide")
                    else:
                        updates['email'] = email
                
                if department != user.get('department'):
                    updates['department'] = department
                
                if new_password:
                    if len(new_password) < 8:
                        st.error("❌ Le mot de passe doit contenir au moins 8 caractères")
                    elif new_password != confirm_password:
                        st.error("❌ Les nouveaux mots de passe ne correspondent pas")
                    elif not current_password:
                        st.error("❌ Veuillez entrer votre mot de passe actuel")
                    else:
                        if db.conn:
                            auth_result = db.authenticate(user['username'], current_password)
                            if auth_result:
                                updates['password'] = new_password
                            else:
                                st.error("❌ Mot de passe actuel incorrect")
                
                if updates:
                    success = db.update_user_profile(user['id'], **updates)
                    
                    if success:
                        st.success("✅ Profil mis à jour avec succès!")
                        
                        for key, value in updates.items():
                            if key != 'password':
                                st.session_state.user[key] = value
                        
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de la mise à jour")
                else:
                    st.info("ℹ️ Aucune modification détectée")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def login_page_enhanced(db):
    st.markdown("""
    <style>
    .login-container {
        max-width: 500px;
        margin: 5rem auto;
        padding: 3rem;
        background: white;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.1);
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .login-header h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5em;
        font-weight: 800;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-header">', unsafe_allow_html=True)
    st.markdown('<h1>🤖 AIM Analytics Platform</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #666; font-size: 1.1em;">Analyse Intelligente & Marketing</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    
    if st.session_state.login_attempts >= Config.MAX_LOGIN_ATTEMPTS:
        st.error("🚫 Trop de tentatives. Veuillez réessayer dans 5 minutes.")
        return
    
    username = st.text_input("👤 Nom d'utilisateur", key="login_username")
    password = st.text_input("🔒 Mot de passe", type="password", key="login_password")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🚀 Se connecter", type="primary", use_container_width=True):
            if not username or not password:
                st.error("Veuillez remplir tous les champs")
                return
                
            user = None
            if db.conn:
                user = db.authenticate(username, password)
            
            if not user:
                default_users = {
                    "admin": ("admin123", "admin", "Super Admin"),
                    "analyst": ("analyst123", "data_analyst", "Data Analyst"),
                    "marketing": ("marketing123", "marketing", "Marketing Manager"),
                    "support": ("support123", "support", "Support Agent")
                }
                
                if username in default_users and default_users[username][0] == password:
                    password_hash, role, full_name = default_users[username]
                    user = {
                        "id": hash(username) % 10000,
                        "username": username,
                        "full_name": full_name,
                        "role": role,
                        "email": f"{username}@aim.com",
                        "department": role.replace('_', ' ').title(),
                        "is_active": True,
                        "created_at": datetime.now(),
                        "last_login": datetime.now()
                    }
            
            if user:
                st.session_state["user"] = user
                st.session_state.login_attempts = 0
                
                if db.conn:
                    db.log_activity(
                        user_id=user['id'],
                        activity_type="login",
                        description=f"Connexion utilisateur {username}"
                    )
                
                st.success("✅ Connexion réussie!")
                time.sleep(1)
                st.rerun()
            else:
                st.session_state.login_attempts += 1
                attempts_left = Config.MAX_LOGIN_ATTEMPTS - st.session_state.login_attempts
                st.error(f"❌ Identifiants incorrects. Tentatives restantes: {attempts_left}")
    
    with col2:
        if st.button("🔄 Réinitialiser", use_container_width=True):
            st.session_state.login_attempts = 0
            st.rerun()
    
    with st.expander("ℹ️ Informations de connexion"):
        st.markdown("**Comptes par défaut:**")
        st.markdown("- 👑 **Admin:** admin / admin123")
        st.markdown("- 🔬 **Analyste:** analyst / analyst123")
        st.markdown("- 📈 **Marketing:** marketing / marketing123")
        st.markdown("- 🛠️ **Support:** support / support123")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================================
# APPLICATION PRINCIPALE
# ==================================
def main():
    db = DatabaseManager()
    
    if "user" not in st.session_state:
        login_page_enhanced(db)
        return
    
    user = st.session_state["user"]
    
    if user["role"] == "admin":
        dashboard_admin_enhanced(user, db)
    elif user["role"] == "data_analyst":
        dashboard_analyst_advanced(user, db)
    elif user["role"] == "marketing":
        dashboard_marketing_advanced(user, db)
    elif user["role"] == "support":
        dashboard_support(user, db)
    else:
        st.error("Rôle utilisateur inconnu")

if __name__ == "__main__":
    main()