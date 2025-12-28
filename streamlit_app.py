# ================================
# AIM ANALYTICS PLATFORM - Streamlit Cloud
# ================================
import streamlit as st
import os
import psycopg2
from psycopg2 import pool
import bcrypt
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import time
import io
import re
from langdetect import detect 
from collections import Counter
import warnings
import urllib.parse
warnings.filterwarnings('ignore')

# Gestion des imports optionnels
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# ==================================
#    CONFIGURATION STREAMLIT
# ==================================
st.set_page_config(
    page_title="AIM Analytics Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configuration
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
        'positif': '#55C592',
        'négatif': '#FA5771',
        'neutre': '#F1C24D',
        'sarcastique': '#83C9FF'
    }
    
    MAX_FILE_SIZE_MB = 100
    MAX_LOGIN_ATTEMPTS = 5
    
    DB_POOL_MIN = 1
    DB_POOL_MAX = 5

# =======================================
#      GESTION DE LA BASE DE DONNÉES
# =======================================
@st.cache_resource
def get_database_manager():
    return DatabaseManager()

class DatabaseManager:
    def __init__(self):
        self.connection_pool = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialise la connexion à la base de données silencieusement"""
        try:
            # Récupération des paramètres
            db_params = self._get_db_params()
            
            if not db_params:
                return
            
            # Création du pool de connexions
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                Config.DB_POOL_MIN,
                Config.DB_POOL_MAX,
                **db_params
            )
            
            # Test de connexion silencieux
            conn = self.get_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    self._create_tables()
                    # Supprimé: self._init_default_users() - Pas d'utilisateurs par défaut
                finally:
                    self.return_connection(conn)
                
        except Exception as e:
            print(f"Erreur DB initialisation: {str(e)}")
    
    def get_connection(self):
        """Obtient une connexion depuis le pool"""
        if self.connection_pool:
            try:
                return self.connection_pool.getconn()
            except:
                return None
        return None
    
    def return_connection(self, conn):
        """Retourne une connexion au pool"""
        if self.connection_pool and conn:
            try:
                self.connection_pool.putconn(conn)
            except:
                pass
    
    def _get_db_params(self):
        """Récupère les paramètres de connexion silencieusement"""
        try:
            if 'RENDER_DB_URL' in st.secrets:
                url = st.secrets['RENDER_DB_URL']
                url = self._fix_render_url(url)
                return self._parse_db_url(url)
            
            if 'DATABASE_URL' in st.secrets:
                return self._parse_db_url(st.secrets['DATABASE_URL'])
            
            required_params = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
            if all(param in st.secrets for param in required_params):
                return {
                    'host': st.secrets['DB_HOST'],
                    'database': st.secrets['DB_NAME'],
                    'user': st.secrets['DB_USER'],
                    'password': st.secrets['DB_PASSWORD'],
                    'port': int(st.secrets.get('DB_PORT', 5432))
                }
            
            return None
            
        except Exception as e:
            print(f"Erreur configuration DB: {e}")
            return None
    
    def _fix_render_url(self, url):
        """Corrige les URLs Render incomplètes"""
        if not url:
            return url
        
        if '-a/' in url and ':5432' not in url:
            parts = url.split('@')
            if len(parts) == 2:
                credentials = parts[0]
                host_db = parts[1]
                
                if host_db.endswith('-a/'):
                    host_db = host_db.replace('-a/', '-a.frankfurt-postgres.render.com:5432/')
                elif '/aim_plateforme_db' in host_db:
                    host_part = host_db.split('/')[0]
                    if not host_part.endswith('.render.com'):
                        host_db = host_part + '.frankfurt-postgres.render.com:5432/aim_plateforme_db'
                
                url = f"{credentials}@{host_db}"
        
        return url
    
    def _parse_db_url(self, url):
        """Parse une URL de base de données"""
        try:
            if not url:
                return None
            
            parsed = urllib.parse.urlparse(url)
            
            return {
                'host': parsed.hostname,
                'database': parsed.path[1:] if parsed.path else 'postgres',
                'user': parsed.username,
                'password': parsed.password,
                'port': parsed.port or 5432
            }
        except Exception as e:
            print(f"Erreur parsing URL DB: {e}")
            return None
    
    def _create_tables(self):
        """Crée les tables nécessaires"""
        conn = self.get_connection()
        if not conn:
            return
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    full_name VARCHAR(100) DEFAULT 'Utilisateur',
                    email VARCHAR(100),
                    password_hash TEXT NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    department VARCHAR(50),
                    is_active BOOLEAN DEFAULT true,
                    is_first_login BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_login TIMESTAMP,
                    preferences JSONB DEFAULT '{}'
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    session_token TEXT,
                    login_time TIMESTAMP DEFAULT NOW(),
                    logout_time TIMESTAMP,
                    ip_address VARCHAR(50),
                    user_agent TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_recommendations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    recommendation_type VARCHAR(50),
                    content TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    implemented BOOLEAN DEFAULT false,
                    implemented_at TIMESTAMP,
                    result_rating INTEGER CHECK (result_rating >= 1 AND result_rating <= 5)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_uploads (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    file_name VARCHAR(255),
                    file_size INTEGER,
                    upload_time TIMESTAMP DEFAULT NOW(),
                    data_type VARCHAR(50),
                    record_count INTEGER,
                    columns_count INTEGER,
                    status VARCHAR(20) DEFAULT 'uploaded'
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    activity_type VARCHAR(50),
                    description TEXT,
                    ip_address VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Nouvelle table pour les données dynamiques des dashboards
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_metrics (
                    id SERIAL PRIMARY KEY,
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value FLOAT NOT NULL,
                    metric_type VARCHAR(50),
                    user_role VARCHAR(50),
                    period VARCHAR(20),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Table pour les données marketing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marketing_data (
                    id SERIAL PRIMARY KEY,
                    campaign_name VARCHAR(100),
                    impressions INTEGER,
                    clicks INTEGER,
                    conversions INTEGER,
                    spend DECIMAL(10,2),
                    revenue DECIMAL(10,2),
                    date DATE,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            
            
            cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id SERIAL PRIMARY KEY,
            subject VARCHAR(200) NOT NULL,
            description TEXT,
            category VARCHAR(50),
            priority VARCHAR(20) DEFAULT 'Moyenne',
            client_name VARCHAR(100) NOT NULL,
            client_email VARCHAR(100),
            status VARCHAR(20) DEFAULT 'Ouvert',
            assigned_to VARCHAR(50),
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            resolved_at TIMESTAMP,
            first_response_at TIMESTAMP
        )
    """)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur création tables: {e}")
        finally:
            cursor.close()
            self.return_connection(conn)

    
    def can_delete_user(self, user_id, current_admin_id):
        """Vérifie si un utilisateur peut être supprimé"""
        if not self.connection_pool:
            return False, "Base de données non disponible"
        
        conn = self.get_connection()
        if not conn:
            return False, "Erreur de connexion"
        
        cursor = conn.cursor()
        try:
            # Convertir les IDs en types Python natifs
            user_id_int = int(user_id)
            current_admin_id_int = int(current_admin_id)
            
            # Vérifier si l'utilisateur existe
            cursor.execute("SELECT id, role FROM users WHERE id = %s", (user_id_int,))
            user_result = cursor.fetchone()
            
            if not user_result:
                return False, "Utilisateur non trouvé"
            
            # Ne pas permettre de se supprimer soi-même
            if user_id_int == current_admin_id_int:
                return False, "Vous ne pouvez pas vous supprimer vous-même"
            
            user_id_db, user_role = user_result
            
            # Vérifier si c'est le dernier administrateur
            if user_role == 'admin':
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND id != %s", (user_id_int,))
                other_admins = cursor.fetchone()[0]
                
                if other_admins == 0:
                    return False, "Impossible de supprimer le dernier administrateur"
            
            return True, "Utilisateur peut être supprimé"
            
        except Exception as e:
            print(f"Erreur can_delete_user: {e}")
            return False, f"Erreur de vérification: {str(e)}"
        finally:
            cursor.close()
            self.return_connection(conn)
            
    def delete_user(self, user_id):
        """Supprime un utilisateur de la base de données"""
        if not self.connection_pool:
            return False, "Base de données non disponible"
        
        conn = self.get_connection()
        if not conn:
            return False, "Erreur de connexion"
        
        cursor = conn.cursor()
        try:
            # Convertir user_id en type Python natif (int)
            user_id_int = int(user_id)
            
            # Vérifier si c'est le dernier administrateur
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND id != %s", (user_id_int,))
            other_admins = cursor.fetchone()[0]
            
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id_int,))
            user_role_result = cursor.fetchone()
            user_role = user_role_result[0] if user_role_result else None
            
            # Empêcher la suppression du dernier admin
            if user_role == 'admin' and other_admins == 0:
                return False, "Impossible de supprimer le dernier administrateur"
            
            # Supprimer l'utilisateur
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id_int,))
            conn.commit()
            
            return True, "Utilisateur supprimé avec succès"
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur delete_user: {e}")
            return False, f"Erreur lors de la suppression: {str(e)}"
        finally:
            cursor.close()
            self.return_connection(conn)
        
    def authenticate_user(self, username, password):
        """Authentifie un utilisateur avec bcrypt"""
        if not self.connection_pool:
            return None
        
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, username, full_name, email, password_hash, role, 
                       department, is_active, is_first_login, last_login
                FROM users 
                WHERE username = %s AND is_active = true
            """, (username,))
            
            user = cursor.fetchone()
            
            if user:
                user_dict = {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[2] or 'Utilisateur',
                    'email': user[3] or '',
                    'password_hash': user[4],
                    'role': user[5] or 'user',
                    'department': user[6] or '',
                    'is_active': bool(user[7]),
                    'is_first_login': bool(user[8]),
                    'last_login': user[9]
                }
                
                if bcrypt.checkpw(password.encode(), user_dict['password_hash'].encode()):
                    cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user_dict['id'],))
                    conn.commit()
                    del user_dict['password_hash']
                    return user_dict
            
            return None
            
        except Exception as e:
            print(f"Erreur authentification: {e}")
            return None
        finally:
            cursor.close()
            self.return_connection(conn)

    def update_user_password(self, user_id, new_password):
        """Met à jour le mot de passe d'un utilisateur"""
        if not self.connection_pool:
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            cursor.execute("""
                UPDATE users 
                SET password_hash = %s, is_first_login = false, last_login = NOW()
                WHERE id = %s
            """, (hashed, user_id))
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur mise à jour mot de passe: {e}")
            return False
        finally:
            cursor.close()
            self.return_connection(conn)

    

    def reset_user_password(self, user_id, new_password="reset123"):
        """Réinitialise le mot de passe d'un utilisateur spécifique"""
        if not self.connection_pool:
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            cursor.execute("""
                UPDATE users 
                SET password_hash = %s, is_first_login = true, last_login = NOW()
                WHERE id = %s
            """, (hashed, user_id))
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur réinitialisation mot de passe: {e}")
            return False
        finally:
            cursor.close()
            self.return_connection(conn)

    def update_user_profile(self, user_id, **kwargs):
        """Met à jour le profil utilisateur"""
        if not self.connection_pool:
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
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
                conn.commit()
            
            return True
        except:
            conn.rollback()
            return False
        finally:
            cursor.close()
            self.return_connection(conn)

    def log_activity(self, user_id, activity_type, description, ip_address="127.0.0.1"):
        """Log une activité"""
        if not self.connection_pool:
            return
        
        conn = self.get_connection()
        if not conn:
            return
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO activity_logs (user_id, activity_type, description, ip_address)
                VALUES (%s, %s, %s, %s)
            """, (user_id, activity_type, description, ip_address))
            conn.commit()
        except:
            conn.rollback()
        finally:
            cursor.close()
            self.return_connection(conn)

    def get_activity_logs(self, limit=100):
        """Récupère les logs d'activité"""
        if not self.connection_pool:
            return []
        
        conn = self.get_connection()
        if not conn:
            return []
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT al.*, u.username, u.full_name 
                FROM activity_logs al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT %s
            """, (limit,))
            logs = cursor.fetchall()
            return logs
        except:
            return []
        finally:
            cursor.close()
            self.return_connection(conn)

    def get_system_stats(self):
        """Récupère les statistiques système DYNAMIQUES"""
        if not self.connection_pool:
            return self._get_default_stats()
        
        conn = self.get_connection()
        if not conn:
            return self._get_default_stats()
        
        cursor = conn.cursor()
        try:
            stats = {}
            
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = true")
            stats['active_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(last_login) = CURRENT_DATE")
            stats['today_logins'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM data_uploads")
            stats['total_uploads'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM activity_logs WHERE DATE(created_at) = CURRENT_DATE")
            stats['today_activities'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_first_login = true")
            stats['first_login_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
            stats['users_by_role'] = dict(cursor.fetchall())
            
            # Statistiques dynamiques pour les dashboards
            cursor.execute("SELECT SUM(file_size) FROM data_uploads WHERE file_size IS NOT NULL")
            total_size = cursor.fetchone()[0] or 0
            stats['total_data_size_mb'] = round(total_size / (1024*1024), 2) if total_size > 0 else 0
            
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) 
                FROM activity_logs 
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            stats['active_users_today'] = cursor.fetchone()[0]
            
            # Générer des données d'activité réelles des 7 derniers jours
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM activity_logs
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            activity_data = cursor.fetchall()
            stats['weekly_activity'] = activity_data
            
            return stats
        except Exception as e:
            print(f"Erreur get_system_stats: {e}")
            return self._get_default_stats()
        finally:
            cursor.close()
            self.return_connection(conn)

    def _get_default_stats(self):
        """Retourne des statistiques par défaut (seulement si DB non disponible)"""
        return {
            'total_users': 0,
            'active_users': 0,
            'today_logins': 0,
            'total_uploads': 0,
            'today_activities': 0,
            'first_login_users': 0,
            'users_by_role': {},
            'total_data_size_mb': 0,
            'active_users_today': 0,
            'weekly_activity': []
        }
    def get_analyst_metrics(self, user_role=None):
        """Récupère les métriques pour analystes"""
        if not self.connection_pool:
            return {}
        
        conn = self.get_connection()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        try:
            metrics = {}
            
            # Statistiques des données uploadées
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_datasets,
                    SUM(record_count) as total_records,
                    SUM(columns_count) as total_columns,
                    COUNT(DISTINCT data_type) as data_types
                FROM data_uploads
                WHERE status = 'uploaded'
            """)
            
            row = cursor.fetchone()
            if row:
                metrics['datasets'] = row[0] or 0
                metrics['records'] = row[1] or 0
                metrics['columns'] = row[2] or 0
                metrics['data_types'] = row[3] or 0
            
            # Distribution par type de données
            cursor.execute("""
                SELECT data_type, COUNT(*) as count
                FROM data_uploads
                WHERE data_type IS NOT NULL
                GROUP BY data_type
            """)
            
            data_distribution = cursor.fetchall()
            metrics['data_distribution'] = data_distribution
            
            # Activité d'upload récente
            cursor.execute("""
                SELECT 
                    DATE(upload_time) as date,
                    COUNT(*) as uploads,
                    SUM(record_count) as records
                FROM data_uploads
                WHERE upload_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(upload_time)
                ORDER BY date
            """)
            
            upload_activity = cursor.fetchall()
            metrics['upload_activity'] = upload_activity
            
            # Taille moyenne des datasets
            cursor.execute("""
                SELECT 
                    AVG(record_count) as avg_records,
                    AVG(columns_count) as avg_columns,
                    AVG(file_size) as avg_size_kb
                FROM data_uploads
                WHERE record_count > 0
            """)
            
            avg_row = cursor.fetchone()
            if avg_row:
                metrics['avg_records'] = round(avg_row[0] or 0, 1)
                metrics['avg_columns'] = round(avg_row[1] or 0, 1)
                metrics['avg_size_kb'] = round((avg_row[2] or 0) / 1024, 1)
            
            return metrics
            
        except Exception as e:
            print(f"Erreur get_analyst_metrics: {e}")
            return {}
        finally:
            cursor.close()
            self.return_connection(conn)
  
    def _calculate_marketing_metrics_from_data(df):
        """Calcule les métriques marketing à partir d'un DataFrame"""
        metrics = {}
        
        # Compter les campagnes uniques (basé sur la première colonne catégorielle)
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        if categorical_cols:
            metrics['total_campaigns'] = df[categorical_cols[0]].nunique()
        
        # Chercher des colonnes communes de métriques marketing
        impression_cols = [col for col in df.columns if 'impression' in col.lower()]
        click_cols = [col for col in df.columns if 'clic' in col.lower() or 'click' in col.lower()]
        conversion_cols = [col for col in df.columns if 'conversion' in col.lower()]
        spend_cols = [col for col in df.columns if 'dépense' in col.lower() or 'spend' in col.lower() or 'cost' in col.lower()]
        revenue_cols = [col for col in df.columns if 'revenu' in col.lower() or 'revenue' in col.lower()]
        
        # Calculer les sommes si les colonnes existent
        if impression_cols:
            metrics['total_impressions'] = df[impression_cols[0]].sum()
        
        if click_cols:
            metrics['total_clicks'] = df[click_cols[0]].sum()
        
        if conversion_cols:
            metrics['total_conversions'] = df[conversion_cols[0]].sum()
        
        if spend_cols:
            metrics['total_spend'] = df[spend_cols[0]].sum()
        
        if revenue_cols:
            metrics['total_revenue'] = df[revenue_cols[0]].sum()
        
        # Calculer les taux
        if 'total_impressions' in metrics and 'total_clicks' in metrics and metrics['total_impressions'] > 0:
            metrics['ctr'] = (metrics['total_clicks'] / metrics['total_impressions']) * 100
        
        if 'total_clicks' in metrics and 'total_conversions' in metrics and metrics['total_clicks'] > 0:
            metrics['conversion_rate'] = (metrics['total_conversions'] / metrics['total_clicks']) * 100
        
        if 'total_spend' in metrics and 'total_revenue' in metrics and metrics['total_spend'] > 0:
            metrics['roi'] = ((metrics['total_revenue'] - metrics['total_spend']) / metrics['total_spend']) * 100
        
        return metrics        

    def create_new_user(self, username, password, full_name, email, role, department=None):
        """Crée un nouvel utilisateur"""
        if not self.connection_pool:
            return False, "Base de données non disponible"
        
        conn = self.get_connection()
        if not conn:
            return False, "Erreur de connexion"
        
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "Ce nom d'utilisateur existe déjà"
            
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            
            cursor.execute("""
                INSERT INTO users (username, full_name, email, password_hash, role, department, is_first_login)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, full_name, email, hashed, role, department, True))
            
            conn.commit()
            return True, f"Utilisateur {username} créé avec succès"
            
        except Exception as e:
            conn.rollback()
            return False, f"Erreur: {str(e)}"
        finally:
            cursor.close()
            self.return_connection(conn)

    def get_all_users(self):
        """Récupère tous les utilisateurs"""
        if not self.connection_pool:
            return []
        
        conn = self.get_connection()
        if not conn:
            return []
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT id, username, full_name, email, role, department, 
                       is_active, is_first_login, created_at, last_login
                FROM users
                ORDER BY username
            """)
            users = cursor.fetchall()
            return users
        except:
            return []
        finally:
            cursor.close()
            self.return_connection(conn)

    def get_user_by_id(self, user_id):
        """Récupère un utilisateur par son ID"""
        if not self.connection_pool:
            return None
        
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT id, username, full_name, email, role, department, 
                       is_active, is_first_login, created_at, last_login
                FROM users WHERE id = %s
            """, (user_id,))
            user = cursor.fetchone()
            return user
        except:
            return None
        finally:
            cursor.close()
            self.return_connection(conn)

    def update_user_status(self, user_id, is_active):
        """Met à jour le statut d'un utilisateur"""
        if not self.connection_pool:
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (is_active, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except:
            conn.rollback()
            return False
        finally:
            cursor.close()
            self.return_connection(conn)

    

    def get_marketing_metrics(self, user_role=None, period='month'):
        """Récupère les métriques marketing dynamiques"""
        if not self.connection_pool:
            return {}
        
        conn = self.get_connection()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        try:
            metrics = {}
            
            # Récupérer les données de la table marketing_data
            if period == 'month':
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT campaign_name) as campaigns,
                        SUM(impressions) as total_impressions,
                        SUM(clicks) as total_clicks,
                        SUM(conversions) as total_conversions,
                        SUM(spend) as total_spend,
                        SUM(revenue) as total_revenue
                    FROM marketing_data
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                """)
            else:  # all time
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT campaign_name) as campaigns,
                        SUM(impressions) as total_impressions,
                        SUM(clicks) as total_clicks,
                        SUM(conversions) as total_conversions,
                        SUM(spend) as total_spend,
                        SUM(revenue) as total_revenue
                    FROM marketing_data
                """)
            
            row = cursor.fetchone()
            if row:
                metrics['campaigns'] = row[0] or 0
                metrics['impressions'] = row[1] or 0
                metrics['clicks'] = row[2] or 0
                metrics['conversions'] = row[3] or 0
                metrics['spend'] = float(row[4] or 0)
                metrics['revenue'] = float(row[5] or 0)
                metrics['roi'] = round((float(row[5] or 0) - float(row[4] or 0)) / max(float(row[4] or 1), 1) * 100, 2)
                metrics['ctr'] = round((row[2] or 0) / max(row[1] or 1, 1) * 100, 2)
                metrics['conversion_rate'] = round((row[3] or 0) / max(row[2] or 1, 1) * 100, 2)
            
            # Données historiques pour graphiques
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', date) as day,
                    SUM(impressions) as impressions,
                    SUM(clicks) as clicks,
                    SUM(conversions) as conversions,
                    SUM(spend) as spend,
                    SUM(revenue) as revenue
                FROM marketing_data
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE_TRUNC('day', date)
                ORDER BY day
            """)
            
            historical_data = cursor.fetchall()
            metrics['historical_data'] = historical_data
            
            # Top campagnes
            cursor.execute("""
                SELECT 
                    campaign_name,
                    SUM(impressions) as impressions,
                    SUM(clicks) as clicks,
                    SUM(conversions) as conversions,
                    SUM(spend) as spend,
                    SUM(revenue) as revenue
                FROM marketing_data
                GROUP BY campaign_name
                ORDER BY SUM(revenue) DESC
                LIMIT 5
            """)
            
            top_campaigns = cursor.fetchall()
            metrics['top_campaigns'] = top_campaigns
            
            return metrics
            
        except Exception as e:
            print(f"Erreur get_marketing_metrics: {e}")
            return {}
        finally:
            cursor.close()
            self.return_connection(conn)

    def get_analyst_metrics(self, user_role=None):
        """Récupère les métriques pour analystes"""
        if not self.connection_pool:
            return {}
        
        conn = self.get_connection()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        try:
            metrics = {}
            
            # Statistiques des données uploadées
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_datasets,
                    SUM(record_count) as total_records,
                    SUM(columns_count) as total_columns,
                    COUNT(DISTINCT data_type) as data_types
                FROM data_uploads
                WHERE status = 'uploaded'
            """)
            
            row = cursor.fetchone()
            if row:
                metrics['datasets'] = row[0] or 0
                metrics['records'] = row[1] or 0
                metrics['columns'] = row[2] or 0
                metrics['data_types'] = row[3] or 0
            
            # Distribution par type de données
            cursor.execute("""
                SELECT data_type, COUNT(*) as count
                FROM data_uploads
                WHERE data_type IS NOT NULL
                GROUP BY data_type
            """)
            
            data_distribution = cursor.fetchall()
            metrics['data_distribution'] = data_distribution
            
            # Activité d'upload récente
            cursor.execute("""
                SELECT 
                    DATE(upload_time) as date,
                    COUNT(*) as uploads,
                    SUM(record_count) as records
                FROM data_uploads
                WHERE upload_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(upload_time)
                ORDER BY date
            """)
            
            upload_activity = cursor.fetchall()
            metrics['upload_activity'] = upload_activity
            
            # Taille moyenne des datasets
            cursor.execute("""
                SELECT 
                    AVG(record_count) as avg_records,
                    AVG(columns_count) as avg_columns,
                    AVG(file_size) as avg_size_kb
                FROM data_uploads
                WHERE record_count > 0
            """)
            
            avg_row = cursor.fetchone()
            if avg_row:
                metrics['avg_records'] = round(avg_row[0] or 0, 1)
                metrics['avg_columns'] = round(avg_row[1] or 0, 1)
                metrics['avg_size_kb'] = round((avg_row[2] or 0) / 1024, 1)
            
            return metrics
            
        except Exception as e:
            print(f"Erreur get_analyst_metrics: {e}")
            return {}
        finally:
            cursor.close()
            self.return_connection(conn)

    def log_ai_recommendation(self, user_id, recommendation_type, content):
        """Enregistre une recommandation IA générée"""
        if not self.connection_pool:
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO ai_recommendations 
                (user_id, recommendation_type, content, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (user_id, recommendation_type, content))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur log_ai_recommendation: {e}")
            return False
        finally:
            cursor.close()
            self.return_connection(conn)

    def insert_sample_marketing_data(self):
        """Insère des données marketing d'exemple (pour démonstration)"""
        if not self.connection_pool:
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        try:
            # Vérifier si des données existent déjà
            cursor.execute("SELECT COUNT(*) FROM marketing_data")
            count = cursor.fetchone()[0]
            
            if count == 0:
                campaigns = ['Summer Sale', 'Black Friday', 'Christmas Campaign', 'New Year Promotion']
                today = datetime.now().date()
                
                for i in range(30):
                    date = today - timedelta(days=i)
                    for campaign in campaigns:
                        impressions = np.random.randint(1000, 10000)
                        clicks = int(impressions * np.random.uniform(0.01, 0.05))
                        conversions = int(clicks * np.random.uniform(0.02, 0.10))
                        spend = round(np.random.uniform(100, 5000), 2)
                        revenue = round(spend * np.random.uniform(1.2, 3.0), 2)
                        
                        cursor.execute("""
                            INSERT INTO marketing_data 
                            (campaign_name, impressions, clicks, conversions, spend, revenue, date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (campaign, impressions, clicks, conversions, spend, revenue, date))
                
                conn.commit()
                return True
            return False
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur insert_sample_marketing_data: {e}")
            return False
        finally:
            cursor.close()
            self.return_connection(conn)

# ==========================
#        STYLE CSS 
# ==========================
def apply_custom_css():
    st.markdown("""
    <style>

    /* =========================
       GLOBAL – STYLE CORPORATE
    ========================= */
    .stApp {
        background: #F8FAFC;
        font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #0F172A;
        font-size: 18px;
    }

    /* =========================
       LOGIN PAGE
    ========================= */
    .login-container {
        max-width: 420px;
        margin: 90px auto;
        padding: 40px;
        background: #FFFFFF;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
    }

    .login-header {
        text-align: center;
        margin-bottom: 32px;
    }

    .login-title {
        font-size: 2.2em;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 6px;
    }

    .login-subtitle {
        color: #64748B;
        font-size: 0.95em;
    }

    /* =========================
       INPUTS
    ========================= */
    .stTextInput input {
        background: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 14px;
        font-size: 15px;
        color: #0F172A;
    }

    .stTextInput input:focus {
        border-color: #2563EB;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
        outline: none;
    }

    .stTextInput input::placeholder {
        color: #94A3B8;
    }

    /* =========================
       BUTTONS
    ========================= */
    .stButton button {
        width: 100%;
        background: #1E3A8A;
        color: #FFFFFF;
        border: none;
        padding: 14px;
        border-radius: 8px;
        font-size: 15px;
        font-weight: 600;
        margin-top: 10px;
        transition: background 0.2s ease;
    }

    .stButton button:hover {
        background: #2563EB;
    }

    /* =========================
       HEADERS / SECTIONS
    ========================= */
    .main-header {
        background: #FFFFFF;
        padding: 2rem;
        border-radius: 14px;
        margin-bottom: 2rem;
        border: 1px solid #E2E8F0;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }

    /* =========================
       KPI CARDS
    ========================= */
    .kpi-card {
        background: #FFFFFF;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
        transition: transform 0.2s ease;
    }

    .kpi-card:hover {
        transform: translateY(-4px);
    }

    .kpi-value {
        font-size: 2.2em;
        font-weight: 700;
        color: #1E3A8A;
    }

    .kpi-label {
        font-size: 0.85em;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    /* =========================
       SIDEBAR
    ========================= */
    section[data-testid="stSidebar"] > div {
        background: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }

    .sidebar-header {
        padding: 1.5rem;
        font-weight: 600;
        color: #1E3A8A;
        border-bottom: 1px solid #E2E8F0;
    }

    /* =========================
       TABLES
    ========================= */
    .dataframe {
        background: #FFFFFF !important;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
    }

    .dataframe thead {
        background: #F1F5F9 !important;
        color: #1E293B !important;
        font-weight: 600;
    }

    /* =========================
       ALERTS
    ========================= */
    .stAlert {
        border-radius: 8px;
        font-size: 14px;
    }

    /* =========================
       TABS
    ========================= */
    .stTabs [data-baseweb="tab-list"] {
        background: #F8FAFC;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
    }

    .stTabs [data-baseweb="tab"] {
        color: #64748B;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: #FFFFFF;
        color: #1E3A8A !important;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
    }

    /* =========================
       PROGRESS
    ========================= */
    .stProgress > div > div > div {
        background: #2563EB;
    }

    /* =========================
       SCROLLBAR
    ========================= */
    ::-webkit-scrollbar {
        width: 6px;
    }

    ::-webkit-scrollbar-thumb {
        background: #CBD5E1;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #94A3B8;
    }

    /* =========================
       MARKDOWN
    ========================= */
    .stMarkdown h1 {
        color: #1E3A8A;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 8px;
    }

    .stMarkdown h2 {
        color: #334155;
    }

    .stMarkdown h3 {
        color: #475569;
    }

    /* =========================
       PLOTLY
    ========================= */
    .js-plotly-plot {
        background: #FFFFFF !important;
        border-radius: 12px;
        padding: 12px;
        border: 1px solid #E2E8F0;
    }

    /* =========================
       FOCUS
    ========================= */
    *:focus {
        outline: 2px solid rgba(37, 99, 235, 0.3) !important;
        outline-offset: 2px;
    }

    </style>
    """, unsafe_allow_html=True)


# ==================================
#     PAGES D'AUTHENTIFICATION
# ==================================
def render_login_page(db):
    """Page de connexion avec design moderne"""
    apply_custom_css()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        # En-tête
        st.markdown('<div class="login-header">', unsafe_allow_html=True)
        st.markdown('<h1 class="login-title">🧮 AIM Analytics</h1>', unsafe_allow_html=True)
        st.markdown('<p class="login-subtitle">Plateforme d\'analyse intelligente et marketing</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Formulaire de connexion
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur", placeholder="Entrez votre nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password", placeholder="Entrez votre mot de passe")
            
            submitted = st.form_submit_button("Se connecter", use_container_width=True)
            
            if submitted:
                if not username or not password:
                    st.error("Veuillez remplir tous les champs")
                else:
                    user = db.authenticate_user(username, password)
                    if user:
                        # Assurer que toutes les clés nécessaires existent
                        user.setdefault('full_name', user.get('username', 'Utilisateur'))
                        user.setdefault('role', 'user')
                        user.setdefault('is_first_login', False)
                        
                        st.session_state.user = user
                        db.log_activity(user['id'], "login", f"Connexion de {username}")
                        
                        if user.get('is_first_login', False):
                            st.session_state.force_password_change = True
                            st.success("Connexion réussie! Vous devez changer votre mot de passe.")
                        else:
                            st.success("Connexion réussie!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Identifiants incorrects")
        
        # SUPPRIMÉ: Section identifiants de démonstration
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_password_change_page(user, db):
    """Page de changement de mot de passe obligatoire"""
    apply_custom_css()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        # Utiliser get() pour éviter KeyError
        user_full_name = user.get('full_name', user.get('username', 'Utilisateur'))
        
        st.markdown('<div class="login-header">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 4em; color: #667eea; margin-bottom: 20px;"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="color: #2c3e50;">Changement de mot de passe requis</h2>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: #666;">Bonjour <strong>{user_full_name}</strong>, pour des raisons de sécurité, vous devez modifier votre mot de passe.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Formulaire de changement
        with st.form("password_change_form"):
            new_password = st.text_input("Nouveau mot de passe", type="password", 
                                         help="Minimum 8 caractères")
            confirm_password = st.text_input("Confirmer le mot de passe", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Enregistrer", use_container_width=True)
            with col2:
                logout = st.form_submit_button("Déconnexion", use_container_width=True)
            
            if logout:
                st.session_state.clear()
                st.rerun()
            
            if submit:
                if not new_password or not confirm_password:
                    st.error("Veuillez remplir tous les champs")
                elif len(new_password) < 8:
                    st.error("Le mot de passe doit contenir au moins 8 caractères")
                elif new_password != confirm_password:
                    st.error("Les mots de passe ne correspondent pas")
                else:
                    if db.update_user_password(user['id'], new_password):
                        st.session_state.user['is_first_login'] = False
                        st.session_state.force_password_change = False
                        st.success("Mot de passe mis à jour avec succès!")
                        db.log_activity(user['id'], "password_change", "Mot de passe modifié")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Erreur lors de la mise à jour")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ==================================
#         DASHBOARD ADMIN 
# ==================================
def dashboard_admin_enhanced(user, db):
    """Dashboard administrateur avec design moderne et données dynamiques"""
    apply_custom_css()
    
    # Récupérer les valeurs
    user_full_name = user.get('full_name', user.get('username', 'Administrateur'))
    user_role = user.get('role', 'admin')
    
    # En-tête principal
    st.markdown(f"""
    <div class="main-header">
        <h1 style="margin-bottom: 0.5rem; font-size: 2.8em;">Dashboard Administrateur</h1>
        <p style="opacity: 0.95; font-size: 1.2em;">
            Administration complète du système AIM Analytics • Connecté en tant que {user_full_name}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        # En-tête sidebar
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 3])
        with col1:
            initials = user_full_name[0].upper() if user_full_name else 'A'
            st.markdown(f'<div style="width: 50px; height: 50px; background: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #667eea; font-size: 1.5em; font-weight: bold;">{initials}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"**{user_full_name}**")
            st.markdown(f"<span class='role-badge role-admin'>{user_role}</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Navigation
        admin_page = st.radio(
            "Navigation",
            ["Vue système", "Gestion utilisateurs", "Logs d'activité", "Profil", "Réinitialisation"],
            label_visibility="collapsed",
            key="admin_nav"
        )
        
        st.markdown("---")
        
        # Boutons d'action
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Rafraîchir", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("Déconnexion", use_container_width=True, type="primary"):
                db.log_activity(user['id'], "logout", "Déconnexion administrateur")
                st.session_state.clear()
                st.rerun()
    
    # Contenu principal
    try:
        if admin_page == "Vue système":
            render_system_overview_enhanced(user, db)
        elif admin_page == "Gestion utilisateurs":
            render_user_management_enhanced(user, db)
        elif admin_page == "Logs d'activité":
            render_activity_logs_enhanced(user, db)
        elif admin_page == "Profil":
            render_user_profile_enhanced(user, db)
        elif admin_page == "Réinitialisation":
            render_password_reset_page(user, db)
    except Exception as e:
        st.error(f"Une erreur est survenue : {str(e)}")
        st.info("Veuillez rafraîchir la page ou vous reconnecter.")

def render_system_overview_enhanced(user, db):
    """Vue d'ensemble système avec données DYNAMIQUES"""
    stats = db.get_system_stats()
    
    # KPIs principaux
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">UTILISATEURS</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("total_users", 0)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color: #27ae60; font-size: 0.9em;">{stats.get("active_users", 0)} actifs</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">CONNEXIONS AJD</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("today_logins", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #3498db; font-size: 0.9em;">Dernières 24h</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">UPLOADS</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("total_uploads", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #9b59b6; font-size: 0.9em;">Total fichiers</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">ACTIVITÉS AJD</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("today_activities", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #e74c3c; font-size: 0.9em;">En temps réel</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Deuxième ligne de KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">TAILLE DONNÉES</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("total_data_size_mb", 0)} MB</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #f39c12; font-size: 0.9em;">Stockage total</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">UTIL. ACTIFS AJD</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("active_users_today", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #2ecc71; font-size: 0.9em;">Uniques aujourd\'hui</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">1ÈRE CONNEXION</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{stats.get("first_login_users", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #e74c3c; font-size: 0.9em;">À réinitialiser</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        # Calculer le taux d'activité
        total_users = stats.get('total_users', 1)
        active_users = stats.get('active_users_today', 0)
        activity_rate = round((active_users / total_users) * 100, 1) if total_users > 0 else 0
        
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">TAUX ACTIVITÉ</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{activity_rate}%</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #3498db; font-size: 0.9em;">Utilisateurs actifs</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Graphiques avec données dynamiques
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Répartition des rôles")
        users_by_role = stats.get('users_by_role', {})
        if users_by_role:
            fig = px.pie(
                values=list(users_by_role.values()),
                names=[role.replace('_', ' ').title() for role in users_by_role.keys()],
                title="",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucun utilisateur enregistré")
    
    with col2:
        st.subheader("Activité récente (7 jours)")
        weekly_activity = stats.get('weekly_activity', [])
        
        if weekly_activity:
            dates = [row[0] for row in weekly_activity]
            counts = [row[1] for row in weekly_activity]
            
            activity_df = pd.DataFrame({
                'date': dates,
                'activités': counts
            })
            
            fig = px.bar(activity_df, x='date', y='activités',
                        title="",
                        color='activités',
                        color_continuous_scale='Viridis',
                        labels={'date': 'Date', 'activités': 'Nombre d\'activités'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Graphique par défaut si pas de données
            activity_data = pd.DataFrame({
                'date': pd.date_range(end=pd.Timestamp.now(), periods=7, freq='D'),
                'activités': np.random.randint(5, 20, 7)
            })
            
            fig = px.bar(activity_data, x='date', y='activités',
                        title="Aucune donnée récente - Affichage d'exemple",
                        color='activités',
                        color_continuous_scale='Viridis')
            st.plotly_chart(fig, use_container_width=True)

def render_user_management_enhanced(user, db):
    """Gestion des utilisateurs"""
    st.subheader("Gestion des utilisateurs")
    
    # Section d'ajout d'utilisateur
    with st.expander("Ajouter un nouvel utilisateur", expanded=False):
        with st.form(key="add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Nom d'utilisateur *", help="Nom unique pour la connexion")
                new_full_name = st.text_input("Nom complet *")
                new_email = st.text_input("Email *")
            
            with col2:
                new_role = st.selectbox(
                    "Rôle *",
                    ["data_analyst", "marketing"],
                    format_func=lambda x: {
                        "data_analyst": "Analyste de données",
                        "marketing": "Manager/Responsable Marketing",
                    }.get(x, x)
                )
                new_password = st.text_input("Mot de passe *", type="password")
                confirm_password = st.text_input("Confirmer le mot de passe *", type="password")
                new_department = st.text_input("Département")
            
            submitted = st.form_submit_button("Créer l'utilisateur", use_container_width=True)
            
            if submitted:
                if not all([new_username, new_full_name, new_email, new_password, confirm_password]):
                    st.error("Veuillez remplir tous les champs obligatoires (*)")
                elif new_password != confirm_password:
                    st.error("Les mots de passe ne correspondent pas")
                elif len(new_password) < 6:
                    st.error("Le mot de passe doit contenir au moins 6 caractères")
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
                        db.log_activity(user['id'], "user_creation", f"Création utilisateur {new_username}")
                        st.success(f"{message}")
                        st.rerun()
                    else:
                        st.error(f"{message}")
    
    # Liste des utilisateurs
    st.subheader("Liste des utilisateurs")
    users = db.get_all_users()
    
    if users:
        users_df = pd.DataFrame(users)
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        with col1:
            role_filter = st.multiselect(
                "Filtrer par rôle",
                users_df['role'].unique(),
                key="role_filter"
            )
        with col2:
            status_filter = st.multiselect(
                "Filtrer par statut",
                ['Actif', 'Inactif'],
                key="status_filter"
            )
        with col3:
            first_login_filter = st.multiselect(
                "Première connexion",
                ['Oui', 'Non'],
                key="first_login_filter"
            )
        
        # Appliquer les filtres
        filtered_df = users_df.copy()
        if role_filter:
            filtered_df = filtered_df[filtered_df['role'].isin(role_filter)]
        if status_filter:
            if 'Actif' in status_filter and 'Inactif' not in status_filter:
                filtered_df = filtered_df[filtered_df['is_active'] == True]
            elif 'Inactif' in status_filter and 'Actif' not in status_filter:
                filtered_df = filtered_df[filtered_df['is_active'] == False]
        if first_login_filter:
            if 'Oui' in first_login_filter and 'Non' not in first_login_filter:
                filtered_df = filtered_df[filtered_df['is_first_login'] == True]
            elif 'Non' in first_login_filter and 'Oui' not in first_login_filter:
                filtered_df = filtered_df[filtered_df['is_first_login'] == False]
        
        # Afficher le tableau avec mise en forme
        st.info(f"**{len(filtered_df)}** utilisateur(s) trouvé(s)")
        
        # Créer une copie pour l'affichage avec des colonnes formatées
        display_df = filtered_df.copy()
        
        # Formater les colonnes
        if 'role' in display_df.columns:
            display_df['role'] = display_df['role'].apply(
                lambda x: {
                    'admin': 'Admin',
                    'data_analyst': 'Analyste',
                    'marketing': 'Marketing',
                    'support': 'Support'
                }.get(x, x)
            )
        
        if 'is_active' in display_df.columns:
            display_df['is_active'] = display_df['is_active'].apply(lambda x: 'Actif' if x else 'Inactif')
        
        if 'is_first_login' in display_df.columns:
            display_df['is_first_login'] = display_df['is_first_login'].apply(lambda x: 'Oui' if x else 'Non')
        
        if 'last_login' in display_df.columns:
            display_df['last_login'] = display_df['last_login'].apply(
                lambda x: x.strftime('%d/%m/%Y %H:%M') if pd.notna(x) and x else 'Jamais'
            )
        
        st.markdown('<div class="data-table">', unsafe_allow_html=True)
        st.dataframe(display_df, use_container_width=True, height=400)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Actions rapides
        st.subheader("Actions rapides")
        
        # Utiliser des onglets pour organiser les actions
        tab1, tab2 = st.tabs(["Modifier le statut", "Supprimer un utilisateur"])
        
        with tab1:
            if len(filtered_df) > 0:
                selected_username_status = st.selectbox(
                    "Sélectionner un utilisateur pour modifier son statut",
                    filtered_df['username'].tolist(),
                    key="user_select_status"
                )
                
                if selected_username_status:
                    user_data_status = filtered_df[filtered_df['username'] == selected_username_status].iloc[0]
                    
                    new_status = st.selectbox(
                        "Changer le statut",
                        ["Actif", "Inactif"],
                        index=0 if user_data_status.get('is_active', True) else 1,
                        key="status_change_select"
                    )
                    
                    if st.button("Mettre à jour le statut", key="update_status_btn"):
                        is_active = new_status == "Actif"
                        success = db.update_user_status(user_data_status['id'], is_active)
                        if success:
                            db.log_activity(user['id'], "user_status_change", 
                                           f"Statut {selected_username_status} changé à {new_status}")
                            st.success(f"Statut de {selected_username_status} mis à jour")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Erreur lors de la mise à jour")
        
        with tab2:
            st.markdown("### Supprimer un utilisateur")
            st.warning("**ATTENTION :** Cette action est irréversible. Toutes les données associées à l'utilisateur seront supprimées.")
            
            if len(filtered_df) > 0:
                # Liste des utilisateurs (exclure l'admin actuel)
                available_users = filtered_df[filtered_df['id'] != user['id']].copy()
                
                if len(available_users) > 0:
                    selected_username_delete = st.selectbox(
                        "Sélectionner un utilisateur à supprimer",
                        available_users['username'].tolist(),
                        key="user_select_delete"
                    )
                    
                    if selected_username_delete:
                        user_data_delete = available_users[available_users['username'] == selected_username_delete].iloc[0]
                        
                        # Convertir l'ID en int natif
                        user_id_to_delete = int(user_data_delete['id'])
                        current_admin_id = int(user['id'])
                        
                        # Afficher les informations de l'utilisateur
                        st.markdown("**Informations de l'utilisateur :**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Nom :** {user_data_delete.get('full_name', 'N/A')}")
                            st.info(f"**Rôle :** {user_data_delete.get('role', 'N/A').replace('_', ' ').title()}")
                        with col2:
                            st.info(f"**Email :** {user_data_delete.get('email', 'N/A')}")
                            st.info(f"**Département :** {user_data_delete.get('department', 'N/A')}")
                        
                        # Vérifier si l'utilisateur peut être supprimé
                        can_delete, delete_message = db.can_delete_user(user_id_to_delete, current_admin_id)
                        
                        if not can_delete:
                            st.error(f"**Impossible de supprimer :** {delete_message}")
                        else:
                            # Confirmation de suppression
                            st.markdown("---")
                            st.markdown("**Confirmation de suppression**")
                            
                            # Double vérification
                            confirm_text = st.text_input(
                                f"Tapez 'SUPPRIMER {selected_username_delete}' pour confirmer",
                                key="confirm_delete_text",
                                placeholder=f"SUPPRIMER {selected_username_delete}"
                            )
                            
                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                delete_disabled = confirm_text != f"SUPPRIMER {selected_username_delete}"
                                if st.button("Supprimer définitivement", 
                                            type="primary",
                                            disabled=delete_disabled,
                                            use_container_width=True):
                                    
                                    # Procéder à la suppression
                                    success, message = db.delete_user(user_id_to_delete)
                                    
                                    if success:
                                        db.log_activity(user['id'], "user_deletion", 
                                                       f"Suppression utilisateur {selected_username_delete}")
                                        st.success(f"Utilisateur {selected_username_delete} supprimé avec succès")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"Erreur : {message}")
                            
                            with col2:
                                if st.button("Vérifier à nouveau", use_container_width=True):
                                    st.rerun()
                            
                            with col3:
                                if st.button("Annuler", use_container_width=True):
                                    st.rerun()
                else:
                    st.info("Aucun autre utilisateur disponible pour la suppression")
            else:
                st.info("Aucun utilisateur à supprimer")

def render_password_reset_page(user, db):
    """Page de réinitialisation des mots de passe"""
    st.subheader("Réinitialisation des mots de passe")
    
    st.markdown("""
    <div class="alert-warning">
    <strong>Attention :</strong> Cette fonctionnalité permet de réinitialiser le mot de passe d'un utilisateur spécifique.
    L'utilisateur devra changer son mot de passe à sa prochaine connexion.
    </div>
    """, unsafe_allow_html=True)
    
    # Récupérer tous les utilisateurs
    users = db.get_all_users()
    
    if users:
        users_df = pd.DataFrame(users)
        
        # Sélection de l'utilisateur
        selected_username = st.selectbox(
            "Sélectionner l'utilisateur à réinitialiser",
            users_df['username'].tolist(),
            key="reset_user_select"
        )
        
        if selected_username:
            user_data = users_df[users_df['username'] == selected_username].iloc[0]
            
            # Afficher les informations de l'utilisateur
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Nom complet :** {user_data.get('full_name', 'N/A')}")
                st.info(f"**Rôle :** {user_data.get('role', 'N/A').replace('_', ' ').title()}")
            with col2:
                status = "Actif" if user_data.get('is_active', False) else "Inactif"
                st.info(f"**Statut :** {status}")
                last_login = user_data.get('last_login', '')
                if last_login and pd.notna(last_login):
                    if isinstance(last_login, str):
                        last_login_str = last_login
                    else:
                        last_login_str = last_login.strftime('%d/%m/%Y %H:%M')
                else:
                    last_login_str = "Jamais"
                st.info(f"**Dernière connexion :** {last_login_str}")
            
            # Options de réinitialisation
            st.subheader("Options de réinitialisation")
            
            option = st.radio(
                "Choisir une option :",
                ["Réinitialiser avec mot de passe par défaut (reset123)",
                 "Définir un nouveau mot de passe personnalisé"],
                key="reset_option"
            )
            
            custom_password = None
            if option == "Définir un nouveau mot de passe personnalisé":
                new_password = st.text_input("Nouveau mot de passe", type="password", 
                                           help="Minimum 8 caractères")
                confirm_password = st.text_input("Confirmer le mot de passe", type="password")
                if new_password and confirm_password and new_password == confirm_password and len(new_password) >= 8:
                    custom_password = new_password
                elif new_password or confirm_password:
                    st.warning("Les mots de passe doivent correspondre et contenir au moins 8 caractères")
            
            # Bouton de confirmation
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                warning_text = ""
                if user_data.get('id') == user.get('id'):
                    warning_text = "**Vous êtes sur le point de réinitialiser VOTRE propre mot de passe !**"
                elif user_data.get('username') == 'admin':
                    warning_text = "**Attention : Réinitialisation du compte administrateur principal !**"
                
                if warning_text:
                    st.markdown(f'<div class="alert-danger">{warning_text}</div>', unsafe_allow_html=True)
            
            with col2:
                if st.button("Réinitialiser le mot de passe", type="primary", use_container_width=True):
                    # Déterminer le mot de passe à utiliser
                    password_to_use = custom_password if custom_password else "reset123"
                    
                    # Réinitialiser le mot de passe
                    if db.reset_user_password(user_data['id'], password_to_use):
                        db.log_activity(user['id'], "password_reset", 
                                       f"Réinitialisation mot de passe de {selected_username}")
                        
                        # Préparer le message
                        if user_data.get('id') == user.get('id'):
                            message = f"""
                            Votre mot de passe a été réinitialisé !
                            
                            **Informations importantes :**
                            - Vous serez déconnecté automatiquement
                            - À votre prochaine connexion, utilisez : `{password_to_use}`
                            - Vous devrez immédiatement changer votre mot de passe
                            """
                            st.warning(message)
                            time.sleep(3)
                            st.session_state.clear()
                            st.rerun()
                        else:
                            message = f"""
                            Mot de passe réinitialisé pour **{selected_username}** !
                            
                            **Informations :**
                            - Nouveau mot de passe : `{password_to_use}`
                            - L'utilisateur devra le changer à sa prochaine connexion
                            """
                            st.success(message)
                            st.rerun()
                    else:
                        st.error("Erreur lors de la réinitialisation")
    else:
        st.info("Aucun utilisateur disponible")

def render_activity_logs_enhanced(user, db):
    """Logs d'activité"""
    st.subheader("Logs d'activité")
    
    logs = db.get_activity_logs(limit=200)
    
    if logs:
        logs_df = pd.DataFrame(logs)
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            activity_types = logs_df['activity_type'].unique()
            if len(activity_types) > 0:
                type_filter = st.multiselect(
                    "Type d'activité :",
                    activity_types,
                    default=activity_types[:3] if len(activity_types) > 3 else activity_types,
                    key="activity_type_filter"
                )
        
        with col2:
            if 'username' in logs_df.columns:
                user_filter = st.multiselect(
                    "Filtrer par utilisateur :",
                    logs_df['username'].unique(),
                    key="activity_user_filter"
                )
        
        with col3:
            if 'created_at' in logs_df.columns:
                logs_df['date'] = pd.to_datetime(logs_df['created_at']).dt.date
                unique_dates = sorted(logs_df['date'].unique(), reverse=True)[:10]
                date_filter = st.multiselect(
                    "Filtrer par date :",
                    unique_dates,
                    key="activity_date_filter"
                )
        
        # Appliquer les filtres
        filtered_logs = logs_df.copy()
        if 'type_filter' in locals() and type_filter:
            filtered_logs = filtered_logs[filtered_logs['activity_type'].isin(type_filter)]
        if 'user_filter' in locals() and user_filter:
            filtered_logs = filtered_logs[filtered_logs['username'].isin(user_filter)]
        if 'date_filter' in locals() and date_filter:
            filtered_logs = filtered_logs[filtered_logs['date'].isin(date_filter)]
        
        st.info(f"**{len(filtered_logs)}** logs correspondant aux filtres")
        
        # Affichage des logs avec mise en forme
        display_logs = filtered_logs.copy()
        
        if 'created_at' in display_logs.columns:
            display_logs['created_at'] = pd.to_datetime(display_logs['created_at']).dt.strftime('%d/%m/%Y %H:%M:%S')
        
        # Formater les types d'activité
        if 'activity_type' in display_logs.columns:
            activity_icons = {
                'login': '',
                'logout': '',
                'password_change': '',
                'password_reset': '',
                'user_creation': '',
                'user_status_change': '',
                'profile_update': '',
                'upload': '',
                'download': ''
            }
            display_logs['activity_type'] = display_logs['activity_type'].apply(
                lambda x: f"{activity_icons.get(x, '')} {x}"
            )
        
        st.markdown('<div class="data-table">', unsafe_allow_html=True)
        st.dataframe(display_logs, use_container_width=True, height=500)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Statistiques
        st.subheader("Statistiques des activités")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'activity_type' in filtered_logs.columns:
                # Nettoyer les types pour enlever les icônes temporaires
                clean_types = filtered_logs['activity_type'].apply(
                    lambda x: x.replace(' ', '').replace(' ', '').replace(' ', '').replace(' ', '')
                        .replace(' ', '').replace(' ', '').replace(' ', '').replace(' ', '').replace(' ', '')
                )
                activity_counts = clean_types.value_counts().head(10)
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

def render_user_profile_enhanced(user, db):
    """Profil utilisateur"""
    st.subheader("Profil Utilisateur")
    
    # Récupérer les valeurs avec get() et valeurs par défaut
    user_full_name = user.get('full_name', user.get('username', 'Utilisateur'))
    user_email = user.get('email', '')
    user_department = user.get('department', '')
    user_role = user.get('role', 'user')
    user_active = user.get('is_active', True)
    user_last_login = user.get('last_login', '')
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Avatar et informations
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        initials = user_full_name[0].upper() if user_full_name else 'U'
        st.markdown(f'''
        <div style="text-align: center;">
            <div style="width: 100px; height: 100px; background: linear-gradient(135deg, #667eea, #764ba2); 
                      border-radius: 50%; display: flex; align-items: center; justify-content: center; 
                      color: white; font-size: 2.5em; font-weight: bold; margin: 0 auto 1.5rem auto;">
                {initials}
            </div>
            <h3>{user_full_name}</h3>
            <p>@{user.get('username', '')}</p>
        </div>
        ''', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Badge de rôle
        role_badge_class = f"role-{user_role}"
        st.markdown(f"**Rôle :** <span class='role-badge {role_badge_class}'>{user_role.replace('_', ' ').title()}</span>", unsafe_allow_html=True)
        
        st.markdown(f"**Email :** {user_email or 'Non défini'}")
        st.markdown(f"**Département :** {user_department or 'Non défini'}")
        st.markdown(f"**Statut :** {'Actif' if user_active else 'Inactif'}")
        
        if user_last_login:
            if isinstance(user_last_login, str):
                st.markdown(f"**Dernière connexion :** {user_last_login}")
            else:
                try:
                    st.markdown(f"**Dernière connexion :** {user_last_login.strftime('%d/%m/%Y %H:%M')}")
                except:
                    st.markdown(f"**Dernière connexion :** {str(user_last_login)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        # Formulaire de modification
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown("### Modifier le profil")
        
        with st.form(key="profile_form_enhanced"):
            full_name = st.text_input("Nom complet", value=user_full_name, key="profile_full_name")
            email = st.text_input("Email", value=user_email, key="profile_email")
            department = st.text_input("Département", value=user_department, key="profile_department")
            
            st.markdown("---")
            st.markdown("### Changer le mot de passe")
            current_password = st.text_input("Mot de passe actuel", type="password", key="profile_current_pw")
            new_password = st.text_input("Nouveau mot de passe", type="password", key="profile_new_pw")
            confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password", key="profile_confirm_pw")
            
            submitted = st.form_submit_button("Enregistrer les modifications", use_container_width=True)
            
            if submitted:
                updates = {}
                validation_errors = []
                
                # Validation des champs
                if full_name != user_full_name:
                    updates['full_name'] = full_name
                
                if email != user_email:
                    if "@" not in email:
                        validation_errors.append("Email invalide")
                    else:
                        updates['email'] = email
                
                if department != user_department:
                    updates['department'] = department
                
                if new_password:
                    if len(new_password) < 8:
                        validation_errors.append("Le mot de passe doit contenir au moins 8 caractères")
                    elif new_password != confirm_password:
                        validation_errors.append("Les nouveaux mots de passe ne correspondent pas")
                    elif not current_password:
                        validation_errors.append("Veuillez entrer votre mot de passe actuel")
                    else:
                        # Vérifier le mot de passe actuel
                        if db.authenticate_user(user.get('username', ''), current_password):
                            updates['password'] = new_password
                        else:
                            validation_errors.append("Mot de passe actuel incorrect")
                
                if validation_errors:
                    for error in validation_errors:
                        st.error(f"{error}")
                elif updates:
                    success = db.update_user_profile(user['id'], **updates)
                    
                    if success:
                        db.log_activity(user['id'], "profile_update", "Mise à jour du profil")
                        st.success("Profil mis à jour avec succès!")
                        
                        # Mettre à jour la session
                        for key, value in updates.items():
                            if key != 'password':
                                st.session_state.user[key] = value
                        
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Erreur lors de la mise à jour")
                else:
                    st.info("Aucune modification détectée")
        
        st.markdown('</div>', unsafe_allow_html=True)

# =======================================
#       DASHBOARD DATA ANALYST
# =======================================
def dashboard_data_analyst(user, db):
    """Dashboard principal pour les analystes de données"""
    apply_custom_css()
    
    user_full_name = user.get('full_name', user.get('username', 'Analyste de données'))
    user_role = user.get('role', 'data_analyst')
    
    # En-tête principal
    st.markdown(f"""
    <div class="main-header">
        <h1 style="margin-bottom: 0.5rem; font-size: 2.4em;">Dashboard Analyste de Données</h1>
        <p style="opacity: 0.95; font-size: 1.1em;">
            Bienvenue {user_full_name} • Plateforme d'analyse avancée des données
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        # En-tête sidebar
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 3])
        with col1:
            initials = user_full_name[0].upper() if user_full_name else 'A'
            st.markdown(f'<div style="width: 50px; height: 50px; background: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #667eea; font-size: 1.5em; font-weight: bold;">{initials}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"**{user_full_name}**")
            st.markdown(f"<span class='role-badge role-data_analyst'>Analyste</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Import des données
        st.markdown("### Import des données")
        
        uploaded_file = st.file_uploader(
            "Importer un fichier de données",
            type=['csv', 'xlsx', 'xls', 'json'],
            key="data_analyst_upload"
        )
        
        if uploaded_file is not None:
            try:
                # Détecter le type de fichier et le lire
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(uploaded_file)
                elif uploaded_file.name.endswith('.json'):
                    df = pd.read_json(uploaded_file)
                else:
                    st.error("Format de fichier non supporté")
                    df = None
                
                if df is not None:
                    # Stocker les données dans la session
                    st.session_state['uploaded_data'] = df
                    st.session_state['uploaded_filename'] = uploaded_file.name
                    st.session_state['uploaded_file_size'] = len(uploaded_file.getvalue())
                    
                    st.success(f"{uploaded_file.name} importé avec succès!")
                    st.info(f"{df.shape[0]} lignes × {df.shape[1]} colonnes")
                    
                    # Log l'activité
                    db.log_activity(user['id'], "data_upload", 
                                   f"Import fichier: {uploaded_file.name} ({df.shape[0]}x{df.shape[1]})")
            except Exception as e:
                st.error(f"Erreur lors de l'import: {str(e)}")
        
        # Navigation - AJOUT DE LA PAGE "PROFIL"
        st.markdown("---")
        pages = ["Vue d'ensemble", "Analyse EDA", "Modèles ML", "Analyse Sentiments et détection faux avis", "Profil"]
        selected_page = st.radio(
            "Navigation",
            pages,
            label_visibility="collapsed",
            key="data_analyst_nav"
        )
        
        st.markdown("---")
        
        # Boutons d'action
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Rafraîchir", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("Déconnexion", use_container_width=True, type="primary"):
                db.log_activity(user['id'], "logout", "Déconnexion analyste")
                st.session_state.clear()
                st.rerun()
    
    # Contenu principal basé sur la page sélectionnée
    if selected_page == "Vue d'ensemble":
        render_analyst_overview(user, db)
    elif selected_page == "Analyse EDA":
        render_eda_analysis(user, db)
    elif selected_page == "Modèles ML":
        render_ml_models(user, db)
    elif selected_page == "Analyse Sentiments et détection faux avis":
        render_sentiment_analysis(user, db)
    elif selected_page == "Profil":
        render_user_profile_enhanced(user, db) 

def render_ml_models(user, db):
    """Page dédiée à la détection de faux avis (Spam/Ham)"""
    st.subheader("Détection Intelligente de Faux Avis")
    
    if 'uploaded_data' not in st.session_state:
        st.warning("Importez d'abord vos données pour analyser les avis")
        return
    
    df = st.session_state['uploaded_data']
    
    st.markdown("""
    ### Système de Détection de Faux Avis (Spam/Ham)
    
    Cette section utilise des algorithmes de machine learning pour détecter automatiquement 
    les faux avis (spam) et les authentiques (ham). L'analyse inclut :
    - Détection automatique des avis suspects
    - Identification des auteurs récurrents
    - Visualisations détaillées
    - Export des résultats
    """)
    
    # ===========================================
    # SECTION 1: IDENTIFICATION DES COLONNES
    # ===========================================
    st.markdown("---")
    st.markdown("### 1. Identification des colonnes")
    
    # Identifier les colonnes automatiquement
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    possible_author_cols = []
    possible_rating_cols = []
    possible_date_cols = []
    
    # Détection intelligente des colonnes
    for col in df.columns:
        col_lower = col.lower()
        
        # Colonnes de texte (avis)
        if df[col].dtype == 'object' and df[col].str.len().mean() > 20:
            text_cols.append(col)
        
        # Colonnes d'auteur
        if any(keyword in col_lower for keyword in ['author', 'user', 'name', 'client', 'utilisateur']):
            possible_author_cols.append(col)
        
        # Colonnes de note
        if any(keyword in col_lower for keyword in ['rating', 'note', 'score', 'star', 'review']):
            possible_rating_cols.append(col)
        
        # Colonnes de date
        if any(keyword in col_lower for keyword in ['date', 'time', 'created', 'posted']):
            possible_date_cols.append(col)
    
    # Sélection des colonnes
    col1, col2, col3 = st.columns(3)
    
    with col1:
        review_col = st.selectbox(
            "Colonne des avis/textes :",
            text_cols,
            help="Colonne contenant le texte des avis",
            key="review_col"
        )
    
    with col2:
        if possible_author_cols:
            author_col = st.selectbox(
                "Colonne des auteurs :",
                ['Aucune'] + possible_author_cols,
                help="Colonne contenant les noms d'auteurs",
                key="author_col"
            )
        else:
            author_col = 'Aucune'
            st.info("Aucune colonne auteur détectée")
    
    with col3:
        if possible_rating_cols:
            rating_col = st.selectbox(
                "Colonne des notes :",
                ['Aucune'] + possible_rating_cols,
                help="Colonne contenant les notes/ratings",
                key="rating_col"
            )
        else:
            rating_col = 'Aucune'
            st.info("Aucune colonne note détectée")
    
    # Informations sur les données
    total_reviews = len(df[review_col].dropna())
    st.info(f"""
    **Données disponibles :**
    - Total avis analysables : **{total_reviews}**
    - Colonne avis : **{review_col}**
    - Colonne auteur : **{author_col if author_col != 'Aucune' else 'Non détectée'}**
    - Colonne note : **{rating_col if rating_col != 'Aucune' else 'Non détectée'}**
    """)
    
    # ===========================================
    # SECTION 2: CONFIGURATION DE LA DÉTECTION
    # ===========================================
    st.markdown("---")
    st.markdown("### 2. Configuration de la détection")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Règles de détection")
        
        min_text_length = st.slider(
            "Longueur texte minimale :",
            min_value=5,
            max_value=100,
            value=10,
            help="Textes plus courts que cette valeur seront suspects"
        )
        
        max_repetition = st.slider(
            "Seuil de répétition (%) :",
            min_value=10,
            max_value=50,
            value=30,
            help="Pourcentage maximum de répétition d'un mot dans le texte"
        )
        
        extreme_rating = st.checkbox(
            "Détecter notes extrêmes",
            value=True,
            help="Marquer comme suspect les notes 1 ou 5 avec texte court"
        )
    
    with col2:
        st.markdown("#### Algorithmes ML")
        
        use_ml = st.checkbox(
            "Utiliser machine learning avancé",
            value=True,
            help="Utiliser des algorithmes ML pour améliorer la détection"
        )
        
        if use_ml:
            ml_method = st.selectbox(
                "Algorithme de détection :",
                ["Naive Bayes", "Régression Logistique", "Forêt Aléatoire"],
                help="Algorithme ML pour classification spam/ham"
            )
        
        confidence_threshold = st.slider(
            "Seuil de confiance :",
            min_value=50,
            max_value=95,
            value=75,
            help="Seuil minimum de confiance pour marquer comme spam"
        )
    
    # ===========================================
    # SECTION 3: ANALYSE ET DÉTECTION
    # ===========================================
    st.markdown("---")
    
    if st.button("Lancer la détection de faux avis", type="primary", use_container_width=True):
        with st.spinner("Analyse des avis en cours..."):
            # Préparer les données
            analysis_data = df.copy()
            
            # Appliquer les règles de base
            analysis_data['text_length'] = analysis_data[review_col].astype(str).apply(len)
            analysis_data['suspicious_short'] = analysis_data['text_length'] < min_text_length
            
            # Détection de répétition
            def check_repetition(text):
                if isinstance(text, str) and len(text) > 0:
                    words = text.split()
                    if len(words) > 0:
                        word_counts = Counter(words)
                        most_common_count = word_counts.most_common(1)[0][1]
                        return (most_common_count / len(words)) * 100 > max_repetition
                return False
            
            analysis_data['suspicious_repetition'] = analysis_data[review_col].apply(check_repetition)
            
            # Détection notes extrêmes
            if rating_col != 'Aucune' and extreme_rating:
                analysis_data['suspicious_rating'] = (
                    (analysis_data[rating_col].isin([1, 5])) & 
                    (analysis_data['text_length'] < 50)
                )
            else:
                analysis_data['suspicious_rating'] = False
            
            # Calculer le score de suspicion (règles basiques)
            rule_columns = ['suspicious_short', 'suspicious_repetition', 'suspicious_rating']
            analysis_data['suspicion_score_rules'] = analysis_data[rule_columns].sum(axis=1)
            analysis_data['is_spam_rules'] = analysis_data['suspicion_score_rules'] >= 2
            
            # ===========================================
            # SECTION 4: ANALYSE AVANCÉE AVEC ML
            # ===========================================
            if use_ml and total_reviews >= 20:
                try:
                    from sklearn.feature_extraction.text import TfidfVectorizer
                    from sklearn.model_selection import train_test_split
                    from sklearn.naive_bayes import MultinomialNB
                    from sklearn.linear_model import LogisticRegression
                    from sklearn.ensemble import RandomForestClassifier
                    from sklearn.metrics import classification_report
                    
                    # Préparer les données pour ML
                    texts = analysis_data[review_col].fillna('').astype(str).tolist()
                    
                    # Créer des labels basés sur les règles
                    y = analysis_data['is_spam_rules'].astype(int).values
                    
                    # Vectorisation TF-IDF
                    vectorizer = TfidfVectorizer(
                        max_features=1000,
                        stop_words='english',
                        ngram_range=(1, 2)
                    )
                    X = vectorizer.fit_transform(texts)
                    
                    # Sélectionner le modèle
                    if ml_method == "Naive Bayes":
                        model = MultinomialNB()
                    elif ml_method == "Régression Logistique":
                        model = LogisticRegression(max_iter=1000, random_state=42)
                    else:  # Forêt Aléatoire
                        model = RandomForestClassifier(n_estimators=100, random_state=42)
                    
                    # Entraîner le modèle
                    model.fit(X, y)
                    
                    # Prédictions
                    y_pred = model.predict(X)
                    y_prob = model.predict_proba(X)
                    
                    # Ajouter les résultats ML
                    analysis_data['is_spam_ml'] = y_pred == 1
                    analysis_data['spam_confidence'] = y_prob[:, 1] * 100
                    analysis_data['is_spam_final'] = (
                        (analysis_data['is_spam_ml']) & 
                        (analysis_data['spam_confidence'] >= confidence_threshold)
                    ) | analysis_data['is_spam_rules']
                    
                    ml_used = True
                    
                except Exception as e:
                    st.warning(f"ML non disponible : {str(e)}")
                    analysis_data['is_spam_final'] = analysis_data['is_spam_rules']
                    analysis_data['spam_confidence'] = analysis_data['suspicion_score_rules'] * 25
                    ml_used = False
            else:
                analysis_data['is_spam_final'] = analysis_data['is_spam_rules']
                analysis_data['spam_confidence'] = analysis_data['suspicion_score_rules'] * 25
                ml_used = False
            
            # ===========================================
            # SECTION 5: STATISTIQUES ET VISUALISATIONS
            # ===========================================
            st.markdown("### 3. Résultats de la détection")
            
            # Calculer les statistiques
            total_spam = analysis_data['is_spam_final'].sum()
            spam_percentage = (total_spam / len(analysis_data)) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Avis analysés", len(analysis_data))
            
            with col2:
                st.metric("Faux avis détectés", total_spam)
            
            with col3:
                st.metric("Taux de faux avis", f"{spam_percentage:.1f}%")
            
            with col4:
                avg_confidence = analysis_data.loc[analysis_data['is_spam_final'], 'spam_confidence'].mean()
                st.metric("Confiance moyenne", f"{avg_confidence:.1f}%" if not pd.isna(avg_confidence) else "0%")
            
            # Visualisation 1: Répartition Spam/Ham
            st.markdown("---")
            st.markdown("#### Répartition Spam vs Ham")
            
            spam_counts = pd.Series(['Ham (Authentique)', 'Spam (Faux)']).value_counts()
            spam_counts['Ham (Authentique)'] = len(analysis_data) - total_spam
            spam_counts['Spam (Faux)'] = total_spam
            
            fig_dist = px.pie(
                values=spam_counts.values,
                names=spam_counts.index,
                title="Distribution des avis",
                hole=0.4,
                color_discrete_map={
                    'Ham (Authentique)': '#36B37E',
                    'Spam (Faux)': '#FF5630'
                }
            )
            fig_dist.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_dist, use_container_width=True)
            
            # Visualisation 2: Causes des faux avis
            st.markdown("---")
            st.markdown("#### Causes principales des faux avis")
            
            spam_data = analysis_data[analysis_data['is_spam_final']].copy()
            
            if len(spam_data) > 0:
                causes = []
                
                for idx, row in spam_data.iterrows():
                    cause_parts = []
                    
                    if row['suspicious_short']:
                        cause_parts.append("Texte court")
                    if row['suspicious_repetition']:
                        cause_parts.append("Répétition")
                    if row.get('suspicious_rating', False):
                        cause_parts.append("Note extrême")
                    
                    causes.append(', '.join(cause_parts) if cause_parts else "Autre")
                
                cause_counts = Counter(causes)
                
                fig_causes = px.bar(
                    x=list(cause_counts.keys()),
                    y=list(cause_counts.values()),
                    title="Répartition des causes de détection",
                    labels={'x': 'Cause', 'y': 'Nombre d\'avis'},
                    color=list(cause_counts.values()),
                    color_continuous_scale='Reds'
                )
                fig_causes.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_causes, use_container_width=True)
            
            # Visualisation 3: Longueur des textes
            st.markdown("---")
            st.markdown("#### Analyse de la longueur des textes")
            
            fig_length = px.histogram(
                analysis_data,
                x='text_length',
                color='is_spam_final',
                nbins=30,
                title="Distribution de la longueur des textes",
                labels={'text_length': 'Longueur du texte (caractères)', 'is_spam_final': 'Est spam'},
                color_discrete_map={False: '#36B37E', True: '#FF5630'},
                opacity=0.7
            )
            fig_length.add_vline(x=min_text_length, line_dash="dash", line_color="red", 
                               annotation_text=f"Seuil: {min_text_length} caractères")
            st.plotly_chart(fig_length, use_container_width=True)
            
            # ===========================================
            # SECTION 6: IDENTIFICATION DES AUTEURS
            # ===========================================
            st.markdown("---")
            st.markdown("### 4. Identification des auteurs")
            
            if author_col != 'Aucune' and author_col in analysis_data.columns:
                # Analyse par auteur
                author_analysis = analysis_data.groupby(author_col).agg({
                    review_col: 'count',
                    'is_spam_final': 'sum',
                    'spam_confidence': 'mean',
                    'text_length': 'mean'
                }).rename(columns={
                    review_col: 'total_reviews',
                    'is_spam_final': 'spam_count',
                    'spam_confidence': 'avg_confidence',
                    'text_length': 'avg_text_length'
                }).round(2)
                
                author_analysis['spam_percentage'] = (author_analysis['spam_count'] / author_analysis['total_reviews']) * 100
                author_analysis = author_analysis.sort_values('spam_count', ascending=False)
                
                # Afficher les auteurs suspects
                suspicious_authors = author_analysis[author_analysis['spam_count'] > 0]
                
                st.markdown(f"**{len(suspicious_authors)} auteurs suspects identifiés**")
                
                if len(suspicious_authors) > 0:
                    # Top 10 auteurs les plus suspects
                    top_suspicious = suspicious_authors.head(10)
                    
                    fig_authors = px.bar(
                        top_suspicious.reset_index(),
                        x=author_col,
                        y='spam_count',
                        color='spam_percentage',
                        title="Top 10 des auteurs les plus suspects",
                        labels={'spam_count': 'Nombre de faux avis', 'spam_percentage': '% de spam'},
                        color_continuous_scale='Reds',
                        hover_data=['total_reviews', 'avg_confidence', 'avg_text_length']
                    )
                    fig_authors.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_authors, use_container_width=True)
                    
                    # Tableau détaillé des auteurs
                    st.markdown("#### Détail des auteurs suspects")
                    
                    display_cols = [
                        author_col, 
                        'total_reviews', 
                        'spam_count', 
                        'spam_percentage', 
                        'avg_confidence',
                        'avg_text_length'
                    ]
                    
                    st.dataframe(
                        suspicious_authors[display_cols].reset_index(drop=True),
                        use_container_width=True,
                        height=400
                    )
                    
                    # Analyse des patterns d'auteurs
                    st.markdown("#### Patterns des auteurs suspects")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        avg_reviews_suspicious = suspicious_authors['total_reviews'].mean()
                        st.metric("Moyenne d'avis par auteur suspect", f"{avg_reviews_suspicious:.1f}")
                    
                    with col2:
                        avg_spam_rate = suspicious_authors['spam_percentage'].mean()
                        st.metric("Taux moyen de spam", f"{avg_spam_rate:.1f}%")
                    
                    # Auteurs avec pattern suspect
                    pattern_authors = suspicious_authors[
                        (suspicious_authors['total_reviews'] >= 3) & 
                        (suspicious_authors['spam_percentage'] >= 50)
                    ]
                    
                    if len(pattern_authors) > 0:
                        st.warning(f"**{len(pattern_authors)} auteurs** ont un pattern très suspect (≥3 avis, ≥50% de spam)")
            else:
                st.info("Aucune colonne auteur disponible pour l'analyse")
            
            # ===========================================
            # SECTION 7: TABLEAU COMPLET DES RÉSULTATS
            # ===========================================
            st.markdown("---")
            st.markdown("### 5. Résultats détaillés")
            
            # Préparer le tableau des résultats
            results_df = analysis_data.copy()
            
            # Ajouter des colonnes d'analyse
            results_df['statut'] = results_df['is_spam_final'].map({True: 'SPAM', False: 'HAM'})
            results_df['confiance'] = results_df['spam_confidence'].round(1)
            
            # Colonnes à afficher
            display_columns = ['statut', 'confiance']
            
            if author_col != 'Aucune':
                display_columns.insert(0, author_col)
            
            display_columns.append(review_col)
            
            if rating_col != 'Aucune':
                display_columns.append(rating_col)
            
            display_columns.extend(['text_length', 'suspicion_score_rules'])
            
            # Afficher le tableau
            st.markdown(f"**{len(results_df)} avis analysés**")
            
            # Filtres
            col1, col2 = st.columns(2)
            
            with col1:
                filter_status = st.multiselect(
                    "Filtrer par statut :",
                    ['SPAM', 'HAM'],
                    default=['SPAM'],
                    key="filter_status"
                )
            
            with col2:
                min_confidence = st.slider(
                    "Confiance minimale :",
                    0, 100, 0,
                    key="min_confidence_filter"
                )
            
            # Appliquer les filtres
            filtered_df = results_df[
                (results_df['statut'].isin(filter_status)) &
                (results_df['confiance'] >= min_confidence)
            ]
            
            st.dataframe(
                filtered_df[display_columns].head(100),
                use_container_width=True,
                height=500
            )
            
            # ===========================================
            # SECTION 8: EXPORT ET RAPPORT
            # ===========================================
            st.markdown("---")
            st.markdown("### 6. Export des résultats")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Export CSV complet
                csv_data = results_df[display_columns].to_csv(index=False)
                st.download_button(
                    label="Exporter tous les résultats (CSV)",
                    data=csv_data,
                    file_name=f"detection_faux_avis_complet_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # Export seulement les spam
                spam_df = results_df[results_df['statut'] == 'SPAM']
                if len(spam_df) > 0:
                    csv_spam = spam_df[display_columns].to_csv(index=False)
                    st.download_button(
                        label=f"Exporter les {len(spam_df)} SPAM (CSV)",
                        data=csv_spam,
                        file_name=f"faux_avis_detectes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            with col3:
                # Rapport synthétique
                report_content = f"""
                RAPPORT DE DÉTECTION DE FAUX AVIS
                ===================================
                
                Date d'analyse : {datetime.now().strftime('%d/%m/%Y %H:%M')}
                Fichier source : {st.session_state.get('uploaded_filename', 'N/A')}
                
                PARAMÈTRES DE DÉTECTION :
                - Longueur texte minimale : {min_text_length} caractères
                - Seuil répétition : {max_repetition}%
                - Détection notes extrêmes : {'Activée' if extreme_rating else 'Désactivée'}
                - Machine Learning : {'Activé' if ml_used else 'Désactivé'}
                - Seuil confiance : {confidence_threshold}%
                
                RÉSULTATS :
                - Total avis analysés : {len(analysis_data)}
                - Faux avis détectés (SPAM) : {total_spam}
                - Avis authentiques (HAM) : {len(analysis_data) - total_spam}
                - Taux de faux avis : {spam_percentage:.1f}%
                
                """
                
                if author_col != 'Aucune' and 'suspicious_authors' in locals():
                    report_content += f"""
                    ANALYSE PAR AUTEUR :
                    - Auteurs suspects identifiés : {len(suspicious_authors)}
                    - Auteurs avec pattern suspect : {len(pattern_authors) if 'pattern_authors' in locals() else 0}
                    
                    TOP 5 AUTEURS SUSPECTS :
                    """
                    
                    for i, (author, data) in enumerate(suspicious_authors.head(5).iterrows(), 1):
                        report_content += f"""
                        {i}. {author}:
                           - Total avis : {data['total_reviews']}
                           - Avis spam : {data['spam_count']}
                           - Taux spam : {data['spam_percentage']:.1f}%
                           - Confiance moyenne : {data['avg_confidence']:.1f}%
                        """
                
                report_content += f"""
                
                RECOMMANDATIONS :
                1. Vérifier manuellement les avis marqués SPAM avec haute confiance
                2. Surveiller les auteurs identifiés comme suspects
                3. Mettre en place une modération pour les nouveaux avis
                4. Réviser régulièrement les paramètres de détection
                
                Généré par AIM Analytics Platform
                """
                
                st.download_button(
                    label="Télécharger rapport détaillé",
                    data=report_content,
                    file_name=f"rapport_detection_faux_avis_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            # ===========================================
            # SECTION 9: ACTIONS RECOMMANDÉES
            # ===========================================
            st.markdown("---")
            st.markdown("### 7. Actions recommandées")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **Actions immédiates :**
                
                1. **Vérifier les SPAM haute confiance**
                   - Priorité aux avis avec confiance > 90%
                   - Vérifier manuellement au moins 10% des détections
                
                2. **Contacter les auteurs suspects**
                   - Auteurs avec ≥3 avis spam
                   - Pattern de notes extrêmes
                
                3. **Mettre à jour les filtres**
                   - Ajuster les seuils si faux positifs
                   - Ajouter mots-clés spécifiques au domaine
                """)
            
            with col2:
                st.markdown("""
                **Actions préventives :**
                
                1. **Implémenter CAPTCHA**
                   - Pour soumission d'avis
                   - Réduit les bots automatisés
                
                2. **Limite temporelle**
                   - 1 avis par utilisateur par jour
                   - Prévention des spams massifs
                
                3. **Signalement communautaire**
                   - Bouton "Signaler cet avis"
                   - Modération collaborative
                
                4. **Analyse périodique**
                   - Revue hebdomadaire des résultats
                   - Ajustement des algorithmes
                """)
            
            # Bouton pour ré-analyser
            st.markdown("---")
            if st.button("Relancer l'analyse avec nouveaux paramètres", use_container_width=True):
                st.rerun()

def render_classification_models(user, df):
    """Modèles de classification avancés"""
    st.markdown("### Modèles de Classification")
    
    # Sélection des données
    all_cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) < 2 or len(all_cols) < 3:
        st.warning("Besoin d'au moins 3 colonnes dont 2 numériques pour la classification")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_col = st.selectbox("Variable cible :", all_cols, key="ml_class_target")
    
    with col2:
        feature_options = [col for col in numeric_cols if col != target_col]
        feature_cols = st.multiselect("Variables prédictives :", 
                                     feature_options,
                                     default=feature_options[:3] if len(feature_options) >= 3 else feature_options,
                                     key="ml_class_features")
    
    if not target_col or not feature_cols:
        return
    
    # Préparation des données
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    
    data = df[[target_col] + feature_cols].dropna()
    
    if len(data) < 20:
        st.warning("Pas assez de données (minimum 20 observations)")
        return
    
    # Encoder la cible
    if data[target_col].dtype == 'object':
        le = LabelEncoder()
        y = le.fit_transform(data[target_col])
        class_names = le.classes_
    else:
        y = data[target_col].values
        if len(np.unique(y)) > 10:
            median_val = np.median(y)
            y = (y > median_val).astype(int)
            class_names = ['Classe 0', 'Classe 1']
        else:
            class_names = np.unique(y)
    
    X = data[feature_cols].values
    
    # Standardiser
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)
    
    # Sélection du modèle
    model_choice = st.selectbox(
        "Choix du modèle :",
        ["Random Forest", "SVM", "K-NN", "Régression Logistique", "Naive Bayes", "XGBoost"],
        key="class_model_choice"
    )
    
    # Configuration des paramètres
    if model_choice == "Random Forest":
        n_estimators = st.slider("Nombre d'arbres :", 10, 200, 100)
        max_depth = st.slider("Profondeur max :", 2, 20, 10)
        
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
    
    elif model_choice == "SVM":
        C = st.slider("Paramètre C :", 0.1, 10.0, 1.0)
        kernel = st.selectbox("Noyau :", ['linear', 'rbf', 'poly'], key="svm_kernel")
        
        from sklearn.svm import SVC
        model = SVC(C=C, kernel=kernel, random_state=42, probability=True)
    
    elif model_choice == "K-NN":
        n_neighbors = st.slider("Nombre de voisins :", 3, 20, 5)
        
        from sklearn.neighbors import KNeighborsClassifier
        model = KNeighborsClassifier(n_neighbors=n_neighbors)
    
    elif model_choice == "Régression Logistique":
        C = st.slider("Régularisation C :", 0.01, 10.0, 1.0)
        
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(C=C, random_state=42, max_iter=1000)
    
    elif model_choice == "Naive Bayes":
        from sklearn.naive_bayes import GaussianNB
        model = GaussianNB()
    
    elif model_choice == "XGBoost":
        try:
            from xgboost import XGBClassifier
            n_estimators = st.slider("Nombre d'arbres :", 50, 500, 100)
            max_depth = st.slider("Profondeur max :", 3, 15, 6)
            
            model = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        except:
            st.warning("XGBoost n'est pas installé. Utilisation de Random Forest à la place.")
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(random_state=42)
    
    # Entraînement
    if st.button("Entraîner le modèle", type="primary"):
        with st.spinner("Entraînement en cours..."):
            model.fit(X_train, y_train)
            
            # Prédictions
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
            
            # Évaluation
            from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                                       f1_score, confusion_matrix, classification_report,
                                       roc_curve, auc, precision_recall_curve)
            
            # Métriques de base
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted')
            recall = recall_score(y_test, y_pred, average='weighted')
            f1 = f1_score(y_test, y_pred, average='weighted')
            
            # Afficher les métriques
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Accuracy", f"{accuracy:.3f}")
            with col2:
                st.metric("Precision", f"{precision:.3f}")
            with col3:
                st.metric("Recall", f"{recall:.3f}")
            with col4:
                st.metric("F1-Score", f"{f1:.3f}")
            
            # MATRICE DE CONFUSION
            st.markdown("### Matrice de Confusion")
            cm = confusion_matrix(y_test, y_pred)
            
            fig_cm = px.imshow(
                cm,
                text_auto=True,
                color_continuous_scale='Blues',
                labels=dict(x="Prédit", y="Réel", color="Nombre"),
                x=[str(c) for c in class_names],
                y=[str(c) for c in class_names],
                title=f"Matrice de Confusion - {model_choice}"
            )
            st.plotly_chart(fig_cm, use_container_width=True)
            
            # Courbe ROC (pour classification binaire)
            if len(class_names) == 2 and y_prob is not None:
                st.markdown("### Courbe ROC")
                
                fpr, tpr, _ = roc_curve(y_test, y_prob[:, 1])
                roc_auc = auc(fpr, tpr)
                
                fig_roc = go.Figure()
                fig_roc.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines',
                                           name=f'ROC curve (AUC = {roc_auc:.3f})',
                                           line=dict(color='blue', width=2)))
                fig_roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines',
                                           name='Random', line=dict(color='red', dash='dash')))
                
                fig_roc.update_layout(
                    title=f'Courbe ROC - {model_choice}',
                    xaxis_title='False Positive Rate',
                    yaxis_title='True Positive Rate',
                    width=600, height=500
                )
                st.plotly_chart(fig_roc, use_container_width=True)
            
            # Rapport de classification
            st.markdown("### Rapport de Classification")
            report = classification_report(y_test, y_pred, target_names=[str(c) for c in class_names])
            st.text(report)
            
            # Importance des features
            if hasattr(model, 'feature_importances_'):
                st.markdown("### Importance des Variables")
                
                importance_df = pd.DataFrame({
                    'Variable': feature_cols,
                    'Importance': model.feature_importances_
                }).sort_values('Importance', ascending=False)
                
                fig_imp = px.bar(importance_df.head(10), x='Variable', y='Importance',
                               title="Top 10 des variables les plus importantes")
                st.plotly_chart(fig_imp, use_container_width=True)
            
            # Prédictions sur de nouvelles données
            st.markdown("### Faire une prédiction")
            
            col1, col2 = st.columns(2)
            input_values = {}
            
            for i, feature in enumerate(feature_cols[:4]):  # Limiter à 4 features pour l'affichage
                with col1 if i % 2 == 0 else col2:
                    mean_val = df[feature].mean()
                    std_val = df[feature].std()
                    input_values[feature] = st.number_input(
                        f"{feature} :",
                        value=float(mean_val),
                        step=float(std_val/10)
                    )
            
            if st.button("Prédire"):
                # Préparer l'input
                input_array = np.array([[input_values[f] for f in feature_cols]])
                input_scaled = scaler.transform(input_array)
                
                # Faire la prédiction
                prediction = model.predict(input_scaled)[0]
                proba = model.predict_proba(input_scaled)[0] if hasattr(model, 'predict_proba') else None
                
                if proba is not None:
                    st.success(f"**Prédiction :** {class_names[prediction]}")
                    st.info(f"**Probabilités :**")
                    for i, prob in enumerate(proba):
                        st.write(f"- {class_names[i]}: {prob:.3f}")
                else:
                    st.success(f"**Prédiction :** {class_names[prediction]}")

# Fonctions simplifiées pour les autres types de modèles

def render_regression_models(user, df):
    """Modèles de régression"""
    st.markdown("### Modèles de Régression")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) >= 2:
        col1, col2 = st.columns(2)
        
        with col1:
            x_col = st.selectbox("Variable indépendante (X) :", numeric_cols, key="reg_ml_x")
        
        with col2:
            y_col = st.selectbox("Variable dépendante (Y) :", numeric_cols, 
                               index=1 if len(numeric_cols) > 1 else 0, 
                               key="reg_ml_y")
        
        model_choice = st.selectbox(
            "Choix du modèle :",
            ["Régression Linéaire", "Ridge", "Lasso", "Random Forest Regressor"],
            key="reg_model_choice"
        )
        
        if st.button("Entraîner le modèle de régression", type="primary"):
            with st.spinner("Entraînement en cours..."):
                from sklearn.model_selection import train_test_split
                from sklearn.preprocessing import StandardScaler
                from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
                
                data = df[[x_col, y_col]].dropna()
                X = data[[x_col]].values
                y = data[y_col].values
                
                # Split
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
                
                # Choix du modèle
                if model_choice == "Régression Linéaire":
                    from sklearn.linear_model import LinearRegression
                    model = LinearRegression()
                
                elif model_choice == "Ridge":
                    from sklearn.linear_model import Ridge
                    alpha = st.slider("Alpha (régularisation) :", 0.1, 10.0, 1.0)
                    model = Ridge(alpha=alpha)
                
                elif model_choice == "Lasso":
                    from sklearn.linear_model import Lasso
                    alpha = st.slider("Alpha (régularisation) :", 0.01, 1.0, 0.1)
                    model = Lasso(alpha=alpha)
                
                elif model_choice == "Random Forest Regressor":
                    from sklearn.ensemble import RandomForestRegressor
                    n_estimators = st.slider("Nombre d'arbres :", 10, 200, 100)
                    model = RandomForestRegressor(n_estimators=n_estimators, random_state=42)
                
                # Entraînement
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                
                # Métriques
                mse = mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                # Affichage des résultats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("R² Score", f"{r2:.3f}")
                with col2:
                    st.metric("RMSE", f"{rmse:.3f}")
                with col3:
                    st.metric("MAE", f"{mae:.3f}")
                with col4:
                    st.metric("MSE", f"{mse:.3f}")
                
                # Visualisation
                fig = px.scatter(x=y_test, y=y_pred, 
                               labels={'x': 'Valeurs réelles', 'y': 'Prédictions'},
                               title=f"Prédictions vs Réelles - {model_choice}")
                fig.add_trace(go.Scatter(x=[y_test.min(), y_test.max()], 
                                       y=[y_test.min(), y_test.max()],
                                       mode='lines', name='Ligne parfaite',
                                       line=dict(color='red', dash='dash')))
                
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Besoin d'au moins 2 colonnes numériques pour la régression")

def render_clustering_models(user, df):
    """Modèles de clustering"""
    st.markdown("### Modèles de Clustering")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) >= 2:
        selected_cols = st.multiselect("Sélectionnez les variables :",
                                      numeric_cols,
                                      default=numeric_cols[:2] if len(numeric_cols) >= 2 else numeric_cols,
                                      key="cluster_features")
        
        model_choice = st.selectbox(
            "Algorithme de clustering :",
            ["K-Means", "DBSCAN", "Agglomerative Clustering"],
            key="cluster_algorithm"
        )
        
        if len(selected_cols) >= 2:
            from sklearn.preprocessing import StandardScaler
            
            data = df[selected_cols].dropna()
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            
            if model_choice == "K-Means":
                n_clusters = st.slider("Nombre de clusters :", 2, 10, 3, key="kmeans_n")
                
                from sklearn.cluster import KMeans
                model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                clusters = model.fit_predict(scaled_data)
                
            elif model_choice == "DBSCAN":
                eps = st.slider("Epsilon :", 0.1, 2.0, 0.5, key="dbscan_eps")
                min_samples = st.slider("Échantillons minimum :", 2, 20, 5, key="dbscan_min")
                
                from sklearn.cluster import DBSCAN
                model = DBSCAN(eps=eps, min_samples=min_samples)
                clusters = model.fit_predict(scaled_data)
                
            elif model_choice == "Agglomerative Clustering":
                n_clusters = st.slider("Nombre de clusters :", 2, 10, 3, key="agg_n")
                linkage = st.selectbox("Lien :", ['ward', 'complete', 'average', 'single'])
                
                from sklearn.cluster import AgglomerativeClustering
                model = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage)
                clusters = model.fit_predict(scaled_data)
            
            if st.button("Appliquer le clustering", type="primary"):
                # Visualisation
                data['cluster'] = clusters
                
                if len(selected_cols) >= 2:
                    fig = px.scatter(data, x=selected_cols[0], y=selected_cols[1],
                                   color='cluster', title=f"Clustering - {model_choice}",
                                   color_continuous_scale=px.colors.qualitative.Set3)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Statistiques des clusters
                st.markdown("### Statistiques des clusters")
                cluster_stats = data.groupby('cluster').agg(['mean', 'std', 'count']).round(2)
                st.dataframe(cluster_stats, use_container_width=True)
    else:
        st.warning("Besoin d'au moins 2 colonnes numériques pour le clustering")

def render_dimensionality_reduction(user, df):
    """Réduction de dimension"""
    st.markdown("### Réduction de Dimension")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) >= 3:
        selected_cols = st.multiselect("Sélectionnez les variables :",
                                      numeric_cols,
                                      default=numeric_cols[:5] if len(numeric_cols) >= 5 else numeric_cols,
                                      key="pca_features")
        
        method = st.selectbox(
            "Méthode :",
            ["PCA", "t-SNE", "UMAP"],
            key="dim_reduction_method"
        )
        
        n_components = st.slider("Nombre de composantes :", 2, 5, 2, key="n_components")
        
        if len(selected_cols) >= 3:
            from sklearn.preprocessing import StandardScaler
            
            data = df[selected_cols].dropna()
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            
            if method == "PCA":
                from sklearn.decomposition import PCA
                reducer = PCA(n_components=n_components)
                reduced_data = reducer.fit_transform(scaled_data)
                
                # Variance expliquée
                var_exp = reducer.explained_variance_ratio_
                
                st.markdown("### Variance expliquée")
                for i, var in enumerate(var_exp, 1):
                    st.write(f"- Composante {i}: {var*100:.1f}%")
                st.write(f"- **Total:** {sum(var_exp)*100:.1f}%")
                
            elif method == "t-SNE":
                from sklearn.manifold import TSNE
                reducer = TSNE(n_components=n_components, random_state=42)
                reduced_data = reducer.fit_transform(scaled_data)
                
            elif method == "UMAP":
                try:
                    from umap import UMAP
                    reducer = UMAP(n_components=n_components, random_state=42)
                    reduced_data = reducer.fit_transform(scaled_data)
                except:
                    st.warning("UMAP n'est pas installé. Utilisation de PCA.")
                    from sklearn.decomposition import PCA
                    reducer = PCA(n_components=n_components)
                    reduced_data = reducer.fit_transform(scaled_data)
            
            if st.button("Appliquer la réduction de dimension", type="primary"):
                # Visualisation
                reduced_df = pd.DataFrame(reduced_data, 
                                        columns=[f'Composante {i+1}' for i in range(n_components)])
                
                if n_components >= 2:
                    fig = px.scatter(reduced_df, x='Composante 1', y='Composante 2',
                                   title=f"Réduction de dimension - {method}")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Matrice des composantes
                st.markdown("### Composantes principales")
                st.dataframe(reduced_df.head(10), use_container_width=True)
    else:
        st.warning("Besoin d'au moins 3 colonnes numériques pour la réduction de dimension")

def render_ensemble_models(user, df):
    """Modèles d'ensemble"""
    st.markdown("### Ensemble Learning")
    
    st.info("""
    ### Modèles d'Ensemble
    
    Les modèles d'ensemble combinent plusieurs modèles pour améliorer les performances.
    Cette section permet d'expérimenter avec différentes techniques d'ensemble.
    
    **Fonctionnalités disponibles :**
    - Bagging (Bootstrap Aggregating)
    - Boosting
    - Stacking
    - Voting Classifiers
    
    *Sélectionnez une technique ci-dessous :*
    """)
    
    ensemble_method = st.selectbox(
        "Technique d'ensemble :",
        ["Voting Classifier", "Bagging", "Boosting", "Stacking"],
        key="ensemble_method"
    )
    
    if ensemble_method == "Voting Classifier":
        st.markdown("""
        ### Voting Classifier
        
        Combine les prédictions de plusieurs classificateurs en utilisant le vote majoritaire
        ou le vote pondéré par les probabilités.
        """)
        
    elif ensemble_method == "Bagging":
        st.markdown("""
        ### Bagging (Bootstrap Aggregating)
        
        Entraîne plusieurs instances du même modèle sur des sous-échantillons bootstrap
        des données d'entraînement, puis combine leurs prédictions.
        """)
        
    elif ensemble_method == "Boosting":
        st.markdown("""
        ### Boosting
        
        Entraîne séquentiellement plusieurs modèles faibles, chaque nouveau modèle
        corrige les erreurs des précédents.
        """)
        
    elif ensemble_method == "Stacking":
        st.markdown("""
        ### Stacking
        
        Combine les prédictions de plusieurs modèles de base en utilisant un méta-modèle
        qui apprend à pondérer les prédictions.
        """)
    
    # Exemple simple de Voting Classifier
    if st.button("Essayer un Voting Classifier simple", type="primary"):
        try:
            from sklearn.ensemble import VotingClassifier
            from sklearn.tree import DecisionTreeClassifier
            from sklearn.svm import SVC
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler, LabelEncoder
            
            # Préparer des données simples
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            
            if len(numeric_cols) >= 3:
                # Prendre 3 colonnes pour l'exemple
                sample_cols = numeric_cols[:3]
                sample_data = df[sample_cols].dropna().head(100)  # Limiter à 100 lignes
                
                # Créer une variable cible binaire simple
                median_val = sample_data[sample_cols[0]].median()
                y = (sample_data[sample_cols[0]] > median_val).astype(int)
                X = sample_data[sample_cols[1:]].values
                
                # Standardiser
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                
                # Split
                X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)
                
                # Créer les classificateurs de base
                clf1 = LogisticRegression(random_state=42)
                clf2 = DecisionTreeClassifier(max_depth=5, random_state=42)
                clf3 = SVC(probability=True, random_state=42)
                
                # Créer le Voting Classifier
                eclf = VotingClassifier(
                    estimators=[('lr', clf1), ('dt', clf2), ('svc', clf3)],
                    voting='soft'  # soft voting utilise les probabilités
                )
                
                # Entraîner
                eclf.fit(X_train, y_train)
                
                # Évaluer
                from sklearn.metrics import accuracy_score
                y_pred = eclf.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)
                
                st.success(f"Accuracy du Voting Classifier: {accuracy:.3f}")
                
                # Comparer avec les classificateurs individuels
                st.markdown("### Comparaison avec les classificateurs individuels")
                
                scores = []
                for clf, label in zip([clf1, clf2, clf3, eclf], 
                                     ['Logistic Regression', 'Decision Tree', 'SVM', 'Voting Classifier']):
                    clf.fit(X_train, y_train)
                    score = clf.score(X_test, y_test)
                    scores.append((label, score))
                
                scores_df = pd.DataFrame(scores, columns=['Modèle', 'Accuracy'])
                scores_df = scores_df.sort_values('Accuracy', ascending=False)
                
                fig = px.bar(scores_df, x='Modèle', y='Accuracy', 
                           title="Comparaison des performances",
                           color='Accuracy',
                           color_continuous_scale='Viridis')
                
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.warning("Besoin d'au moins 3 colonnes numériques pour cet exemple")
                
        except Exception as e:
            st.error(f"Erreur: {str(e)}")
            
def render_ml_models(user, db):
    """Page dédiée aux modèles de machine learning"""
    st.subheader("Modèles de Machine Learning")
    
    if 'uploaded_data' not in st.session_state:
        st.warning("Importez d'abord vos données pour utiliser les modèles ML")
        return
    
    df = st.session_state['uploaded_data']
    
    st.markdown("""
    ### Modèles de Machine Learning Avancés
    
    Cette section vous permet d'entraîner et d'évaluer différents modèles de machine learning
    sur vos données. Choisissez un type de modèle et configurez les paramètres.
    """)
    
    model_type = st.selectbox(
        "Type de modèle :",
        ["Classification", "Régression", "Clustering", "Réduction de dimension", "Ensemble Learning"],
        key="ml_model_type"
    )
    
    if model_type == "Classification":
        render_classification_models(user, df)
    elif model_type == "Régression":
        render_regression_models(user, df)
    elif model_type == "Clustering":
        render_clustering_models(user, df)
    elif model_type == "Réduction de dimension":
        render_dimensionality_reduction(user, df)
    elif model_type == "Ensemble Learning":
        render_ensemble_models(user, df)

def render_classification_models(user, df):
    """Modèles de classification avancés"""
    st.markdown("### Modèles de Classification")
    
    # Sélection des données
    all_cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) < 2 or len(all_cols) < 3:
        st.warning("Besoin d'au moins 3 colonnes dont 2 numériques pour la classification")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_col = st.selectbox("Variable cible :", all_cols, key="ml_class_target")
    
    with col2:
        feature_options = [col for col in numeric_cols if col != target_col]
        feature_cols = st.multiselect("Variables prédictives :", 
                                     feature_options,
                                     default=feature_options[:3] if len(feature_options) >= 3 else feature_options,
                                     key="ml_class_features")
    
    if not target_col or not feature_cols:
        return
    
    # Préparation des données
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    
    data = df[[target_col] + feature_cols].dropna()
    
    if len(data) < 20:
        st.warning("Pas assez de données (minimum 20 observations)")
        return
    
    # Encoder la cible
    if data[target_col].dtype == 'object':
        le = LabelEncoder()
        y = le.fit_transform(data[target_col])
        class_names = le.classes_
    else:
        y = data[target_col].values
        if len(np.unique(y)) > 10:
            median_val = np.median(y)
            y = (y > median_val).astype(int)
            class_names = ['Classe 0', 'Classe 1']
        else:
            class_names = np.unique(y)
    
    X = data[feature_cols].values
    
    # Standardiser
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)
    
    # Sélection du modèle
    model_choice = st.selectbox(
        "Choix du modèle :",
        ["Random Forest", "SVM", "K-NN", "Régression Logistique", "Naive Bayes", "XGBoost"],
        key="class_model_choice"
    )
    
    # Configuration des paramètres
    if model_choice == "Random Forest":
        n_estimators = st.slider("Nombre d'arbres :", 10, 200, 100)
        max_depth = st.slider("Profondeur max :", 2, 20, 10)
        
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
    
    elif model_choice == "SVM":
        C = st.slider("Paramètre C :", 0.1, 10.0, 1.0)
        kernel = st.selectbox("Noyau :", ['linear', 'rbf', 'poly'], key="svm_kernel")
        
        from sklearn.svm import SVC
        model = SVC(C=C, kernel=kernel, random_state=42, probability=True)
    
    elif model_choice == "K-NN":
        n_neighbors = st.slider("Nombre de voisins :", 3, 20, 5)
        
        from sklearn.neighbors import KNeighborsClassifier
        model = KNeighborsClassifier(n_neighbors=n_neighbors)
    
    elif model_choice == "Régression Logistique":
        C = st.slider("Régularisation C :", 0.01, 10.0, 1.0)
        
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(C=C, random_state=42, max_iter=1000)
    
    elif model_choice == "Naive Bayes":
        from sklearn.naive_bayes import GaussianNB
        model = GaussianNB()
    
    elif model_choice == "XGBoost":
        try:
            from xgboost import XGBClassifier
            n_estimators = st.slider("Nombre d'arbres :", 50, 500, 100)
            max_depth = st.slider("Profondeur max :", 3, 15, 6)
            
            model = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        except:
            st.warning("XGBoost n'est pas installé. Utilisation de Random Forest à la place.")
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(random_state=42)
    
    # Entraînement
    if st.button("Entraîner le modèle", type="primary"):
        with st.spinner("Entraînement en cours..."):
            model.fit(X_train, y_train)
            
            # Prédictions
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
            
            # Évaluation
            from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                                       f1_score, confusion_matrix, classification_report,
                                       roc_curve, auc, precision_recall_curve)
            
            # Métriques de base
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted')
            recall = recall_score(y_test, y_pred, average='weighted')
            f1 = f1_score(y_test, y_pred, average='weighted')
            
            # Afficher les métriques
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Accuracy", f"{accuracy:.3f}")
            with col2:
                st.metric("Precision", f"{precision:.3f}")
            with col3:
                st.metric("Recall", f"{recall:.3f}")
            with col4:
                st.metric("F1-Score", f"{f1:.3f}")
            
            # MATRICE DE CONFUSION
            st.markdown("### Matrice de Confusion")
            cm = confusion_matrix(y_test, y_pred)
            
            fig_cm = px.imshow(
                cm,
                text_auto=True,
                color_continuous_scale='Blues',
                labels=dict(x="Prédit", y="Réel", color="Nombre"),
                x=[str(c) for c in class_names],
                y=[str(c) for c in class_names],
                title=f"Matrice de Confusion - {model_choice}"
            )
            st.plotly_chart(fig_cm, use_container_width=True)
            
            # Courbe ROC (pour classification binaire)
            if len(class_names) == 2 and y_prob is not None:
                st.markdown("### Courbe ROC")
                
                fpr, tpr, _ = roc_curve(y_test, y_prob[:, 1])
                roc_auc = auc(fpr, tpr)
                
                fig_roc = go.Figure()
                fig_roc.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines',
                                           name=f'ROC curve (AUC = {roc_auc:.3f})',
                                           line=dict(color='blue', width=2)))
                fig_roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines',
                                           name='Random', line=dict(color='red', dash='dash')))
                
                fig_roc.update_layout(
                    title=f'Courbe ROC - {model_choice}',
                    xaxis_title='False Positive Rate',
                    yaxis_title='True Positive Rate',
                    width=600, height=500
                )
                st.plotly_chart(fig_roc, use_container_width=True)
            
            # Rapport de classification
            st.markdown("### Rapport de Classification")
            report = classification_report(y_test, y_pred, target_names=[str(c) for c in class_names])
            st.text(report)
            
            # Importance des features
            if hasattr(model, 'feature_importances_'):
                st.markdown("### Importance des Variables")
                
                importance_df = pd.DataFrame({
                    'Variable': feature_cols,
                    'Importance': model.feature_importances_
                }).sort_values('Importance', ascending=False)
                
                fig_imp = px.bar(importance_df.head(10), x='Variable', y='Importance',
                               title="Top 10 des variables les plus importantes")
                st.plotly_chart(fig_imp, use_container_width=True)
            
            # Prédictions sur de nouvelles données
            st.markdown("### Faire une prédiction")
            
            col1, col2 = st.columns(2)
            input_values = {}
            
            for i, feature in enumerate(feature_cols[:4]):  # Limiter à 4 features pour l'affichage
                with col1 if i % 2 == 0 else col2:
                    mean_val = df[feature].mean()
                    std_val = df[feature].std()
                    input_values[feature] = st.number_input(
                        f"{feature} :",
                        value=float(mean_val),
                        step=float(std_val/10)
                    )
            
            if st.button("Prédire"):
                # Préparer l'input
                input_array = np.array([[input_values[f] for f in feature_cols]])
                input_scaled = scaler.transform(input_array)
                
                # Faire la prédiction
                prediction = model.predict(input_scaled)[0]
                proba = model.predict_proba(input_scaled)[0] if hasattr(model, 'predict_proba') else None
                
                if proba is not None:
                    st.success(f"**Prédiction :** {class_names[prediction]}")
                    st.info(f"**Probabilités :**")
                    for i, prob in enumerate(proba):
                        st.write(f"- {class_names[i]}: {prob:.3f}")
                else:
                    st.success(f"**Prédiction :** {class_names[prediction]}")

# Fonctions simplifiées pour les autres types de modèles

def render_regression_models(user, df):
    """Modèles de régression"""
    st.markdown("### Modèles de Régression")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) >= 2:
        col1, col2 = st.columns(2)
        
        with col1:
            x_col = st.selectbox("Variable indépendante (X) :", numeric_cols, key="reg_ml_x")
        
        with col2:
            y_col = st.selectbox("Variable dépendante (Y) :", numeric_cols, 
                               index=1 if len(numeric_cols) > 1 else 0, 
                               key="reg_ml_y")
        
        model_choice = st.selectbox(
            "Choix du modèle :",
            ["Régression Linéaire", "Ridge", "Lasso", "Random Forest Regressor"],
            key="reg_model_choice"
        )
        
        if st.button("Entraîner le modèle de régression", type="primary"):
            with st.spinner("Entraînement en cours..."):
                from sklearn.model_selection import train_test_split
                from sklearn.preprocessing import StandardScaler
                from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
                
                data = df[[x_col, y_col]].dropna()
                X = data[[x_col]].values
                y = data[y_col].values
                
                # Split
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
                
                # Choix du modèle
                if model_choice == "Régression Linéaire":
                    from sklearn.linear_model import LinearRegression
                    model = LinearRegression()
                
                elif model_choice == "Ridge":
                    from sklearn.linear_model import Ridge
                    alpha = st.slider("Alpha (régularisation) :", 0.1, 10.0, 1.0)
                    model = Ridge(alpha=alpha)
                
                elif model_choice == "Lasso":
                    from sklearn.linear_model import Lasso
                    alpha = st.slider("Alpha (régularisation) :", 0.01, 1.0, 0.1)
                    model = Lasso(alpha=alpha)
                
                elif model_choice == "Random Forest Regressor":
                    from sklearn.ensemble import RandomForestRegressor
                    n_estimators = st.slider("Nombre d'arbres :", 10, 200, 100)
                    model = RandomForestRegressor(n_estimators=n_estimators, random_state=42)
                
                # Entraînement
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                
                # Métriques
                mse = mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                # Affichage des résultats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("R² Score", f"{r2:.3f}")
                with col2:
                    st.metric("RMSE", f"{rmse:.3f}")
                with col3:
                    st.metric("MAE", f"{mae:.3f}")
                with col4:
                    st.metric("MSE", f"{mse:.3f}")
                
                # Visualisation
                fig = px.scatter(x=y_test, y=y_pred, 
                               labels={'x': 'Valeurs réelles', 'y': 'Prédictions'},
                               title=f"Prédictions vs Réelles - {model_choice}")
                fig.add_trace(go.Scatter(x=[y_test.min(), y_test.max()], 
                                       y=[y_test.min(), y_test.max()],
                                       mode='lines', name='Ligne parfaite',
                                       line=dict(color='red', dash='dash')))
                
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Besoin d'au moins 2 colonnes numériques pour la régression")

def render_clustering_models(user, df):
    """Modèles de clustering"""
    st.markdown("### Modèles de Clustering")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) >= 2:
        selected_cols = st.multiselect("Sélectionnez les variables :",
                                      numeric_cols,
                                      default=numeric_cols[:2] if len(numeric_cols) >= 2 else numeric_cols,
                                      key="cluster_features")
        
        model_choice = st.selectbox(
            "Algorithme de clustering :",
            ["K-Means", "DBSCAN", "Agglomerative Clustering"],
            key="cluster_algorithm"
        )
        
        if len(selected_cols) >= 2:
            from sklearn.preprocessing import StandardScaler
            
            data = df[selected_cols].dropna()
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            
            if model_choice == "K-Means":
                n_clusters = st.slider("Nombre de clusters :", 2, 10, 3, key="kmeans_n")
                
                from sklearn.cluster import KMeans
                model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                clusters = model.fit_predict(scaled_data)
                
            elif model_choice == "DBSCAN":
                eps = st.slider("Epsilon :", 0.1, 2.0, 0.5, key="dbscan_eps")
                min_samples = st.slider("Échantillons minimum :", 2, 20, 5, key="dbscan_min")
                
                from sklearn.cluster import DBSCAN
                model = DBSCAN(eps=eps, min_samples=min_samples)
                clusters = model.fit_predict(scaled_data)
                
            elif model_choice == "Agglomerative Clustering":
                n_clusters = st.slider("Nombre de clusters :", 2, 10, 3, key="agg_n")
                linkage = st.selectbox("Lien :", ['ward', 'complete', 'average', 'single'])
                
                from sklearn.cluster import AgglomerativeClustering
                model = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage)
                clusters = model.fit_predict(scaled_data)
            
            if st.button("Appliquer le clustering", type="primary"):
                # Visualisation
                data['cluster'] = clusters
                
                if len(selected_cols) >= 2:
                    fig = px.scatter(data, x=selected_cols[0], y=selected_cols[1],
                                   color='cluster', title=f"Clustering - {model_choice}",
                                   color_continuous_scale=px.colors.qualitative.Set3)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Statistiques des clusters
                st.markdown("### Statistiques des clusters")
                cluster_stats = data.groupby('cluster').agg(['mean', 'std', 'count']).round(2)
                st.dataframe(cluster_stats, use_container_width=True)
    else:
        st.warning("Besoin d'au moins 2 colonnes numériques pour le clustering")

def render_dimensionality_reduction(user, df):
    """Réduction de dimension"""
    st.markdown("### Réduction de Dimension")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) >= 3:
        selected_cols = st.multiselect("Sélectionnez les variables :",
                                      numeric_cols,
                                      default=numeric_cols[:5] if len(numeric_cols) >= 5 else numeric_cols,
                                      key="pca_features")
        
        method = st.selectbox(
            "Méthode :",
            ["PCA", "t-SNE", "UMAP"],
            key="dim_reduction_method"
        )
        
        n_components = st.slider("Nombre de composantes :", 2, 5, 2, key="n_components")
        
        if len(selected_cols) >= 3:
            from sklearn.preprocessing import StandardScaler
            
            data = df[selected_cols].dropna()
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(data)
            
            if method == "PCA":
                from sklearn.decomposition import PCA
                reducer = PCA(n_components=n_components)
                reduced_data = reducer.fit_transform(scaled_data)
                
                # Variance expliquée
                var_exp = reducer.explained_variance_ratio_
                
                st.markdown("### Variance expliquée")
                for i, var in enumerate(var_exp, 1):
                    st.write(f"- Composante {i}: {var*100:.1f}%")
                st.write(f"- **Total:** {sum(var_exp)*100:.1f}%")
                
            elif method == "t-SNE":
                from sklearn.manifold import TSNE
                reducer = TSNE(n_components=n_components, random_state=42)
                reduced_data = reducer.fit_transform(scaled_data)
                
            elif method == "UMAP":
                try:
                    from umap import UMAP
                    reducer = UMAP(n_components=n_components, random_state=42)
                    reduced_data = reducer.fit_transform(scaled_data)
                except:
                    st.warning("UMAP n'est pas installé. Utilisation de PCA.")
                    from sklearn.decomposition import PCA
                    reducer = PCA(n_components=n_components)
                    reduced_data = reducer.fit_transform(scaled_data)
            
            if st.button("Appliquer la réduction de dimension", type="primary"):
                # Visualisation
                reduced_df = pd.DataFrame(reduced_data, 
                                        columns=[f'Composante {i+1}' for i in range(n_components)])
                
                if n_components >= 2:
                    fig = px.scatter(reduced_df, x='Composante 1', y='Composante 2',
                                   title=f"Réduction de dimension - {method}")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Matrice des composantes
                st.markdown("### Composantes principales")
                st.dataframe(reduced_df.head(10), use_container_width=True)
    else:
        st.warning("Besoin d'au moins 3 colonnes numériques pour la réduction de dimension")

def render_ensemble_models(user, df):
    """Modèles d'ensemble"""
    st.markdown("### Ensemble Learning")
    
    st.info("""
    ### Modèles d'Ensemble
    
    Les modèles d'ensemble combinent plusieurs modèles pour améliorer les performances.
    Cette section permet d'expérimenter avec différentes techniques d'ensemble.
    
    **Fonctionnalités disponibles :**
    - Bagging (Bootstrap Aggregating)
    - Boosting
    - Stacking
    - Voting Classifiers
    
    *Sélectionnez une technique ci-dessous :*
    """)
    
    ensemble_method = st.selectbox(
        "Technique d'ensemble :",
        ["Voting Classifier", "Bagging", "Boosting", "Stacking"],
        key="ensemble_method"
    )
    
    if ensemble_method == "Voting Classifier":
        st.markdown("""
        ### Voting Classifier
        
        Combine les prédictions de plusieurs classificateurs en utilisant le vote majoritaire
        ou le vote pondéré par les probabilités.
        """)
        
    elif ensemble_method == "Bagging":
        st.markdown("""
        ### Bagging (Bootstrap Aggregating)
        
        Entraîne plusieurs instances du même modèle sur des sous-échantillons bootstrap
        des données d'entraînement, puis combine leurs prédictions.
        """)
        
    elif ensemble_method == "Boosting":
        st.markdown("""
        ### Boosting
        
        Entraîne séquentiellement plusieurs modèles faibles, chaque nouveau modèle
        corrige les erreurs des précédents.
        """)
        
    elif ensemble_method == "Stacking":
        st.markdown("""
        ### Stacking
        
        Combine les prédictions de plusieurs modèles de base en utilisant un méta-modèle
        qui apprend à pondérer les prédictions.
        """)
    
    # Exemple simple de Voting Classifier
    if st.button("Essayer un Voting Classifier simple", type="primary"):
        try:
            from sklearn.ensemble import VotingClassifier
            from sklearn.tree import DecisionTreeClassifier
            from sklearn.svm import SVC
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler, LabelEncoder
            
            # Préparer des données simples
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            
            if len(numeric_cols) >= 3:
                # Prendre 3 colonnes pour l'exemple
                sample_cols = numeric_cols[:3]
                sample_data = df[sample_cols].dropna().head(100)  # Limiter à 100 lignes
                
                # Créer une variable cible binaire simple
                median_val = sample_data[sample_cols[0]].median()
                y = (sample_data[sample_cols[0]] > median_val).astype(int)
                X = sample_data[sample_cols[1:]].values
                
                # Standardiser
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                
                # Split
                X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)
                
                # Créer les classificateurs de base
                clf1 = LogisticRegression(random_state=42)
                clf2 = DecisionTreeClassifier(max_depth=5, random_state=42)
                clf3 = SVC(probability=True, random_state=42)
                
                # Créer le Voting Classifier
                eclf = VotingClassifier(
                    estimators=[('lr', clf1), ('dt', clf2), ('svc', clf3)],
                    voting='soft'  # soft voting utilise les probabilités
                )
                
                # Entraîner
                eclf.fit(X_train, y_train)
                
                # Évaluer
                from sklearn.metrics import accuracy_score
                y_pred = eclf.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)
                
                st.success(f"Accuracy du Voting Classifier: {accuracy:.3f}")
                
                # Comparer avec les classificateurs individuels
                st.markdown("### Comparaison avec les classificateurs individuels")
                
                scores = []
                for clf, label in zip([clf1, clf2, clf3, eclf], 
                                     ['Logistic Regression', 'Decision Tree', 'SVM', 'Voting Classifier']):
                    clf.fit(X_train, y_train)
                    score = clf.score(X_test, y_test)
                    scores.append((label, score))
                
                scores_df = pd.DataFrame(scores, columns=['Modèle', 'Accuracy'])
                scores_df = scores_df.sort_values('Accuracy', ascending=False)
                
                fig = px.bar(scores_df, x='Modèle', y='Accuracy', 
                           title="Comparaison des performances",
                           color='Accuracy',
                           color_continuous_scale='Viridis')
                
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.warning("Besoin d'au moins 3 colonnes numériques pour cet exemple")
                
        except Exception as e:
            st.error(f"Erreur: {str(e)}")

def render_eda_analysis(user, db):
    """Analyse Exploratoire des Données (EDA)"""
    st.subheader("Analyse Exploratoire des Données (EDA)")
    
    # Vérifier si des données ont été importées
    if 'uploaded_data' not in st.session_state or st.session_state['uploaded_data'] is None:
        st.warning("Aucune donnée importée")
        st.markdown("""
        Pour effectuer une analyse exploratoire des données :
        1. Importez un fichier CSV ou Excel depuis la sidebar à gauche
        2. Attendez que les données soient chargées
        3. Revenez sur cette page pour analyser vos données
        """)
        return
    
    df = st.session_state['uploaded_data']
    filename = st.session_state.get('uploaded_filename', 'Fichier importé')
    
    st.success(f"Analyse EDA de: {filename}")
    
    # Créer des onglets pour différentes analyses EDA
    tab1, tab2, tab3 = st.tabs(["Aperçu", "Nettoyage", "Export"])
    
    with tab1:
        st.markdown("### Aperçu des Données")
        
        # Informations générales
        cols = st.columns(3)
        with cols[0]:
            st.metric("Lignes", df.shape[0])
        with cols[1]:
            st.metric("Colonnes", df.shape[1])
        with cols[2]:
            missing_total = df.isnull().sum().sum()
            st.metric("Valeurs manquantes", missing_total)
        
        # Aperçu du dataframe
        st.markdown("#### Prévisualisation des données")
        num_rows_preview = st.slider("Nombre de lignes à afficher", 5, 50, 10, key="preview_rows")
        
        cols = st.columns(2)
        with cols[0]:
            show_head = st.checkbox("Afficher les premières lignes", value=True, key="show_head")
        with cols[1]:
            show_tail = st.checkbox("Afficher les dernières lignes", key="show_tail")
        
        if show_head:
            st.markdown(f"Premières {num_rows_preview} lignes :")
            st.dataframe(df.head(num_rows_preview), use_container_width=True)
        
        if show_tail:
            st.markdown(f"Dernières {num_rows_preview} lignes :")
            st.dataframe(df.tail(num_rows_preview), use_container_width=True)
        
        # Types de données
        st.markdown("#### Types de données")
        dtype_info = pd.DataFrame({
            'Colonne': df.columns,
            'Type': df.dtypes.astype(str),
            'Valeurs uniques': [df[col].nunique() for col in df.columns],
            'Valeurs manquantes': df.isnull().sum().values
        })
        st.dataframe(dtype_info, use_container_width=True, height=400)
        
        # Statistiques descriptives
        st.markdown("#### Statistiques descriptives")
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if numeric_cols:
            desc_stats = df[numeric_cols].describe().T
            desc_stats['IQR'] = desc_stats['75%'] - desc_stats['25%']
            desc_stats = desc_stats[['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max', 'IQR']]
            st.dataframe(desc_stats, use_container_width=True)
        else:
            st.info("Aucune colonne numérique pour les statistiques descriptives")
    
    with tab2:
        st.markdown("### Nettoyage des données")
        
        # Détection des valeurs manquantes
        st.markdown("#### Détection des valeurs manquantes")
        missing_data = df.isnull().sum()
        missing_percent = (missing_data / len(df)) * 100
        
        missing_df = pd.DataFrame({
            'Colonne': missing_data.index,
            'Valeurs manquantes': missing_data.values,
            'Pourcentage': missing_percent.values
        })
        missing_df = missing_df[missing_df['Valeurs manquantes'] > 0].sort_values('Pourcentage', ascending=False)
        
        if len(missing_df) > 0:
            st.dataframe(missing_df, use_container_width=True)
            
            # Options de traitement
            st.markdown("#### Traitement des valeurs manquantes")
            treatment_col = st.selectbox("Sélectionner une colonne à traiter:", missing_df['Colonne'].tolist())
            
            cols = st.columns(3)
            with cols[0]:
                if st.button("Supprimer les lignes", key="drop_rows"):
                    # Récupérer le DataFrame actuel depuis la session
                    current_df = st.session_state['uploaded_data'].copy()
                    initial_count = len(current_df)
                    df_cleaned = current_df.dropna(subset=[treatment_col])
                    
                    # Mettre à jour le DataFrame dans la session
                    st.session_state['uploaded_data'] = df_cleaned
                    
                    st.success(f"✅ {initial_count - len(df_cleaned)} lignes supprimées")
                    st.rerun()
            
            with cols[1]:
                if st.button("Remplacer par moyenne", key="fill_mean"):
                    # Récupérer le DataFrame actuel depuis la session
                    current_df = st.session_state['uploaded_data'].copy()
                    
                    if current_df[treatment_col].dtype in [np.int64, np.float64]:
                        mean_val = current_df[treatment_col].mean()
                        current_df[treatment_col] = current_df[treatment_col].fillna(mean_val)
                        
                        # Mettre à jour le DataFrame dans la session
                        st.session_state['uploaded_data'] = current_df
                        
                        st.success(f"✅ Valeurs manquantes remplacées par {mean_val:.2f}")
                        st.rerun()
                    else:
                        st.error("Cette colonne n'est pas numérique")
            
            with cols[2]:
                if st.button("Remplacer par mode", key="fill_mode"):
                    # Récupérer le DataFrame actuel depuis la session
                    current_df = st.session_state['uploaded_data'].copy()
                    
                    mode_val = current_df[treatment_col].mode()[0] if not current_df[treatment_col].mode().empty else None
                    if mode_val is not None:
                        current_df[treatment_col] = current_df[treatment_col].fillna(mode_val)
                        
                        # Mettre à jour le DataFrame dans la session
                        st.session_state['uploaded_data'] = current_df
                        
                        st.success(f"✅ Valeurs manquantes remplacées par '{mode_val}'")
                        st.rerun()
                    else:
                        st.error("Impossible de déterminer le mode")
        else:
            st.success("Aucune valeur manquante détectée")
        
        # Détection des anomalies
        st.markdown("#### Détection des anomalies")
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if numeric_cols:
            selected_col = st.selectbox("Colonne numérique pour détection d'anomalies:", numeric_cols)
            
            if selected_col and selected_col in df.columns:
                try:
                    # Calculer les seuils
                    Q1 = df[selected_col].quantile(0.25)
                    Q3 = df[selected_col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    
                    # Identifier les anomalies
                    anomalies = df[(df[selected_col] < lower_bound) | (df[selected_col] > upper_bound)]
                    
                    # Afficher les statistiques
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric("Anomalies détectées", len(anomalies))
                    with cols[1]:
                        percentage = (len(anomalies)/len(df)*100) if len(df) > 0 else 0
                        st.metric("Pourcentage", f"{percentage:.2f}%")
                    with cols[2]:
                        st.metric("Borne inférieure", f"{lower_bound:.2f}")
                    with cols[3]:
                        st.metric("Borne supérieure", f"{upper_bound:.2f}")
                    
                    if len(anomalies) > 0:
                        st.dataframe(anomalies[[selected_col]].head(10), use_container_width=True)
                        
                        # Bouton pour supprimer les anomalies
                        if st.button("Supprimer toutes les anomalies", key=f"remove_anomalies_{selected_col}", type="primary"):
                            # Récupérer le DataFrame actuel depuis la session
                            current_df = st.session_state['uploaded_data'].copy()
                            
                            # Filtrer pour garder seulement les non-anomalies
                            mask = (current_df[selected_col] >= lower_bound) & (current_df[selected_col] <= upper_bound)
                            df_cleaned = current_df[mask].copy()
                            
                            # Mettre à jour le DataFrame dans la session
                            st.session_state['uploaded_data'] = df_cleaned
                            
                            # Afficher un message de confirmation
                            anomalies_removed = len(current_df) - len(df_cleaned)
                            st.success(f"✅ {anomalies_removed} anomalies supprimées avec succès !")
                            st.info(f"Dataset mis à jour : {len(df_cleaned)} lignes restantes.")
                            
                            # Forcer le rechargement immédiat de la page
                            st.rerun()
                    else:
                        st.success("Aucune anomalie détectée dans cette colonne")
                        
                except Exception as e:
                    st.error(f"Erreur dans l'analyse des anomalies: {str(e)}")
        else:
            st.info("Aucune colonne numérique pour la détection d'anomalies")
        
        # Détection des doublons
        st.markdown("#### Détection des doublons")
        duplicate_count = df.duplicated().sum()
            
        if duplicate_count > 0:
            st.warning(f"{duplicate_count} doublons détectés")
            duplicates = df[df.duplicated(keep=False)]
            st.dataframe(duplicates.head(10), use_container_width=True)
                
            if st.button("Supprimer tous les doublons", key="remove_duplicates"):
                # Récupérer le DataFrame actuel depuis la session
                current_df = st.session_state['uploaded_data'].copy()
                
                # Supprimer les doublons
                df_cleaned = current_df.drop_duplicates().copy()
                
                # Mettre à jour le DataFrame dans la session
                st.session_state['uploaded_data'] = df_cleaned
                
                # Message de confirmation
                st.success(f"✅ {len(current_df) - len(df_cleaned)} doublons supprimés avec succès !")
                st.info(f"Dataset mis à jour : {len(df_cleaned)} lignes uniques.")
                
                # Forcer le rechargement
                st.rerun()
        else:
            st.success("Aucun doublon détecté")
    
    with tab3:
        st.markdown("### Export des Données")
        
        # Options d'export
        export_format = st.selectbox(
            "Format d'export :",
            ["CSV", "Excel", "JSON", "Rapport HTML"],
            key="export_format"
        )
        
        # Filtres d'export
        st.markdown("#### Options d'export")
        
        cols = st.columns(2)
        with cols[0]:
            export_all = st.checkbox("Exporter toutes les colonnes", value=True, key="export_all")
            if not export_all:
                selected_columns = st.multiselect(
                    "Sélectionner les colonnes à exporter :",
                    df.columns.tolist(),
                    default=df.columns.tolist()[:5] if len(df.columns) > 5 else df.columns.tolist(),
                    key="export_columns"
                )
            else:
                selected_columns = df.columns.tolist()
        
        with cols[1]:
            sample_size = st.slider(
                "Nombre de lignes à exporter :",
                min_value=1,
                max_value=len(df),
                value=min(1000, len(df)),
                key="export_rows"
            )
        
        # Bouton d'export
        if st.button("Générer l'export", type="primary", use_container_width=True):
            with st.spinner("Génération de l'export en cours..."):
                # Préparer les données
                export_df = df[selected_columns].head(sample_size) if selected_columns else df.head(sample_size)
                
                if export_format == "CSV":
                    csv_data = export_df.to_csv(index=False)
                    st.download_button(
                        label="Télécharger CSV",
                        data=csv_data,
                        file_name=f"export_eda_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                elif export_format == "Excel":
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        export_df.to_excel(writer, sheet_name='Données', index=False)
                        
                        # Ajouter un sheet avec les métadonnées
                        metadata = pd.DataFrame({
                            'Métrique': ['Lignes exportées', 'Colonnes exportées', 'Date export'],
                            'Valeur': [len(export_df), len(export_df.columns), datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                        })
                        metadata.to_excel(writer, sheet_name='Métadonnées', index=False)
                    
                    st.download_button(
                        label="Télécharger Excel",
                        data=buffer.getvalue(),
                        file_name=f"export_eda_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                elif export_format == "JSON":
                    json_data = export_df.to_json(orient='records', indent=2)
                    st.download_button(
                        label="Télécharger JSON",
                        data=json_data,
                        file_name=f"export_eda_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                elif export_format == "Rapport HTML":
                    # Créer un rapport HTML simple
                    html_report = f"""
                    <html>
                    <head>
                        <title>Rapport EDA - {filename}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 40px; }}
                            h1 {{ color: #333; }}
                            .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
                            table {{ width: 100%; border-collapse: collapse; }}
                            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                            th {{ background-color: #4CAF50; color: white; }}
                        </style>
                    </head>
                    <body>
                        <h1>Rapport d'Analyse Exploratoire des Données</h1>
                        <p><strong>Fichier :</strong> {filename}</p>
                        <p><strong>Date d'export :</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        
                        <div class="summary">
                            <h2>Résumé des données</h2>
                            <p><strong>Lignes :</strong> {len(export_df)}</p>
                            <p><strong>Colonnes :</strong> {len(export_df.columns)}</p>
                            <p><strong>Valeurs manquantes :</strong> {export_df.isnull().sum().sum()}</p>
                        </div>
                        
                        <h2>Aperçu des données</h2>
                        {export_df.head(20).to_html(index=False)}
                        
                        <h2>Statistiques descriptives</h2>
                    """
                    
                    # Ajouter les statistiques descriptives pour les colonnes numériques
                    numeric_cols = export_df.select_dtypes(include=[np.number]).columns.tolist()
                    if numeric_cols:
                        desc_stats = export_df[numeric_cols].describe().T
                        html_report += desc_stats.to_html()
                    
                    html_report += """
                    </body>
                    </html>
                    """
                    
                    st.download_button(
                        label="Télécharger Rapport HTML",
                        data=html_report,
                        file_name=f"rapport_eda_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                        mime="text/html",
                        use_container_width=True
                    )
        
        # Rapport statistique
        st.markdown("---")
        st.markdown("#### Générer un rapport statistique")
        
        if st.button("Générer rapport statistique", use_container_width=True):
            with st.spinner("Génération du rapport..."):
                report_content = f"""
                RAPPORT STATISTIQUE - ANALYSE EDA
                =================================
                Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}
                Fichier : {filename}
                Lignes : {len(df)}
                Colonnes : {len(df.columns)}
                
                RÉSUMÉ DES DONNÉES :
                ===================
                """
                
                # Types de données
                report_content += "\nTypes de données par colonne :\n"
                for col in df.columns:
                    report_content += f"- {col}: {df[col].dtype}, Valeurs uniques: {df[col].nunique()}, Manquantes: {df[col].isnull().sum()}\n"
                
                # Valeurs manquantes
                missing_total = df.isnull().sum().sum()
                report_content += f"\nValeurs manquantes totales : {missing_total} ({missing_total/(len(df)*len(df.columns))*100:.1f}%)\n"
                
                # Statistiques descriptives
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    report_content += "\nSTATISTIQUES DESCRIPTIVES :\n"
                    report_content += "===========================\n"
                    for col in numeric_cols[:10]:  # Limiter à 10 colonnes
                        if df[col].notna().sum() > 0:
                            report_content += f"\n{col}:\n"
                            report_content += f"  Moyenne: {df[col].mean():.2f}\n"
                            report_content += f"  Médiane: {df[col].median():.2f}\n"
                            report_content += f"  Écart-type: {df[col].std():.2f}\n"
                            report_content += f"  Min: {df[col].min():.2f}\n"
                            report_content += f"  Max: {df[col].max():.2f}\n"
                
                # Recommandations
                report_content += """
                
                RECOMMANDATIONS :
                ================
                1. Nettoyer les valeurs manquantes avant analyse
                2. Vérifier la cohérence des types de données
                3. Explorer les relations entre variables
                4. Valider les hypothèses statistiques
                """
                
                st.download_button(
                    label="Télécharger Rapport Statistique",
                    data=report_content,
                    file_name=f"rapport_statistique_eda_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
                
def render_sentiment_analysis(user, db):
    """Analyse des sentiments et détection des faux avis"""
    st.subheader("Analyse des Sentiments & Détection des Faux Avis")
    
    # =============================================
    # SECTION EXPLICATION - AJOUTÉE
    # =============================================
    with st.expander("Comment fonctionne l'analyse ?", expanded=True):
        st.markdown("""
        ### Méthodologie d'analyse
        
        **1. Analyse des sentiments :**
        - Utilisation de la bibliothèque **TextBlob** pour l'analyse de texte
        - **Détection automatique de la langue** (anglais requis pour meilleure précision)
        - **Polarité** (-1 à +1) : Négatif ← 0 → Positif
        - **Subjectivité** (0 à 1) : Factuel ← → Subjectif
        - **Classification** :
          - **Positif** : polarité > 0.1
          - **Négatif** : polarité < -0.1
          - **Neutre** : entre -0.1 et 0.1
        
        **2. Détection des faux avis :**
        - **Texte trop court** : < 10 caractères
        - **Subjectivité faible** : < 0.1 (manque d'opinion personnelle)
        - **Répétition excessive** : un mot > 30% du texte
        - **Polarité extrême** avec texte court (si colonne note disponible)
        """)
    
    # =============================================
    # RESTE DU CODE EXISTANT
    # =============================================
    
    # Vérifier si TextBlob est disponible
    if not TEXTBLOB_AVAILABLE:
        st.error("**TextBlob n'est pas installé**")
        st.markdown("""
        Pour utiliser l'analyse des sentiments, installez TextBlob :
        ```
        pip install textblob
        ```
        Et téléchargez les ressources linguistiques :
        ```
        python -m textblob.download_corpora
        ```
        """)
        return
    
    # Vérifier si des données ont été importées
    if 'uploaded_data' not in st.session_state or st.session_state['uploaded_data'] is None:
        st.warning("**Aucune donnée importée**")
        st.markdown("""
        Pour effectuer une analyse des sentiments :
        1. **Importez un fichier CSV ou Excel** contenant des textes à analyser
        2. **Assurez-vous qu'il y a une colonne de texte** (commentaires, avis, etc.)
        3. **Revenez sur cette page** pour analyser les sentiments
        """)
        return
    
    df = st.session_state['uploaded_data']
    filename = st.session_state.get('uploaded_filename', 'Fichier importé')
    
    st.success(f"**Analyse de:** {filename}")
    
    # Sélection de la colonne de texte à analyser
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    
    if not text_cols:
        st.error("**Aucune colonne texte trouvée**")
        st.markdown("""
        Le dataset importé ne contient pas de colonnes texte (type objet).
        Importez un fichier contenant des colonnes de texte (commentaires, avis, descriptions, etc.)
        """)
        return
    
    # =============================================
    # AJOUTER UNE SECTION AVANT LE BOUTON D'ANALYSE
    # =============================================
    st.markdown("### Configuration de l'analyse")
    
    with st.expander("Paramètres techniques", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.info("""
            **Seuils de classification :**
            - Positif : > 0.1
            - Négatif : < -0.1
            - Neutre : -0.1 à 0.1
            """)
        with col2:
            st.info("""
            **Détection faux avis :**
            - Texte < 10 caractères
            - Subjectivité < 0.1
            - Répétition > 30%
            """)
    
    # Configuration de l'analyse
    col1, col2 = st.columns(2)
    
    with col1:
        text_column = st.selectbox(
            "Colonne texte à analyser:",
            text_cols,
            help="Sélectionnez la colonne contenant les textes à analyser"
        )
    
    with col2:
        # Option pour colonne auteur si disponible
        author_cols = [col for col in df.columns if 'auteur' in col.lower() or 'user' in col.lower() or 'name' in col.lower()]
        author_column = st.selectbox(
            "Colonne auteur (optionnel):",
            ['Aucune'] + author_cols,
            help="Sélectionnez la colonne contenant les noms d'auteurs"
        )
    
    # =============================================
    # MODIFIER LA SECTION DU BOUTON D'ANALYSE
    # =============================================
    st.markdown("---")
    st.markdown("### Lancement de l'analyse")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"""
        **Résumé de l'analyse :**
        - **Fichier :** {filename}
        - **Colonne texte :** {text_column}
        - **Textes à analyser :** {len(df[text_column].dropna())}
        - **Méthode :** TextBlob + règles de détection
        """)
    
    with col2:
        if st.button("Lancer l'analyse des sentiments", type="primary", use_container_width=True):
            with st.spinner("Analyse des sentiments en cours..."):
                # Analyser les sentiments
                sentiments = []
                polarities = []
                subjectivities = []
                
                for text in df[text_column].dropna():
                    try:
                        blob = TextBlob(str(text))
                        # Traduction si nécessaire (TextBlob fonctionne mieux en anglais)
                        if detect(str(text)) != 'en':
                            try:
                                translated = blob.translate(to='en')
                                polarity = translated.sentiment.polarity
                                subjectivity = translated.sentiment.subjectivity
                            except:
                                polarity = blob.sentiment.polarity
                                subjectivity = blob.sentiment.subjectivity
                        else:
                            polarity = blob.sentiment.polarity
                            subjectivity = blob.sentiment.subjectivity
                        
                        # Catégoriser le sentiment
                        if polarity > 0.1:
                            sentiment = 'positif'
                        elif polarity < -0.1:
                            sentiment = 'négatif'
                        else:
                            sentiment = 'neutre'
                        
                        sentiments.append(sentiment)
                        polarities.append(polarity)
                        subjectivities.append(subjectivity)
                        
                    except Exception as e:
                        sentiments.append('erreur')
                        polarities.append(0)
                        subjectivities.append(0)
                
                # Ajouter les résultats au DataFrame
                df_analysis = df.copy()
                df_analysis['sentiment'] = sentiments
                df_analysis['polarite'] = polarities
                df_analysis['subjectivite'] = subjectivities
                
                # Détection des faux avis (règles simples)
                df_analysis['faux_avis'] = False
                
                # Règles pour détecter les faux avis
                # 1. Texte trop court
                df_analysis['texte_longueur'] = df_analysis[text_column].astype(str).apply(len)
                df_analysis.loc[df_analysis['texte_longueur'] < 10, 'faux_avis'] = True
                
                # 2. Subjectivité très basse
                df_analysis.loc[df_analysis['subjectivite'] < 0.1, 'faux_avis'] = True
                
                # 3. Polarité extrême (5 étoiles ou 1 étoile systématique)
                if 'note' in df_analysis.columns or 'rating' in df_analysis.columns:
                    rating_col = 'note' if 'note' in df_analysis.columns else 'rating'
                    df_analysis.loc[(df_analysis[rating_col] == 5) & (df_analysis['texte_longueur'] < 20), 'faux_avis'] = True
                    df_analysis.loc[(df_analysis[rating_col] == 1) & (df_analysis['texte_longueur'] < 20), 'faux_avis'] = True
                
                # 4. Répétition excessive de mots
                def check_repetition(text):
                    if isinstance(text, str) and len(text) > 0:
                        words = text.split()
                        if len(words) > 0:
                            word_counts = Counter(words)
                            most_common_count = word_counts.most_common(1)[0][1]
                            return most_common_count / len(words) > 0.3  # Si un mot représente >30% du texte
                    return False
                
                df_analysis['repetition_excessive'] = df_analysis[text_column].apply(check_repetition)
                df_analysis.loc[df_analysis['repetition_excessive'], 'faux_avis'] = True
                
                # Stocker les résultats dans la session
                st.session_state['sentiment_analysis'] = df_analysis
                st.session_state['analysis_complete'] = True
                
                st.success("Analyse terminée!")
    
    # =============================================
    # AJOUTER UNE EXPLICATION AVANT LES RÉSULTATS
    # =============================================
    if 'analysis_complete' in st.session_state and st.session_state['analysis_complete']:
        df_analysis = st.session_state['sentiment_analysis']
        
        st.markdown("---")
        st.markdown("## Résultats de l'analyse")
        
        # Afficher un résumé des méthodes utilisées
        with st.expander("Méthodologie appliquée", expanded=False):
            st.markdown("""
            ### Analyse terminée avec succès !
            
            **Méthodes appliquées :**
            
            1. **Analyse linguistique :**
               - Détection automatique de la langue
               - Traduction en anglais si nécessaire
               - Calcul de polarité et subjectivité
            
            2. **Classification des sentiments :**
               ```python
               if polarite > 0.1: sentiment = 'positif'
               elif polarite < -0.1: sentiment = 'négatif'
               else: sentiment = 'neutre'
               ```
            
            3. **Détection des faux avis :**
               - Texte trop court (10 caractères)
               - Subjectivité faible (0.1)
               - Répétition excessive (30%)
               - Notes extrêmes avec texte court
            
            4. **Métriques calculées :**
               - Distribution des sentiments
               - Taux de faux avis
               - Analyse temporelle
               - Statistiques détaillées
            """)
        
        # Créer des onglets pour les résultats
        tab1, tab2, tab3, tab4 = st.tabs(["Vue d'ensemble", "Visualisations", "Faux Avis", "Détails"])
        
        # Dans chaque onglet, ajouter une petite explication
        with tab1:
            st.markdown("""
            ### Vue d'ensemble des résultats
            
            Cette section présente un résumé statistique de l'analyse :
            - Distribution des sentiments (positif/négatif/neutre)
            - Nombre de faux avis détectés
            - Métriques clés de l'analyse
            """)
            
            # Statistiques des sentiments
            sentiment_counts = df_analysis['sentiment'].value_counts()
            fake_reviews_count = df_analysis['faux_avis'].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Avis positifs", sentiment_counts.get('positif', 0))
            with col2:
                st.metric("Avis négatifs", sentiment_counts.get('négatif', 0))
            with col3:
                st.metric("Avis neutres", sentiment_counts.get('neutre', 0))
            with col4:
                st.metric("Faux avis détectés", fake_reviews_count)
            
            # Distribution des sentiments
            fig1 = px.pie(
                values=sentiment_counts.values,
                names=sentiment_counts.index,
                title="Distribution des sentiments",
                hole=0.4,
                color_discrete_map={
                    'positif': '#36B37E',
                    'négatif': '#FF5630',
                    'neutre': '#FFAB00',
                    'erreur': '#6554C0'
                }
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with tab2:
            st.markdown("""
            ### Visualisations interactives
            
            Graphiques générés à partir des résultats :
            1. **Distribution des polarités** : histogramme des scores
            2. **Nuage de points** : polarité vs subjectivité
            3. **Mots fréquents** : analyse lexicale
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Histogramme des polarités
                fig2 = px.histogram(
                    df_analysis,
                    x='polarite',
                    title="Distribution des polarités",
                    nbins=30,
                    color_discrete_sequence=['#667eea'],
                    labels={'polarite': 'Polarité (-1 à 1)'}
                )
                fig2.add_vline(x=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig2, use_container_width=True)
            
            with col2:
                # Nuage de points polarité vs subjectivité
                fig3 = px.scatter(
                    df_analysis,
                    x='polarite',
                    y='subjectivite',
                    color='sentiment',
                    title="Polarité vs Subjectivité",
                    color_discrete_map={
                        'positif': '#36B37E',
                        'négatif': '#FF5630',
                        'neutre': '#FFAB00'
                    },
                    labels={'polarite': 'Polarité', 'subjectivite': 'Subjectivité'}
                )
                st.plotly_chart(fig3, use_container_width=True)
            
            # Word cloud des mots les plus fréquents (simulé avec bar chart)
            if text_column in df_analysis.columns:
                st.markdown("#### Mots les plus fréquents")
                
                # Extraire les mots les plus fréquents
                all_text = ' '.join(df_analysis[text_column].dropna().astype(str))
                words = re.findall(r'\b\w+\b', all_text.lower())
                word_counts = Counter(words)
                
                # Exclure les mots vides
                stop_words = ['le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'est', 'dans', 'pour', 'avec', 'sur']
                filtered_counts = {word: count for word, count in word_counts.items() 
                                 if word not in stop_words and len(word) > 2}
                
                top_words = dict(sorted(filtered_counts.items(), key=lambda x: x[1], reverse=True)[:20])
                
                fig4 = px.bar(
                    x=list(top_words.keys()),
                    y=list(top_words.values()),
                    title="Mots les plus fréquents (Top 20)",
                    labels={'x': 'Mot', 'y': 'Fréquence'},
                    color=list(top_words.values()),
                    color_continuous_scale='Viridis'
                )
                fig4.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig4, use_container_width=True)
        
        with tab3:
            st.markdown("""
            ### Analyse des faux avis
            
            Cette section identifie les avis suspects selon nos critères :
            - **Texte insuffisant** pour une évaluation valide
            - **Manque de subjectivité** (avis générique)
            - **Répétition suspecte** de mots ou phrases
            - **Notes extrêmes** sans justification
            """)
            
            fake_reviews = df_analysis[df_analysis['faux_avis'] == True]
            
            if len(fake_reviews) > 0:
                st.warning(f"{len(fake_reviews)} faux avis détectés")
                
                # Afficher les faux avis
                display_cols = [text_column, 'sentiment', 'polarite', 'subjectivite']
                if author_column != 'Aucune':
                    display_cols.insert(0, author_column)
                
                st.dataframe(fake_reviews[display_cols].head(20), use_container_width=True)
                
                # Statistiques des faux avis
                col1, col2 = st.columns(2)
                
                with col1:
                    fake_sentiments = fake_reviews['sentiment'].value_counts()
                    fig5 = px.pie(
                        values=fake_sentiments.values,
                        names=fake_sentiments.index,
                        title="Sentiments des faux avis",
                        hole=0.4
                    )
                    st.plotly_chart(fig5, use_container_width=True)
                
                with col2:
                    # Raisons des faux avis
                    reasons = []
                    for idx, row in fake_reviews.iterrows():
                        reason = []
                        if row['texte_longueur'] < 10:
                            reason.append("Texte trop court")
                        if row['subjectivite'] < 0.1:
                            reason.append("Subjectivité faible")
                        if row.get('repetition_excessive', False):
                            reason.append("Répétition excessive")
                        reasons.append(', '.join(reason) if reason else "Autre")
                    
                    reason_counts = Counter(reasons)
                    fig6 = px.bar(
                        x=list(reason_counts.keys()),
                        y=list(reason_counts.values()),
                        title="Raisons des faux avis",
                        labels={'x': 'Raison', 'y': 'Nombre'},
                        color=list(reason_counts.values()),
                        color_continuous_scale='Reds'
                    )
                    fig6.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig6, use_container_width=True)
                
                # Export des faux avis
                st.markdown("#### Export des faux avis")
                csv_fake = fake_reviews.to_csv(index=False)
                st.download_button(
                    label="Télécharger la liste des faux avis (CSV)",
                    data=csv_fake,
                    file_name=f"faux_avis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.success("Aucun faux avis détecté")
        
        with tab4:
            st.markdown("""
            ### Données complètes
            
            Tableau contenant tous les résultats détaillés :
            - Texte original
            - Score de sentiment (polarité)
            - Niveau de subjectivité
            - Classification finale
            - Indicateur de faux avis
            """)
            
            # Tableau complet avec tous les résultats
            display_cols_full = [text_column, 'sentiment', 'polarite', 'subjectivite', 'faux_avis']
            if author_column != 'Aucune':
                display_cols_full.insert(0, author_column)
            
            st.dataframe(df_analysis[display_cols_full].head(50), use_container_width=True)
            
            # Bouton pour exporter tous les résultats
            st.markdown("---")
            csv_all = df_analysis.to_csv(index=False)
            st.download_button(
                label="Télécharger tous les résultats d'analyse (CSV)",
                data=csv_all,
                file_name=f"analyse_sentiments_complete_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # =============================================
        # AJOUTER UNE SECTION CONCLUSION
        # =============================================
        st.markdown("---")
        st.markdown("### Interprétation des résultats")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Pour les sentiments :**
            - **> 0.1** : Opinion positive
            - **-0.1 à 0.1** : Opinion neutre/factuelle
            - **< -0.1** : Opinion négative
            
            **Fiabilité des scores :**
            - Plus la subjectivité est élevée, plus le sentiment est prononcé
            - Les scores proches de 0 indiquent un contenu factuel
            """)
        
        with col2:
            st.markdown("""
            **Pour les faux avis :**
            - **Non définitif** : Ces indicateurs signalent des anomalies
            - **Vérification manuelle** recommandée
            - **Contextuel** : Les règles peuvent être ajustées
            
            **Limitations :**
            - L'analyse automatique a ses limites
            - Le contexte peut influencer l'interprétation
            - Les sarcasmes/ironies sont difficiles à détecter
            """)
        
        # Bouton de ré-analyse avec explication
        st.markdown("---")
        if st.button("Ré-analyser avec différents paramètres", use_container_width=True):
            st.info("""
            Pour modifier l'analyse :
            1. Changer la colonne texte sélectionnée
            2. Ajuster les seuils dans le code
            3. Importer de nouvelles données
            """)
            st.session_state['analysis_complete'] = False
            st.rerun()
    
    else:
        st.info("Cliquez sur 'Lancer l'analyse des sentiments' pour commencer l'analyse")

        
def render_analyst_overview(user, db):
    """Vue d'ensemble pour analystes avec données dynamiques"""
    st.subheader("Vue d'ensemble des données")
    
    # Vérifier si des données ont été importées
    data_available = 'uploaded_data' in st.session_state and st.session_state['uploaded_data'] is not None
    
    if data_available:
        df = st.session_state['uploaded_data']
        filename = st.session_state.get('uploaded_filename', 'Fichier importé')
        
        st.success(f"**Données actives:** {filename}")
        
        # Calculer les métriques dynamiques à partir des données importées
        metrics = {
            'datasets': 1,  # Un seul dataset importé
            'records': len(df),
            'columns': len(df.columns),
            'data_types': len(df.dtypes.unique()),
            'data_distribution': [],
            'avg_records': len(df),
            'avg_columns': len(df.columns),
            'avg_size_kb': st.session_state.get('uploaded_file_size', 0) / 1024 if 'uploaded_file_size' in st.session_state else 0
        }
        
        # Distribution par type de données
        type_counts = df.dtypes.value_counts()
        metrics['data_distribution'] = [(str(dtype), count) for dtype, count in type_counts.items()]
    else:
        # Utiliser les métriques de la base de données si aucune donnée importée
        try:
            metrics = db.get_analyst_metrics()
        except AttributeError:
            st.warning("Les métriques analystes ne sont pas disponibles pour le moment")
            metrics = {
                'datasets': 0,
                'records': 0,
                'columns': 0,
                'data_types': 0,
                'data_distribution': [],
                'avg_records': 0,
                'avg_columns': 0,
                'avg_size_kb': 0
            }
        
        if not data_available:
            st.info("Aucune donnée importée. Importez un fichier depuis la sidebar pour des analyses dynamiques.")
    
    # KPIs - Maintenant 3 colonnes au lieu de 4
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">DATASETS</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{metrics.get("datasets", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #27ae60; font-size: 0.9em;">Total</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">ENREGISTREMENTS</div>', unsafe_allow_html=True)
        total_records = metrics.get('records', 0)
        formatted_records = f"{total_records:,}".replace(",", " ") if total_records >= 1000 else str(total_records)
        st.markdown(f'<div class="kpi-value">{formatted_records}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #3498db; font-size: 0.9em;">Total</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">COLONNES</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{metrics.get("columns", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #9b59b6; font-size: 0.9em;">Total</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Deuxième ligne de KPIs - Maintenant 3 colonnes au lieu de 4
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">ENREG. MOYEN</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{metrics.get("avg_records", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #f39c12; font-size: 0.9em;">Par dataset</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">COLONNES MOY.</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{metrics.get("avg_columns", 0)}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #2ecc71; font-size: 0.9em;">Par dataset</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">TAILLE MOY.</div>', unsafe_allow_html=True)
        avg_size = metrics.get('avg_size_kb', 0)
        size_display = f"{avg_size:.1f} KB" if avg_size > 0 else "0 KB"
        st.markdown(f'<div class="kpi-value">{size_display}</div>', unsafe_allow_html=True)
        st.markdown('<div style="color: #e74c3c; font-size: 0.9em;">Par dataset</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribution par type de données")
        
        if data_available:
            # Utiliser les données importées
            type_counts = df.dtypes.value_counts()
            types = [str(dtype) for dtype in type_counts.index]
            counts = type_counts.values.tolist()
            
            if len(types) > 0:
                fig = px.pie(
                    values=counts,
                    names=types,
                    title="Types de données dans le fichier",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.3
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune information sur les types de données")
        else:
            data_distribution = metrics.get('data_distribution', [])
            
            if data_distribution:
                types = [row[0] for row in data_distribution]
                counts = [row[1] for row in data_distribution]
                
                fig = px.pie(
                    values=counts,
                    names=types,
                    title="",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.3
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée disponible")
    
    with col2:
        st.subheader("Aperçu des données")
        
        if data_available:
            # Afficher un aperçu statistique des données importées
            st.markdown("**Statistiques descriptives:**")
            
            # Sélectionner une colonne numérique pour analyse
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            
            if len(numeric_cols) > 0:
                selected_col = st.selectbox(
                    "Sélectionner une colonne numérique :",
                    numeric_cols,
                    key="overview_numeric_col"
                )
                
                if selected_col:
                    col_data = df[selected_col].dropna()
                    
                    if len(col_data) > 0:
                        # Histogramme
                        fig = px.histogram(
                            df, 
                            x=selected_col,
                            title=f"Distribution de '{selected_col}'",
                            nbins=30,
                            color_discrete_sequence=['#667eea']
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Statistiques
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Moyenne", f"{col_data.mean():.2f}")
                        with col2:
                            st.metric("Médiane", f"{col_data.median():.2f}")
                        with col3:
                            st.metric("Écart-type", f"{col_data.std():.2f}")
                        with col4:
                            st.metric("Valeurs uniques", len(col_data.unique()))
                    else:
                        st.warning(f"La colonne '{selected_col}' ne contient pas de valeurs numériques valides.")
            else:
                st.info("Aucune colonne numérique trouvée dans les données.")
                
            # Aperçu des données
            with st.expander("Aperçu du tableau de données (10 premières lignes)", expanded=False):
                # Afficher les informations sur le tableau
                st.caption(f"Dimensions : {df.shape[0]} lignes × {df.shape[1]} colonnes")
                
                # Afficher un échantillon du tableau
                if len(df.columns) <= 15:  # Si nombre raisonnable de colonnes
                    st.dataframe(
                        df.head(10),
                        use_container_width=True,
                        height=300
                    )
                else:  # Si trop de colonnes, afficher un sous-ensemble
                    st.info(f"Affichage des 10 premières colonnes sur {len(df.columns)}")
                    st.dataframe(
                        df.iloc[:, :10].head(10),
                        use_container_width=True,
                        height=300,
                        column_config={
                            col: st.column_config.Column(
                                width="small" if df[col].dtype == 'object' else "medium",
                                help=f"Type: {df[col].dtype}"
                            )
                            for col in df.columns[:10]
                        }
                    )
                    st.caption(f"... et {len(df.columns) - 10} colonnes supplémentaires")
                
                # Afficher les types de données
                with st.expander("Types de données par colonne", expanded=False):
                    type_info = pd.DataFrame({
                        'Colonne': df.columns,
                        'Type': df.dtypes.astype(str),
                        'Valeurs manquantes': df.isnull().sum().values,
                        'Valeurs uniques': [df[col].nunique() for col in df.columns]
                    })
                    st.dataframe(type_info, use_container_width=True, height=400)
        else:
            upload_activity = metrics.get('upload_activity', [])
            
            if upload_activity:
                dates = [row[0] for row in upload_activity]
                uploads = [row[1] for row in upload_activity]
                records = [row[2] for row in upload_activity]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=dates,
                    y=uploads,
                    name='Uploads',
                    marker_color='#667eea'
                ))
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=records,
                    name='Enregistrements',
                    yaxis='y2',
                    line=dict(color='#36B37E', width=3)
                ))
                
                fig.update_layout(
                    title="Activité d'upload récente",
                    yaxis=dict(title="Nombre d'uploads"),
                    yaxis2=dict(
                        title="Enregistrements (milliers)",
                        overlaying='y',
                        side='right',
                        tickformat=',.0f'
                    ),
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                # Graphique d'exemple
                dates = pd.date_range(end=pd.Timestamp.now(), periods=7, freq='D')
                fig = px.bar(
                    x=dates,
                    y=np.random.randint(1, 10, 7),
                    title="Aucune donnée récente",
                    labels={'x': 'Date', 'y': 'Uploads'}
                )
                st.plotly_chart(fig, use_container_width=True)
                

def render_analyst_analytics_enhanced(user, db):
    """Page analytics pour analystes avec toutes les fonctionnalités"""
    st.subheader("Analytics Avancés")
    
    # Vérifier si des données ont été importées
    if 'uploaded_data' in st.session_state and st.session_state['uploaded_data'] is not None:
        df = st.session_state['uploaded_data']
        filename = st.session_state.get('uploaded_filename', 'Fichier importé')
        
        st.success(f"**Analyse des données:** {filename}")
        
        # Section d'analyse
        st.markdown(f"""
        ### Analyse des données importées
        Sélectionnez un type d'analyse à effectuer sur vos données :
        """)
        
        analysis_type = st.selectbox(
            "Type d'analyse :",
            ["Analyse descriptive", "Analyse de corrélation", "Analyse de tendance", 
             "Clustering", "Régression", "Classification", "Analyse temporelle", "Analyse multivariée"],
            key="analysis_type_select"
        )
        
        if analysis_type:
            st.info(f"**{analysis_type}** - Application de méthodes d'analyse avancées sur vos données.")
            
            # Aperçu des données
            with st.expander("Aperçu des données", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Lignes", df.shape[0])
                with col2:
                    st.metric("Colonnes", df.shape[1])
                with col3:
                    missing_values = df.isnull().sum().sum()
                    st.metric("Valeurs manquantes", missing_values)
                
                st.dataframe(df.head(10), use_container_width=True)
            
            # Statistiques descriptives
            with st.expander("Statistiques descriptives complètes", expanded=False):
                st.dataframe(df.describe(), use_container_width=True)
            
            # Visualisations selon le type d'analyse
            st.subheader("Visualisations et résultats")
            
            if analysis_type == "Analyse descriptive":
                col1, col2 = st.columns(2)
                
                with col1:
                    # Histogramme pour chaque colonne numérique
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    if len(numeric_cols) > 0:
                        selected_col = st.selectbox("Colonne numérique :", numeric_cols, key="hist_col")
                        fig = px.histogram(df, x=selected_col, title=f"Distribution de {selected_col}", nbins=30)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Aucune colonne numérique disponible")
                
                with col2:
                    # Box plot
                    if len(numeric_cols) > 0:
                        selected_col_box = st.selectbox("Colonne pour box plot :", numeric_cols, key="box_col", index=0)
                        fig = px.box(df, y=selected_col_box, title=f"Box plot de {selected_col_box}")
                        st.plotly_chart(fig, use_container_width=True)
            
            elif analysis_type == "Analyse de corrélation":
                # Matrice de corrélation
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if len(numeric_cols) >= 2:
                    corr_matrix = df[numeric_cols].corr()
                    
                    fig = px.imshow(
                        corr_matrix,
                        title="Matrice de corrélation",
                        color_continuous_scale='RdBu',
                        zmin=-1, zmax=1,
                        labels=dict(color="Corrélation")
                    )
                    fig.update_layout(width=600, height=500)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Trouver les corrélations les plus fortes
                    st.markdown("**Corrélations les plus fortes:**")
                    correlations = []
                    for i in range(len(numeric_cols)):
                        for j in range(i+1, len(numeric_cols)):
                            corr = corr_matrix.iloc[i, j]
                            if abs(corr) > 0.5:  # Seuil arbitraire
                                correlations.append((numeric_cols[i], numeric_cols[j], corr))
                    
                    if correlations:
                        for col1, col2, corr in correlations[:5]:  # Limiter à 5
                            st.write(f"- **{col1}** et **{col2}**: {corr:.3f}")
                    else:
                        st.info("Aucune forte corrélation trouvée (|r| > 0.5)")
                else:
                    st.warning("Besoin d'au moins 2 colonnes numériques pour l'analyse de corrélation")
            
            elif analysis_type == "Analyse de tendance":
                # Analyse de tendance temporelle
                date_cols = df.select_dtypes(include=['datetime64', 'datetime']).columns.tolist()
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                
                if date_cols and numeric_cols:
                    col1, col2 = st.columns(2)
                    with col1:
                        date_col = st.selectbox("Colonne date :", date_cols, key="date_col")
                    with col2:
                        value_col = st.selectbox("Colonne valeur :", numeric_cols, key="value_col")
                    
                    if date_col and value_col:
                        # Trier par date
                        df_sorted = df.sort_values(date_col)
                        fig = px.line(df_sorted, x=date_col, y=value_col, title=f"Évolution de {value_col} dans le temps")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Ajouter une ligne de tendance
                        try:
                            # Calculer la tendance linéaire
                            x_numeric = pd.to_numeric(pd.to_datetime(df_sorted[date_col]))
                            y_values = df_sorted[value_col].values
                            
                            # Régression linéaire
                            z = np.polyfit(x_numeric, y_values, 1)
                            p = np.poly1d(z)
                            
                            # Ajouter à la figure
                            fig.add_scatter(x=df_sorted[date_col], y=p(x_numeric), 
                                          mode='lines', name='Tendance linéaire',
                                          line=dict(color='red', dash='dash'))
                            
                            st.plotly_chart(fig, use_container_width=True)
                        except:
                            pass
                else:
                    st.info("Besoin d'au moins une colonne date et une colonne numérique pour l'analyse de tendance")
            
            elif analysis_type == "Clustering":
                # Clustering simple (K-means)
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if len(numeric_cols) >= 2:
                    col1, col2 = st.columns(2)
                    with col1:
                        x_col = st.selectbox("Axe X :", numeric_cols, key="cluster_x")
                    with col2:
                        y_col = st.selectbox("Axe Y :", numeric_cols, 
                                           index=1 if len(numeric_cols) > 1 else 0, 
                                           key="cluster_y")
                    
                    n_clusters = st.slider("Nombre de clusters :", 2, 10, 3, key="n_clusters")
                    
                    # Appliquer K-means
                    from sklearn.cluster import KMeans
                    from sklearn.preprocessing import StandardScaler
                    
                    data_for_clustering = df[[x_col, y_col]].dropna()
                    
                    if len(data_for_clustering) > n_clusters:
                        # Standardiser les données
                        scaler = StandardScaler()
                        scaled_data = scaler.fit_transform(data_for_clustering)
                        
                        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                        clusters = kmeans.fit_predict(scaled_data)
                        
                        data_for_clustering['cluster'] = clusters
                        
                        fig = px.scatter(data_for_clustering, x=x_col, y=y_col, 
                                       color='cluster', title=f"Clustering K-means (k={n_clusters})",
                                       color_continuous_scale=px.colors.qualitative.Set3)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Analyse des clusters
                        st.markdown("**Caractéristiques des clusters:**")
                        cluster_stats = data_for_clustering.groupby('cluster').agg({
                            x_col: ['mean', 'std', 'count'],
                            y_col: ['mean', 'std']
                        }).round(2)
                        
                        st.dataframe(cluster_stats, use_container_width=True)
                    else:
                        st.warning("Pas assez de données pour le clustering")
                else:
                    st.info("Besoin d'au moins 2 colonnes numériques pour le clustering")
            
            elif analysis_type == "Régression":
                # Analyse de régression
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if len(numeric_cols) >= 2:
                    col1, col2 = st.columns(2)
                    with col1:
                        x_col = st.selectbox("Variable indépendante (X) :", numeric_cols, key="reg_x")
                    with col2:
                        y_col = st.selectbox("Variable dépendante (Y) :", numeric_cols, 
                                           index=1 if len(numeric_cols) > 1 else 0, 
                                           key="reg_y")
                    
                    if x_col and y_col:
                        # Régression linéaire
                        from sklearn.linear_model import LinearRegression
                        from sklearn.metrics import mean_squared_error, r2_score
                        
                        data_reg = df[[x_col, y_col]].dropna()
                        
                        if len(data_reg) > 10:
                            X = data_reg[[x_col]].values
                            y = data_reg[y_col].values
                            
                            model = LinearRegression()
                            model.fit(X, y)
                            
                            y_pred = model.predict(X)
                            
                            # Graphique de régression
                            fig = px.scatter(data_reg, x=x_col, y=y_col, 
                                           title=f"Régression linéaire: {y_col} vs {x_col}")
                            
                            # Ajouter la ligne de régression
                            x_range = np.linspace(X.min(), X.max(), 100).reshape(-1, 1)
                            y_range = model.predict(x_range)
                            
                            fig.add_scatter(x=x_range.flatten(), y=y_range, 
                                          mode='lines', name='Régression',
                                          line=dict(color='red', width=3))
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Métriques
                            mse = mean_squared_error(y, y_pred)
                            r2 = r2_score(y, y_pred)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Coefficient R²", f"{r2:.3f}")
                            with col2:
                                st.metric("MSE", f"{mse:.3f}")
                            with col3:
                                st.metric("Pente", f"{model.coef_[0]:.3f}")
                            
                            # Équation de la régression
                            st.info(f"Équation: {y_col} = {model.coef_[0]:.3f} × {x_col} + {model.intercept_:.3f}")
                        else:
                            st.warning("Pas assez de données pour la régression (min 10)")
                else:
                    st.info("Besoin d'au moins 2 colonnes numériques pour la régression")
            
            elif analysis_type == "Classification":
                # Analyse de classification avec matrice de confusion
                st.markdown("### Analyse de Classification")
                
                # Sélection des colonnes
                all_cols = df.columns.tolist()
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                
                if len(numeric_cols) >= 2 and len(all_cols) >= 3:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Sélectionner la variable cible (doit être catégorielle ou binaire)
                        target_col = st.selectbox("Variable cible :", all_cols, key="class_target")
                    
                    with col2:
                        # Sélectionner les features
                        feature_options = [col for col in numeric_cols if col != target_col]
                        feature_cols = st.multiselect("Variables prédictives :", 
                                                     feature_options,
                                                     default=feature_options[:2] if len(feature_options) >= 2 else feature_options,
                                                     key="class_features")
                    
                    with col3:
                        model_type = st.selectbox("Modèle :", 
                                                ["Arbre de décision", "Random Forest", "Régression logistique"],
                                                key="class_model")
                    
                    if target_col and feature_cols and len(feature_cols) >= 1:
                        # Préparation des données
                        from sklearn.model_selection import train_test_split
                        from sklearn.preprocessing import LabelEncoder, StandardScaler
                        
                        # Préparer les données
                        classification_data = df[[target_col] + feature_cols].dropna()
                        
                        if len(classification_data) > 20:
                            # Encoder la variable cible si nécessaire
                            if classification_data[target_col].dtype == 'object':
                                le = LabelEncoder()
                                y = le.fit_transform(classification_data[target_col])
                                class_names = le.classes_
                            else:
                                y = classification_data[target_col].values
                                # Convertir en classification binaire si numérique
                                if len(np.unique(y)) > 10:
                                    median_val = np.median(y)
                                    y = (y > median_val).astype(int)
                                    class_names = ['Classe 0', 'Classe 1']
                                else:
                                    class_names = np.unique(y)
                            
                            X = classification_data[feature_cols].values
                            
                            # Standardiser les features
                            scaler = StandardScaler()
                            X_scaled = scaler.fit_transform(X)
                            
                            # Split train/test
                            X_train, X_test, y_train, y_test = train_test_split(
                                X_scaled, y, test_size=0.3, random_state=42
                            )
                            
                            # Entraîner le modèle
                            if model_type == "Arbre de décision":
                                from sklearn.tree import DecisionTreeClassifier
                                model = DecisionTreeClassifier(max_depth=5, random_state=42)
                            elif model_type == "Random Forest":
                                from sklearn.ensemble import RandomForestClassifier
                                model = RandomForestClassifier(n_estimators=100, random_state=42)
                            else:  # Régression logistique
                                from sklearn.linear_model import LogisticRegression
                                model = LogisticRegression(random_state=42)
                            
                            model.fit(X_train, y_train)
                            y_pred = model.predict(X_test)
                            
                            # Évaluation
                            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
                            from sklearn.metrics import confusion_matrix, classification_report
                            
                            accuracy = accuracy_score(y_test, y_pred)
                            precision = precision_score(y_test, y_pred, average='weighted')
                            recall = recall_score(y_test, y_pred, average='weighted')
                            f1 = f1_score(y_test, y_pred, average='weighted')
                            
                            # Afficher les métriques
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Accuracy", f"{accuracy:.3f}")
                            with col2:
                                st.metric("Precision", f"{precision:.3f}")
                            with col3:
                                st.metric("Recall", f"{recall:.3f}")
                            with col4:
                                st.metric("F1-Score", f"{f1:.3f}")
                            
                            # MATRICE DE CONFUSION
                            st.markdown("### Matrice de Confusion")
                            
                            cm = confusion_matrix(y_test, y_pred)
                            
                            # Créer la visualisation de la matrice de confusion
                            fig_cm = px.imshow(
                                cm,
                                text_auto=True,
                                color_continuous_scale='Blues',
                                labels=dict(x="Prédit", y="Réel", color="Nombre"),
                                x=class_names,
                                y=class_names,
                                title="Matrice de Confusion"
                            )
                            fig_cm.update_layout(width=600, height=500)
                            st.plotly_chart(fig_cm, use_container_width=True)
                            
                            # Rapport de classification
                            st.markdown("### Rapport de Classification")
                            report = classification_report(y_test, y_pred, target_names=[str(c) for c in class_names])
                            st.text(report)
                            
                            # Importance des features (si disponible)
                            if hasattr(model, 'feature_importances_'):
                                st.markdown("### Importance des Variables")
                                importance_df = pd.DataFrame({
                                    'Variable': feature_cols,
                                    'Importance': model.feature_importances_
                                }).sort_values('Importance', ascending=False)
                                
                                fig_importance = px.bar(importance_df, x='Variable', y='Importance',
                                                       title="Importance des variables")
                                st.plotly_chart(fig_importance, use_container_width=True)
                            
                        else:
                            st.warning("Pas assez de données pour la classification (min 20)")
                    else:
                        st.warning("Sélectionnez au moins une variable prédictive")
                else:
                    st.info("Besoin d'au moins 3 colonnes dont 2 numériques pour la classification")
            
            elif analysis_type == "Analyse temporelle":
                # Analyse temporelle avancée
                date_cols = df.select_dtypes(include=['datetime64', 'datetime']).columns.tolist()
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                
                if date_cols and numeric_cols:
                    col1, col2 = st.columns(2)
                    with col1:
                        date_col = st.selectbox("Colonne date :", date_cols, key="time_date")
                    with col2:
                        value_col = st.selectbox("Colonne valeur :", numeric_cols, key="time_value")
                    
                    if date_col and value_col:
                        # Préparer les données
                        time_data = df[[date_col, value_col]].copy()
                        time_data = time_data.sort_values(date_col)
                        time_data = time_data.dropna()
                        
                        # Analyse de saisonnalité
                        st.markdown("### Analyse de Saisonnalité")
                        
                        # Extraire les composantes temporelles
                        time_data['month'] = time_data[date_col].dt.month
                        time_data['year'] = time_data[date_col].dt.year
                        
                        # Moyenne par mois
                        monthly_avg = time_data.groupby('month')[value_col].mean().reset_index()
                        
                        fig_seasonal = px.line(monthly_avg, x='month', y=value_col,
                                              title=f"Saisonnalité de {value_col} par mois",
                                              markers=True)
                        st.plotly_chart(fig_seasonal, use_container_width=True)
                        
                        # Série temporelle avec moyenne mobile
                        st.markdown("### Série temporelle avec moyenne mobile")
                        
                        # Calculer la moyenne mobile
                        window_size = st.slider("Taille de la fenêtre (moyenne mobile) :", 3, 30, 7)
                        time_data['moving_avg'] = time_data[value_col].rolling(window=window_size).mean()
                        
                        fig_ts = px.line(time_data, x=date_col, y=value_col,
                                        title=f"Série temporelle de {value_col}")
                        fig_ts.add_scatter(x=time_data[date_col], y=time_data['moving_avg'],
                                         mode='lines', name=f'Moyenne mobile ({window_size}j)',
                                         line=dict(color='red', width=2))
                        
                        st.plotly_chart(fig_ts, use_container_width=True)
                        
                        # Analyse de croissance
                        if len(time_data) > 10:
                            time_data['growth'] = time_data[value_col].pct_change() * 100
                            
                            fig_growth = px.line(time_data, x=date_col, y='growth',
                                               title=f"Taux de croissance de {value_col} (%)",
                                               labels={'growth': 'Croissance (%)'})
                            fig_growth.add_hline(y=0, line_dash="dash", line_color="gray")
                            
                            st.plotly_chart(fig_growth, use_container_width=True)
                else:
                    st.info("Besoin d'au moins une colonne date et une colonne numérique")
            
            elif analysis_type == "Analyse multivariée":
                # Analyse multivariée
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                
                if len(numeric_cols) >= 3:
                    selected_cols = st.multiselect("Sélectionnez 3-5 variables numériques :",
                                                  numeric_cols,
                                                  default=numeric_cols[:3] if len(numeric_cols) >= 3 else numeric_cols,
                                                  max_marks=5)
                    
                    if len(selected_cols) >= 3:
                        # Matrice de scatter plot
                        st.markdown("### Matrice de Scatter Plots")
                        
                        scatter_matrix = pd.plotting.scatter_matrix(df[selected_cols], figsize=(12, 8))
                        st.pyplot()
                        
                        # Heatmap de corrélation
                        st.markdown("### Heatmap de Corrélation Multivariée")
                        
                        corr_matrix = df[selected_cols].corr()
                        
                        fig = px.imshow(corr_matrix,
                                       text_auto=True,
                                       color_continuous_scale='RdBu',
                                       zmin=-1, zmax=1,
                                       title="Matrice de corrélation")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Analyse en composantes principales (PCA)
                        st.markdown("### Analyse en Composantes Principales (PCA)")
                        
                        from sklearn.decomposition import PCA
                        from sklearn.preprocessing import StandardScaler
                        
                        # Standardiser les données
                        scaler = StandardScaler()
                        scaled_data = scaler.fit_transform(df[selected_cols].dropna())
                        
                        # Appliquer PCA
                        pca = PCA(n_components=2)
                        principal_components = pca.fit_transform(scaled_data)
                        
                        pca_df = pd.DataFrame(data=principal_components,
                                             columns=['PC1', 'PC2'])
                        
                        # Visualiser les composantes principales
                        fig_pca = px.scatter(pca_df, x='PC1', y='PC2',
                                           title="Projection PCA (2 composantes)")
                        
                        # Ajouter les pourcentages de variance expliquée
                        var_exp = pca.explained_variance_ratio_
                        fig_pca.update_layout(
                            xaxis_title=f"PC1 ({var_exp[0]*100:.1f}% variance)",
                            yaxis_title=f"PC2 ({var_exp[1]*100:.1f}% variance)"
                        )
                        
                        st.plotly_chart(fig_pca, use_container_width=True)
                        
                        # Variance expliquée par composante
                        st.markdown("**Variance expliquée par composante:**")
                        for i, var in enumerate(var_exp, 1):
                            st.write(f"- Composante {i}: {var*100:.1f}%")
                        
                        st.write(f"- **Variance totale expliquée:** {sum(var_exp)*100:.1f}%")
                        
                        # Contribution des variables originales
                        st.markdown("**Contribution des variables aux composantes principales:**")
                        loadings = pd.DataFrame(
                            pca.components_.T,
                            columns=['PC1', 'PC2'],
                            index=selected_cols
                        )
                        
                        st.dataframe(loadings.round(3), use_container_width=True)
                        
                    else:
                        st.warning("Sélectionnez au moins 3 variables pour l'analyse multivariée")
                else:
                    st.info("Besoin d'au moins 3 colonnes numériques pour l'analyse multivariée")
            
            # Bouton d'export des résultats
            st.markdown("---")
            if st.button("Exporter les résultats d'analyse", use_container_width=True):
                # Créer un rapport d'analyse
                report_content = f"""
                RAPPORT D'ANALYSE - AIM Analytics Platform
                ============================================
                Type d'analyse: {analysis_type}
                Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}
                Fichier analysé: {filename}
                Analyste: {user.get('full_name', user.get('username', 'N/A'))}
                
                DONNÉES ANALYSÉES:
                - Lignes: {df.shape[0]}
                - Colonnes: {df.shape[1]}
                - Valeurs manquantes: {df.isnull().sum().sum()}
                
                RÉSULTATS:
                """
                
                # Ajouter des résultats spécifiques selon le type d'analyse
                if analysis_type == "Analyse descriptive":
                    report_content += "\nStatistiques descriptives:\n"
                    report_content += df.describe().to_string()
                
                elif analysis_type == "Analyse de corrélation":
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    if len(numeric_cols) >= 2:
                        corr_matrix = df[numeric_cols].corr()
                        report_content += "\nMatrice de corrélation:\n"
                        report_content += corr_matrix.to_string()
                
                st.download_button(
                    label="Télécharger le rapport",
                    data=report_content,
                    file_name=f"rapport_analyse_{analysis_type.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
                
    else:
        # Si aucune donnée n'a été importée
        st.warning("**Aucune donnée importée**")
        st.markdown("""
        Pour utiliser les fonctionnalités d'analyse avancée :
        1. **Importez un fichier CSV ou Excel** depuis la sidebar à gauche
        2. **Attendez que les données soient chargées**
        3. **Revenez sur cette page** pour analyser vos données
        
        Les données importées seront disponibles dans toutes les sections du dashboard.
        """)
        
        # Bouton pour rediriger vers la sidebar
        if st.button("Aller à l'import de données", type="primary"):
            st.info("Utilisez la sidebar à gauche pour importer des données")

def render_ml_models(user, db):
    """Page dédiée aux modèles de machine learning"""
    st.subheader("Modèles de Machine Learning")
    
    if 'uploaded_data' not in st.session_state:
        st.warning("Importez d'abord vos données pour utiliser les modèles ML")
        return
    
    df = st.session_state['uploaded_data']
    
    st.markdown("""
    ### Modèles de Machine Learning Avancés
    
    Cette section vous permet d'entraîner et d'évaluer différents modèles de machine learning
    sur vos données. Choisissez un type de modèle et configurez les paramètres.
    """)
    
    model_type = st.selectbox(
        "Type de modèle :",
        ["Classification", "Régression", "Clustering", "Réduction de dimension", "Ensemble Learning"],
        key="ml_model_type"
    )
    
    if model_type == "Classification":
        render_classification_models(user, df)
    elif model_type == "Régression":
        render_regression_models(user, df)
    elif model_type == "Clustering":
        render_clustering_models(user, df)
    elif model_type == "Réduction de dimension":
        render_dimensionality_reduction(user, df)
    elif model_type == "Ensemble Learning":
        render_ensemble_models(user, df)

def render_classification_models(user, df):
    """Modèles de classification avancés"""
    st.markdown("### Modèles de Classification")
    
    # Sélection des données
    all_cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) < 2 or len(all_cols) < 3:
        st.warning("Besoin d'au moins 3 colonnes dont 2 numériques pour la classification")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_col = st.selectbox("Variable cible :", all_cols, key="ml_class_target")
    
    with col2:
        feature_options = [col for col in numeric_cols if col != target_col]
        feature_cols = st.multiselect("Variables prédictives :", 
                                     feature_options,
                                     default=feature_options[:3] if len(feature_options) >= 3 else feature_options,
                                     key="ml_class_features")
    
    if not target_col or not feature_cols:
        return
    
    # Préparation des données
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    
    data = df[[target_col] + feature_cols].dropna()
    
    if len(data) < 20:
        st.warning("Pas assez de données (minimum 20 observations)")
        return
    
    # Encoder la cible
    if data[target_col].dtype == 'object':
        le = LabelEncoder()
        y = le.fit_transform(data[target_col])
        class_names = le.classes_
    else:
        y = data[target_col].values
        if len(np.unique(y)) > 10:
            median_val = np.median(y)
            y = (y > median_val).astype(int)
            class_names = ['Classe 0', 'Classe 1']
        else:
            class_names = np.unique(y)
    
    X = data[feature_cols].values
    
    # Standardiser
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)
    
    # Sélection du modèle
    model_choice = st.selectbox(
        "Choix du modèle :",
        ["Random Forest", "SVM", "K-NN", "Régression Logistique", "Naive Bayes", "XGBoost"],
        key="class_model_choice"
    )
    
    # Configuration des paramètres
    if model_choice == "Random Forest":
        n_estimators = st.slider("Nombre d'arbres :", 10, 200, 100)
        max_depth = st.slider("Profondeur max :", 2, 20, 10)
        
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
    
    elif model_choice == "SVM":
        C = st.slider("Paramètre C :", 0.1, 10.0, 1.0)
        kernel = st.selectbox("Noyau :", ['linear', 'rbf', 'poly'], key="svm_kernel")
        
        from sklearn.svm import SVC
        model = SVC(C=C, kernel=kernel, random_state=42, probability=True)
    
    elif model_choice == "K-NN":
        n_neighbors = st.slider("Nombre de voisins :", 3, 20, 5)
        
        from sklearn.neighbors import KNeighborsClassifier
        model = KNeighborsClassifier(n_neighbors=n_neighbors)
    
    elif model_choice == "Régression Logistique":
        C = st.slider("Régularisation C :", 0.01, 10.0, 1.0)
        
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(C=C, random_state=42, max_iter=1000)
    
    elif model_choice == "Naive Bayes":
        from sklearn.naive_bayes import GaussianNB
        model = GaussianNB()
    
    elif model_choice == "XGBoost":
        try:
            from xgboost import XGBClassifier
            n_estimators = st.slider("Nombre d'arbres :", 50, 500, 100)
            max_depth = st.slider("Profondeur max :", 3, 15, 6)
            
            model = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        except:
            st.warning("XGBoost n'est pas installé. Utilisation de Random Forest à la place.")
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(random_state=42)
    
    # Entraînement
    if st.button("Entraîner le modèle", type="primary"):
        with st.spinner("Entraînement en cours..."):
            model.fit(X_train, y_train)
            
            # Prédictions
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
            
            # Évaluation
            from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                                       f1_score, confusion_matrix, classification_report,
                                       roc_curve, auc, precision_recall_curve)
            
            # Métriques de base
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted')
            recall = recall_score(y_test, y_pred, average='weighted')
            f1 = f1_score(y_test, y_pred, average='weighted')
            
            # Afficher les métriques
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Accuracy", f"{accuracy:.3f}")
            with col2:
                st.metric("Precision", f"{precision:.3f}")
            with col3:
                st.metric("Recall", f"{recall:.3f}")
            with col4:
                st.metric("F1-Score", f"{f1:.3f}")
            
            # Matrice de confusion
            st.markdown("### Matrice de Confusion")
            cm = confusion_matrix(y_test, y_pred)
            
            fig_cm = px.imshow(
                cm,
                text_auto=True,
                color_continuous_scale='Blues',
                labels=dict(x="Prédit", y="Réel", color="Nombre"),
                x=[str(c) for c in class_names],
                y=[str(c) for c in class_names],
                title=f"Matrice de Confusion - {model_choice}"
            )
            st.plotly_chart(fig_cm, use_container_width=True)
            
            # Courbe ROC (pour classification binaire)
            if len(class_names) == 2 and y_prob is not None:
                st.markdown("### Courbe ROC")
                
                fpr, tpr, _ = roc_curve(y_test, y_prob[:, 1])
                roc_auc = auc(fpr, tpr)
                
                fig_roc = go.Figure()
                fig_roc.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines',
                                           name=f'ROC curve (AUC = {roc_auc:.3f})',
                                           line=dict(color='blue', width=2)))
                fig_roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines',
                                           name='Random', line=dict(color='red', dash='dash')))
                
                fig_roc.update_layout(
                    title=f'Courbe ROC - {model_choice}',
                    xaxis_title='False Positive Rate',
                    yaxis_title='True Positive Rate',
                    width=600, height=500
                )
                st.plotly_chart(fig_roc, use_container_width=True)
            
            # Rapport de classification
            st.markdown("### Rapport de Classification")
            report = classification_report(y_test, y_pred, target_names=[str(c) for c in class_names])
            st.text(report)
            
            # Importance des features
            if hasattr(model, 'feature_importances_'):
                st.markdown("### Importance des Variables")
                
                importance_df = pd.DataFrame({
                    'Variable': feature_cols,
                    'Importance': model.feature_importances_
                }).sort_values('Importance', ascending=False)
                
                fig_imp = px.bar(importance_df.head(10), x='Variable', y='Importance',
                               title="Top 10 des variables les plus importantes")
                st.plotly_chart(fig_imp, use_container_width=True)
            

def render_reports(user, db):
    """Génération de rapports (Section désactivée)"""
    st.subheader("Génération de Rapports")
    
    st.info("""
    **Cette section est actuellement en développement**
    
    La fonctionnalité de génération de rapports automatisés sera disponible prochainement.
    En attendant, vous pouvez :
    
    1. **Exporter vos données** depuis les sections EDA ou Analyse des Sentiments
    2. **Utiliser les visualisations** pour créer vos propres rapports
    3. **Contacter l'administrateur** pour des besoins spécifiques
    
    Les rapports automatisés incluront :
    - Rapports d'analyse complète
    - Dashboards exportables
    - Rapports périodiques automatisés
    """)
    
    # Option alternative simple
    st.markdown("---")
    st.markdown("### Créer un rapport simple")
    
    report_title = st.text_input("Titre du rapport:", "Rapport d'analyse")
    include_sections = st.multiselect(
        "Sections à inclure:",
        ["Aperçu des données", "Statistiques descriptives", "Visualisations", "Recommandations"],
        default=["Aperçu des données", "Statistiques descriptives"]
    )
    
    if st.button("Générer le rapport simple", use_container_width=True):
        # Rapport simple basé sur les données importées
        report_content = f"""
        ==========================================
        {report_title}
        Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        Généré par: {user.get('full_name', user.get('username', 'Utilisateur'))}
        ==========================================
        
        """
        
        if 'uploaded_data' in st.session_state and st.session_state['uploaded_data'] is not None:
            df = st.session_state['uploaded_data']
            filename = st.session_state.get('uploaded_filename', 'Fichier inconnu')
            
            report_content += f"""
            DONNÉES ANALYSÉES:
            - Fichier: {filename}
            - Lignes: {len(df)}
            - Colonnes: {len(df.columns)}
            
            """
        
        if "Aperçu des données" in include_sections and 'uploaded_data' in st.session_state:
            df = st.session_state['uploaded_data']
            report_content += """
            APERÇU DES DONNÉES:
            """
            report_content += df.head().to_string()
            report_content += "\n\n"
        
        if "Statistiques descriptives" in include_sections and 'uploaded_data' in st.session_state:
            df = st.session_state['uploaded_data']
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                report_content += """
                STATISTIQUES DESCRIPTIVES:
                """
                report_content += df[numeric_cols].describe().to_string()
                report_content += "\n\n"
        
        if "Recommandations" in include_sections:
            report_content += """
            RECOMMANDATIONS:
            1. Vérifier la qualité des données avant analyse
            2. Considérer les éventuelles valeurs manquantes
            3. Valider les hypothèses statistiques
            4. Documenter toutes les étapes d'analyse
            """
        
        st.download_button(
            label="Télécharger le rapport",
            data=report_content,
            file_name=f"{report_title.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            use_container_width=True
        )
            
# =============================
#   DASHBOARD MARKETING
# =============================

def dashboard_marketing(user, db):
    """Dashboard avancé pour le responsable marketing avec IA"""
    apply_custom_css()
    
    user_full_name = user.get('full_name', user.get('username', 'Responsable Marketing'))
    user_role = user.get('role', 'marketing')
    
    # En-tête principal avec explication AIM
    st.markdown(f"""
    <div class="main-header">
        <h1 style="margin-bottom: 0.5rem; font-size: 2.4em;">AIM Marketing Intelligence</h1>
        <p style="opacity: 0.95; font-size: 1.1em; background: rgba(255,255,255,0.7); padding: 15px; border-radius: 10px; border-left: 4px solid #8B5CF6;">
            <strong>Mission :</strong> Plateforme d'intelligence marketing alimentée par l'IA pour optimiser vos campagnes, 
            analyser les sentiments clients, détecter les faux avis et générer des recommandations stratégiques personnalisées.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        # En-tête sidebar
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 3])
        with col1:
            initials = user_full_name[0].upper() if user_full_name else 'M'
            st.markdown(f'<div style="width: 50px; height: 50px; background: linear-gradient(135deg, #8B5CF6, #EC4899); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5em; font-weight: bold;">{initials}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"**{user_full_name}**")
            st.markdown(f"<span class='role-badge role-marketing'>Responsable Marketing</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # IMPORT DES DONNÉES MARKETING
        st.markdown("### Import des données")
        
        marketing_file = st.file_uploader(
            "Importer vos données marketing (CSV/Excel)",
            type=['csv', 'xlsx', 'xls'],
            key="marketing_data_upload",
            help="Importez vos données clients, campagnes, avis, etc."
        )
        
        if marketing_file is not None:
            try:
                if marketing_file.name.endswith('.csv'):
                    marketing_df = pd.read_csv(marketing_file)
                else:
                    marketing_df = pd.read_excel(marketing_file)
                
                # Stocker les données
                st.session_state['marketing_data'] = marketing_df
                st.session_state['marketing_filename'] = marketing_file.name
                st.session_state['marketing_file_size'] = len(marketing_file.getvalue())
                
                st.success(f"{marketing_file.name} importé!")
                st.info(f"{marketing_df.shape[0]} lignes × {marketing_df.shape[1]} colonnes")
                
                db.log_activity(user['id'], "data_upload", f"Import marketing: {marketing_file.name}")
                
            except Exception as e:
                st.error(f"Erreur d'import: {str(e)}")
        
        # Navigation MAJ - AJOUT DE "PROFIL"
        st.markdown("---")
        pages = ["Vue d'ensemble", "Analyse Sentiments", "Détection Faux Avis", "IA & Recommandations", "Profil"]
        selected_page = st.radio(
            "Navigation",
            pages,
            label_visibility="collapsed",
            key="marketing_nav_advanced"
        )
        
        st.markdown("---")
        
        # Bouton déconnexion uniquement
        if st.button("Déconnexion", use_container_width=True, type="primary"):
            db.log_activity(user['id'], "logout", "Déconnexion marketing")
            st.session_state.clear()
            st.rerun()
    
    # Contenu principal - TOUTES LES PAGES DOIVENT ÊTRE DÉFINIES
    if selected_page == "Vue d'ensemble":
        render_marketing_overview_existing(user, db)
    elif selected_page == "Analyse Sentiments":
        render_sentiment_analysis_marketing(user, db)
    elif selected_page == "Détection Faux Avis":
        render_fake_reviews_detection_marketing(user, db)
    elif selected_page == "IA & Recommandations":
        render_marketing_ai_recommendations(user, db) 
    elif selected_page == "Profil":
        render_user_profile_enhanced(user, db) 

# =============================
#   FONCTIONS MARKETING EXISTANTES (AVEC KPIs DYNAMIQUES)
# =============================

def render_marketing_overview_existing(user, db):
    """Vue d'ensemble marketing EXISTANTE avec KPIs dynamiques"""
    st.subheader("Vue d'ensemble Marketing")
    
    # Vérifier si des données ont été importées
    data_available = 'marketing_data' in st.session_state and st.session_state['marketing_data'] is not None
    
    if data_available:
        df = st.session_state['marketing_data']
        filename = st.session_state.get('marketing_filename', 'Fichier importé')
        
        st.success(f"Données actives: {filename}")
        
        # Calculer les métriques dynamiques à partir des données importées
        total_rows = len(df)
        total_columns = len(df.columns)
        
        # Identifier les colonnes marketing communes
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Chercher des colonnes spécifiques marketing
        impression_cols = [col for col in df.columns if 'impression' in col.lower()]
        click_cols = [col for col in df.columns if 'clic' in col.lower() or 'click' in col.lower()]
        conversion_cols = [col for col in df.columns if 'conversion' in col.lower()]
        spend_cols = [col for col in df.columns if 'dépense' in col.lower() or 'spend' in col.lower() or 'cost' in col.lower()]
        revenue_cols = [col for col in df.columns if 'revenu' in col.lower() or 'revenue' in col.lower()]
        campaign_cols = [col for col in df.columns if 'campagne' in col.lower() or 'campaign' in col.lower()]
        
        # Calculer les métriques si les colonnes existent
        metrics = {
            'total_campaigns': df[campaign_cols[0]].nunique() if campaign_cols else 0,
            'total_rows': total_rows,
            'total_columns': total_columns,
            'numeric_columns': len(numeric_cols)
        }
        
        if impression_cols:
            metrics['total_impressions'] = df[impression_cols[0]].sum()
        if click_cols:
            metrics['total_clicks'] = df[click_cols[0]].sum()
        if conversion_cols:
            metrics['total_conversions'] = df[conversion_cols[0]].sum()
        if spend_cols:
            metrics['total_spend'] = df[spend_cols[0]].sum()
        if revenue_cols:
            metrics['total_revenue'] = df[revenue_cols[0]].sum()
        
        # Calculer les taux si possible
        if 'total_impressions' in metrics and 'total_clicks' in metrics and metrics['total_impressions'] > 0:
            metrics['ctr'] = (metrics['total_clicks'] / metrics['total_impressions']) * 100
        
        if 'total_clicks' in metrics and 'total_conversions' in metrics and metrics['total_clicks'] > 0:
            metrics['conversion_rate'] = (metrics['total_conversions'] / metrics['total_clicks']) * 100
        
        if 'total_spend' in metrics and 'total_revenue' in metrics and metrics['total_spend'] > 0:
            metrics['roi'] = ((metrics['total_revenue'] - metrics['total_spend']) / metrics['total_spend']) * 100
        
    else:
        # Utiliser les métriques de la base de données si aucune donnée importée
        try:
            metrics = db.get_marketing_metrics()
        except AttributeError:
            st.warning("Les métriques marketing ne sont pas disponibles pour le moment")
            metrics = {
                'total_campaigns': 0,
                'total_rows': 0,
                'total_columns': 0,
                'numeric_columns': 0
            }
        
        if not data_available:
            st.info("Aucune donnée importée. Importez un fichier depuis la sidebar pour des analyses dynamiques.")
    
    # AFFICHER LES KPIs DYNAMIQUES EXISTANTS
    st.markdown("### KPIs Marketing")
    
    # Ligne 1 de KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Campagnes", metrics.get('total_campaigns', 0))
    
    with col2:
        st.metric("Lignes", metrics.get('total_rows', 0))
    
    with col3:
        st.metric("Colonnes", metrics.get('total_columns', 0))
    
    with col4:
        st.metric("Col. numériques", metrics.get('numeric_columns', 0))
    
    # Ligne 2 de KPIs (si disponibles)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'total_impressions' in metrics:
            st.metric("Impressions", f"{metrics['total_impressions']:,}")
        else:
            st.metric("Impressions", "N/A")
    
    with col2:
        if 'total_clicks' in metrics:
            st.metric("Clics", f"{metrics['total_clicks']:,}")
        else:
            st.metric("Clics", "N/A")
    
    with col3:
        if 'ctr' in metrics:
            st.metric("CTR", f"{metrics['ctr']:.2f}%")
        else:
            st.metric("CTR", "N/A")
    
    with col4:
        if 'roi' in metrics:
            st.metric("ROI", f"{metrics['roi']:.2f}%")
        else:
            st.metric("ROI", "N/A")
    
    st.markdown("---")
    
    # Aperçu des données si importées
    if data_available:
        st.markdown("### Aperçu des données")
        
        with st.expander("Visualiser les données importées", expanded=False):
            # Sélection du nombre de lignes à afficher
            num_rows = st.slider("Nombre de lignes à afficher", 5, 100, 10)
            
            # Afficher les données
            st.dataframe(df.head(num_rows), use_container_width=True)
            
            # Statistiques descriptives
            if numeric_cols:
                st.markdown("#### Statistiques descriptives")
                st.dataframe(df[numeric_cols].describe(), use_container_width=True)
        
        # Graphique de distribution
        if numeric_cols:
            st.markdown("### Distribution des données")
            
            selected_col = st.selectbox(
                "Sélectionner une colonne numérique:",
                numeric_cols,
                key="marketing_numeric_col"
            )
            
            if selected_col:
                fig = px.histogram(
                    df, 
                    x=selected_col,
                    title=f"Distribution de {selected_col}",
                    nbins=30,
                    color_discrete_sequence=['#667eea']
                )
                st.plotly_chart(fig, use_container_width=True)

def render_sentiment_analysis_marketing(user, db):
    """Analyse des sentiments pour marketing - VERSION EXISTANTE"""
    st.subheader("Analyse des Sentiments Clients")
    
    # Vérifier si des données ont été importées
    if 'marketing_data' not in st.session_state:
        st.warning("Aucune donnée importée")
        st.markdown("Importez d'abord vos données depuis la sidebar.")
        return
    
    df = st.session_state['marketing_data']
    
    # Identifier les colonnes de texte
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    
    if not text_cols:
        st.error("Aucune colonne texte trouvée dans les données")
        return
    
    # Interface utilisateur
    col1, col2 = st.columns(2)
    
    with col1:
        text_column = st.selectbox(
            "Colonne à analyser:",
            text_cols,
            help="Sélectionnez la colonne contenant les avis/textes clients"
        )
    
    with col2:
        if 'rating' in df.columns or 'note' in df.columns:
            rating_col = 'rating' if 'rating' in df.columns else 'note'
            st.info(f"Colonne de notes détectée: {rating_col}")
    
    # Analyse
    if st.button("Lancer l'analyse des sentiments", type="primary"):
        with st.spinner("Analyse en cours..."):
            # Vérifier si TextBlob est disponible
            if not TEXTBLOB_AVAILABLE:
                st.error("TextBlob n'est pas installé")
                return
            
            # Analyser les sentiments
            sentiments = []
            polarities = []
            
            for text in df[text_column].dropna().astype(str):
                try:
                    blob = TextBlob(text)
                    polarity = blob.sentiment.polarity
                    
                    # Classifier
                    if polarity > 0.1:
                        sentiment = 'positif'
                    elif polarity < -0.1:
                        sentiment = 'négatif'
                    else:
                        sentiment = 'neutre'
                    
                    sentiments.append(sentiment)
                    polarities.append(polarity)
                    
                except Exception as e:
                    sentiments.append('erreur')
                    polarities.append(0)
            
            # Ajouter les résultats au DataFrame
            df_results = df.copy()
            df_results['sentiment'] = sentiments
            df_results['polarite'] = polarities
            
            # Stocker les résultats
            st.session_state['sentiment_results'] = df_results
            
            # Afficher les résultats
            st.success(f"Analyse terminée sur {len(df_results)} entrées")
            
            # Distribution des sentiments
            sentiment_counts = df_results['sentiment'].value_counts()
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Graphique camembert
                fig = px.pie(
                    values=sentiment_counts.values,
                    names=sentiment_counts.index,
                    title="Distribution des sentiments",
                    hole=0.3,
                    color_discrete_map={
                        'positif': '#36B37E',
                        'négatif': '#FF5630',
                        'neutre': '#FFAB00'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Statistiques
                st.markdown("#### Statistiques")
                for sentiment, count in sentiment_counts.items():
                    percentage = (count / len(df_results)) * 100
                    st.write(f"**{sentiment}:** {count} ({percentage:.1f}%)")
                
                # Polarité moyenne
                avg_polarity = df_results['polarite'].mean()
                st.write(f"**Polarité moyenne:** {avg_polarity:.3f}")
            
            # Corrélation avec les notes si disponibles
            if 'rating' in df.columns or 'note' in df.columns:
                rating_col = 'rating' if 'rating' in df.columns else 'note'
                
                st.markdown("#### Corrélation avec les notes")
                
                # Créer un graphique de dispersion
                fig = px.scatter(
                    df_results,
                    x=rating_col,
                    y='polarite',
                    color='sentiment',
                    title="Notes vs Polarité des sentiments",
                    labels={rating_col: 'Note', 'polarite': 'Polarité'}
                )
                st.plotly_chart(fig, use_container_width=True)

def render_fake_reviews_detection_marketing(user, db):
    """Détection de faux avis pour marketing avec analyse des auteurs"""
    st.subheader("Détection de Faux Avis")
    
    # Vérifier si des données ont été importées
    if 'marketing_data' not in st.session_state:
        st.warning("Aucune donnée importée")
        st.markdown("Importez d'abord vos données depuis la sidebar.")
        return
    
    df = st.session_state['marketing_data']
    
    st.markdown("""
    ### Système de Détection de Faux Avis
    
    Cette fonctionnalité analyse automatiquement les avis pour détecter les patterns suspects 
    et identifier les auteurs potentiellement frauduleux.
    """)
    
    # Identifier les colonnes
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    
    if not text_cols:
        st.error("Aucune colonne texte trouvée")
        return
    
    # Configuration
    col1, col2, col3 = st.columns(3)
    
    with col1:
        text_column = st.selectbox(
            "Colonne des avis:",
            text_cols,
            key="fake_reviews_text_col"
        )
        
        min_length = st.slider(
            "Longueur minimale suspecte:",
            min_value=5,
            max_value=50,
            value=15,
            help="Les textes plus courts seront suspects"
        )
    
    with col2:
        # Chercher colonne auteur
        author_cols = [col for col in df.columns if any(word in col.lower() for word in ['author', 'user', 'name', 'client', 'auteur', 'utilisateur'])]
        author_column = st.selectbox(
            "Colonne auteur:",
            ['Aucune'] + author_cols,
            key="fake_reviews_author_col"
        )
        
        repetition_threshold = st.slider(
            "Seuil de répétition (%):",
            min_value=10,
            max_value=50,
            value=30,
            help="Pourcentage maximum de répétition d'un mot"
        )
    
    with col3:
        # Chercher colonne note/rating
        rating_cols = [col for col in df.columns if any(word in col.lower() for word in ['rating', 'note', 'score', 'star', 'review'])]
        rating_column = st.selectbox(
            "Colonne note (optionnel):",
            ['Aucune'] + rating_cols,
            key="fake_reviews_rating_col"
        )
        
        extreme_rating_threshold = st.checkbox(
            "Détecter notes extrêmes",
            value=True,
            help="Marquer comme suspect les notes 1 ou 5 avec texte court"
        )
    
    # Règles avancées
    with st.expander("Règles de détection avancées", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            min_reviews_per_author = st.slider(
                "Avis minimum par auteur suspect:",
                min_value=2,
                max_value=10,
                value=3,
                help="Nombre minimum d'avis pour qu'un auteur soit considéré suspect"
            )
            
            same_day_post = st.checkbox(
                "Détecter avis même jour",
                value=True,
                help="Marquer comme suspect si un auteur poste plusieurs avis le même jour"
            )
        
        with col2:
            pattern_detection = st.checkbox(
                "Détection de patterns",
                value=True,
                help="Détecter les patterns répétitifs dans les avis d'un même auteur"
            )
            
            ip_detection = st.checkbox(
                "Simulation IP identique",
                value=False,
                help="Simuler la détection d'IP identiques (si colonne IP disponible)"
            )
    
    # Initialiser les variables pour stocker les résultats
    analysis_df = None
    suspicious_authors_data = None
    fake_count = 0
    total_reviews = 0
    
    # Bouton d'analyse
    if st.button("Analyser les faux avis", type="primary", use_container_width=True):
        with st.spinner("Analyse en cours..."):
            # Préparer les données
            analysis_df = df.copy()
            
            # 1. Détection par longueur
            analysis_df['text_length'] = analysis_df[text_column].astype(str).apply(len)
            analysis_df['suspicious_length'] = analysis_df['text_length'] < min_length
            
            # 2. Détection par répétition
            def check_repetition(text):
                if isinstance(text, str) and len(text) > 0:
                    words = text.split()
                    if len(words) > 0:
                        word_counts = Counter(words)
                        most_common_count = word_counts.most_common(1)[0][1]
                        repetition_percentage = (most_common_count / len(words)) * 100
                        return repetition_percentage > repetition_threshold
                return False
            
            analysis_df['suspicious_repetition'] = analysis_df[text_column].apply(check_repetition)
            
            # 3. Détection par note extrême
            analysis_df['suspicious_rating'] = False
            if rating_column != 'Aucune' and rating_column in analysis_df.columns and extreme_rating_threshold:
                analysis_df['suspicious_rating'] = (
                    (analysis_df[rating_column].isin([1, 5])) & 
                    (analysis_df['text_length'] < 50)
                )
            
            # 4. ANALYSE DES AUTEURS (PARTIE IMPORTANTE)
            suspicious_authors_data = {}
            
            if author_column != 'Aucune' and author_column in analysis_df.columns:
                # Grouper par auteur
                author_groups = analysis_df.groupby(author_column)
                
                for author, group in author_groups:
                    author_stats = {
                        'total_reviews': len(group),
                        'fake_reviews_count': 0,
                        'suspicion_score': 0,
                        'avg_text_length': group['text_length'].mean(),
                        'extreme_ratings': 0,
                        'patterns': []
                    }
                    
                    # Calculer le score pour chaque avis de l'auteur
                    for idx, row in group.iterrows():
                        suspicion_score = 0
                        
                        if row['suspicious_length']:
                            suspicion_score += 1
                        if row['suspicious_repetition']:
                            suspicion_score += 1
                        if row['suspicious_rating']:
                            suspicion_score += 1
                            author_stats['extreme_ratings'] += 1
                        
                        if suspicion_score >= 2:
                            author_stats['fake_reviews_count'] += 1
                        
                        author_stats['suspicion_score'] += suspicion_score
                    
                    # Détection de patterns par auteur
                    if pattern_detection and len(group) >= 2:
                        texts = group[text_column].astype(str).tolist()
                        # Vérifier la similarité entre les textes
                        if len(texts) >= 2:
                            # Vérifier les mots clés communs
                            all_words = []
                            for text in texts:
                                words = text.lower().split()
                                all_words.extend(words[:10])  # Prendre les premiers mots
                            
                            word_counts = Counter(all_words)
                            common_words = [word for word, count in word_counts.items() if count > 1]
                            
                            if len(common_words) >= 3:
                                author_stats['patterns'].append(f"Mots répétés: {', '.join(common_words[:5])}")
                    
                    # Marquer l'auteur comme suspect si plusieurs critères
                    if (author_stats['total_reviews'] >= min_reviews_per_author and 
                        author_stats['fake_reviews_count'] > 0):
                        suspicious_authors_data[author] = author_stats
                
                # Marquer les avis des auteurs suspects
                suspicious_authors = list(suspicious_authors_data.keys())
                analysis_df['suspicious_author'] = analysis_df[author_column].isin(suspicious_authors)
            else:
                analysis_df['suspicious_author'] = False
            
            # Calculer le score de suspicion final
            suspicion_columns = ['suspicious_length', 'suspicious_repetition', 'suspicious_rating', 'suspicious_author']
            analysis_df['suspicion_score'] = analysis_df[suspicion_columns].sum(axis=1)
            analysis_df['is_fake_review'] = analysis_df['suspicion_score'] >= 2
            
            # Stocker les résultats dans la session
            st.session_state['fake_reviews_analysis'] = {
                'analysis_df': analysis_df,
                'suspicious_authors_data': suspicious_authors_data,
                'params': {
                    'min_length': min_length,
                    'repetition_threshold': repetition_threshold,
                    'extreme_rating_threshold': extreme_rating_threshold,
                    'min_reviews_per_author': min_reviews_per_author
                }
            }
            
            # ===========================================
            # AFFICHAGE DES RÉSULTATS
            # ===========================================
            
            fake_count = analysis_df['is_fake_review'].sum()
            total_reviews = len(analysis_df)
            fake_percentage = (fake_count / total_reviews) * 100
            
            # Métriques principales
            st.markdown("### Résultats de la détection")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Avis analysés", total_reviews)
            
            with col2:
                st.metric("Faux avis détectés", fake_count)
            
            with col3:
                st.metric("Taux de faux avis", f"{fake_percentage:.1f}%")
            
            with col4:
                avg_suspicion = analysis_df['suspicion_score'].mean()
                st.metric("Score suspicion moyen", f"{avg_suspicion:.2f}")
            
            # ===========================================
            # ANALYSE DES AUTEURS SUSPECTS
            # ===========================================
            if suspicious_authors_data:
                st.markdown("### Auteurs Suspects Identifiés")
                st.warning(f"**{len(suspicious_authors_data)} auteurs suspects détectés**")
                
                # Créer un DataFrame pour les auteurs suspects
                authors_df = pd.DataFrame.from_dict(suspicious_authors_data, orient='index')
                authors_df['author'] = authors_df.index
                authors_df = authors_df.reset_index(drop=True)
                
                # Calculer le pourcentage de faux avis par auteur
                authors_df['fake_percentage'] = (authors_df['fake_reviews_count'] / authors_df['total_reviews']) * 100
                authors_df = authors_df.sort_values('fake_percentage', ascending=False)
                
                # Afficher le top 10 des auteurs les plus suspects
                st.markdown("#### Top 10 des auteurs les plus suspects")
                
                top_authors = authors_df.head(10)
                
                fig_authors = px.bar(
                    top_authors,
                    x='author',
                    y='fake_percentage',
                    color='total_reviews',
                    title="Auteurs avec le plus haut pourcentage de faux avis",
                    labels={'author': 'Auteur', 'fake_percentage': '% de faux avis', 'total_reviews': 'Total avis'},
                    color_continuous_scale='Reds'
                )
                fig_authors.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_authors, use_container_width=True)
                
                # Tableau détaillé des auteurs suspects
                st.markdown("#### Détail des auteurs suspects")
                
                display_columns = ['author', 'total_reviews', 'fake_reviews_count', 'fake_percentage', 
                                 'avg_text_length', 'extreme_ratings', 'suspicion_score']
                
                st.dataframe(
                    authors_df[display_columns],
                    use_container_width=True,
                    height=400
                )
                
                # Patterns détectés
                st.markdown("#### Patterns détectés")
                
                for author, stats in list(suspicious_authors_data.items())[:5]:  # Limiter à 5 auteurs
                    if stats['patterns']:
                        with st.expander(f"Patterns pour {author}", expanded=False):
                            for pattern in stats['patterns']:
                                st.write(f"- {pattern}")
                
                # Recommandations pour les auteurs suspects
                st.markdown("#### Recommandations")
                
                high_risk_authors = authors_df[authors_df['fake_percentage'] >= 50]
                
                if len(high_risk_authors) > 0:
                    st.error(f"**{len(high_risk_authors)} auteurs à haut risque** (≥50% de faux avis)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Actions recommandées:**")
                        st.write("1. Suspension temporaire des comptes")
                        st.write("2. Vérification manuelle des avis")
                        st.write("3. Envoi d'email de vérification")
                    
                    with col2:
                        st.markdown("**Prévention:**")
                        st.write("1. Limite d'avis par jour")
                        st.write("2. CAPTCHA pour nouveaux avis")
                        st.write("3. Validation email obligatoire")
            
            # ===========================================
            # DÉTAILS DES FAUX AVIS
            # ===========================================
            if fake_count > 0:
                st.markdown("### Détails des avis suspects")
                
                fake_reviews = analysis_df[analysis_df['is_fake_review']]
                
                # Colonnes à afficher
                display_cols = ['suspicion_score', 'text_length']
                if author_column != 'Aucune':
                    display_cols.insert(0, author_column)
                display_cols.append(text_column)
                if rating_column != 'Aucune':
                    display_cols.append(rating_column)
                
                # Filtres
                col1, col2 = st.columns(2)
                
                with col1:
                    min_score = st.slider(
                        "Score de suspicion minimum:",
                        min_value=2,
                        max_value=4,
                        value=2,
                        key="min_suspicion_score"
                    )
                
                with col2:
                    show_only = st.multiselect(
                        "Afficher par type:",
                        ['Texte court', 'Répétition', 'Note extrême', 'Auteur suspect'],
                        default=['Texte court', 'Répétition', 'Note extrême', 'Auteur suspect']
                    )
                
                # Appliquer les filtres
                filtered_fakes = fake_reviews[fake_reviews['suspicion_score'] >= min_score]
                
                st.dataframe(
                    filtered_fakes[display_cols].head(50),
                    use_container_width=True,
                    height=500
                )
                
                # ===========================================
                # EXPORT DES RÉSULTATS
                # ===========================================
                st.markdown("### Export des résultats")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Export CSV complet
                    csv_all = analysis_df.to_csv(index=False)
                    st.download_button(
                        label="Exporter tous les résultats",
                        data=csv_all,
                        file_name=f"detection_faux_avis_complet_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col2:
                    # Export seulement les faux avis
                    if len(fake_reviews) > 0:
                        csv_fakes = fake_reviews.to_csv(index=False)
                        st.download_button(
                            label=f"Exporter {len(fake_reviews)} faux avis",
                            data=csv_fakes,
                            file_name=f"faux_avis_detectes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                
                with col3:
                    # Export des auteurs suspects
                    if suspicious_authors_data:
                        authors_export = pd.DataFrame.from_dict(suspicious_authors_data, orient='index')
                        csv_authors = authors_export.to_csv()
                        st.download_button(
                            label=f"Exporter {len(suspicious_authors_data)} auteurs suspects",
                            data=csv_authors,
                            file_name=f"auteurs_suspects_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
            else:
                st.success(" Aucun faux avis détecté selon les critères définis")
    
    # ===========================================
    # BOUTON DE RAPPORT DÉTAILLÉ (EN DEHORS DE LA CONDITION)
    # ===========================================
    
    # Vérifier si une analyse a été effectuée
    if 'fake_reviews_analysis' in st.session_state:
        analysis_data = st.session_state['fake_reviews_analysis']
        analysis_df = analysis_data['analysis_df']
        suspicious_authors_data = analysis_data['suspicious_authors_data']
        params = analysis_data['params']
        
        fake_count = analysis_df['is_fake_review'].sum() if analysis_df is not None else 0
        total_reviews = len(analysis_df) if analysis_df is not None else 0
        
        st.markdown("---")
        st.markdown("### Rapport d'analyse")
        
        # Bouton pour générer le rapport
        if st.button(" Générer un rapport détaillé", use_container_width=True):
            # Préparer le contenu du rapport
            fake_percentage = (fake_count / total_reviews * 100) if total_reviews > 0 else 0
            
            report_content = f"""
            RAPPORT DE DÉTECTION DE FAUX AVIS - AIM ANALYTICS
            ===================================================
            
            Date d'analyse: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            Fichier analysé: {st.session_state.get('marketing_filename', 'N/A')}
            Analyste: {user.get('full_name', user.get('username', 'Utilisateur'))}
            
            PARAMÈTRES UTILISÉS:
            - Longueur texte minimale: {params['min_length']} caractères
            - Seuil de répétition: {params['repetition_threshold']}%
            - Détection notes extrêmes: {'Activée' if params['extreme_rating_threshold'] else 'Désactivée'}
            - Avis minimum par auteur suspect: {params['min_reviews_per_author']}
            
            RÉSULTATS:
            - Total avis analysés: {total_reviews}
            - Faux avis détectés: {fake_count}
            - Taux de faux avis: {fake_percentage:.1f}%
            - Auteurs suspects identifiés: {len(suspicious_authors_data) if suspicious_authors_data else 0}
            
            DISTRIBUTION DES SCORES DE SUSPICION:
            """
            
            # Ajouter la distribution des scores
            if analysis_df is not None:
                score_distribution = analysis_df['suspicion_score'].value_counts().sort_index()
                for score, count in score_distribution.items():
                    percentage = (count / total_reviews) * 100
                    report_content += f"\n- Score {score}: {count} avis ({percentage:.1f}%)"
            
            # Ajouter les auteurs suspects
            if suspicious_authors_data:
                report_content += f"\n\nAUTEURS SUSPECTS ({len(suspicious_authors_data)}):"
                for i, (author, stats) in enumerate(list(suspicious_authors_data.items())[:10], 1):
                    fake_percent = (stats['fake_reviews_count'] / stats['total_reviews'] * 100) if stats['total_reviews'] > 0 else 0
                    report_content += f"""
    {i}. {author}:
       - Total avis: {stats['total_reviews']}
       - Avis suspects: {stats['fake_reviews_count']}
       - Taux suspicion: {fake_percent:.1f}%
       - Longueur moyenne: {stats['avg_text_length']:.0f} caractères
                    """
            
            report_content += f"""
            
            RECOMMANDATIONS:
            1. Vérifier manuellement les avis avec score ≥3
            2. Contacter les {min(5, len(suspicious_authors_data) if suspicious_authors_data else 0)} auteurs les plus suspects
            3. Implémenter un système de validation pour les nouveaux avis
            4. Mettre en place une limite d'avis par utilisateur par jour
            
            ---
            Rapport généré automatiquement par AIM Analytics Platform
            """
            
            # Créer un bouton de téléchargement
            st.download_button(
                label=" Télécharger le rapport complet",
                data=report_content,
                file_name=f"rapport_faux_avis_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            # Afficher un aperçu du rapport
            with st.expander("Aperçu du rapport", expanded=False):
                st.text(report_content[:2000] + "..." if len(report_content) > 2000 else report_content)
                
def render_marketing_ai_recommendations(user, db):
    """Génération de recommandations IA basées sur les analyses de sentiments et faux avis"""
    st.subheader("Recommandations Marketing Intelligentes")
    
    # Vérifier les données disponibles
    has_sentiment_data = 'sentiment_analysis' in st.session_state
    has_fake_review_data = 'fake_review_detection' in st.session_state
    
    # Section d'import des résultats d'analyse
    st.markdown("### Import des résultats d'analyse")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Import résultats analyse sentiments
        if not has_sentiment_data:
            st.info("Aucune analyse de sentiments importée")
            sentiment_file = st.file_uploader(
                "Importer résultats analyse sentiments (CSV)",
                type=['csv'],
                key="sentiment_results_upload",
                help="Importez les résultats de l'analyse des sentiments"
            )
            
            if sentiment_file:
                try:
                    sentiment_df = pd.read_csv(sentiment_file)
                    # Vérifier les colonnes nécessaires
                    required_cols = ['sentiment', 'polarite']
                    if all(col in sentiment_df.columns for col in required_cols):
                        st.session_state['sentiment_analysis'] = sentiment_df
                        st.success(f"Import réussi: {len(sentiment_df)} avis analysés")
                        st.rerun()
                    else:
                        st.error("Format invalide: colonnes 'sentiment' et 'polarite' requises")
                except Exception as e:
                    st.error(f"Erreur d'import: {str(e)}")
    
    with col2:
        # Import résultats détection faux avis
        if not has_fake_review_data:
            st.info("Aucune détection de faux avis importée")
            fake_review_file = st.file_uploader(
                "Importer résultats détection faux avis (CSV)",
                type=['csv'],
                key="fake_review_results_upload",
                help="Importez les résultats de la détection de faux avis"
            )
            
            if fake_review_file:
                try:
                    fake_review_df = pd.read_csv(fake_review_file)
                    # Chercher les colonnes de statut
                    status_col = None
                    for col in ['is_spam_final', 'faux_avis', 'status', 'statut']:
                        if col in fake_review_df.columns:
                            status_col = col
                            break
                    
                    if status_col:
                        st.session_state['fake_review_detection'] = fake_review_df
                        st.success(f"Import réussi: {len(fake_review_df)} avis analysés")
                        st.rerun()
                    else:
                        st.error("Format invalide: colonne de statut non trouvée")
                except Exception as e:
                    st.error(f"Erreur d'import: {str(e)}")
    
    # Afficher les statistiques si des données sont disponibles
    if has_sentiment_data or has_fake_review_data:
        st.markdown("### Statistiques disponibles")
        
        stats_cols = st.columns(2)
        
        with stats_cols[0]:
            if has_sentiment_data:
                sentiment_df = st.session_state['sentiment_analysis']
                sentiment_counts = sentiment_df['sentiment'].value_counts()
                st.markdown("**Analyse des sentiments:**")
                st.write(f"- Total avis: {len(sentiment_df)}")
                for sentiment, count in sentiment_counts.items():
                    percentage = (count / len(sentiment_df)) * 100
                    st.write(f"- {sentiment}: {count} ({percentage:.1f}%)")
        
        with stats_cols[1]:
            if has_fake_review_data:
                fake_review_df = st.session_state['fake_review_detection']
                # Identifier la colonne de statut
                status_col = None
                for col in ['is_spam_final', 'faux_avis', 'status', 'statut']:
                    if col in fake_review_df.columns:
                        status_col = col
                        break
                
                if status_col:
                    if fake_review_df[status_col].dtype == 'bool':
                        fake_count = fake_review_df[status_col].sum()
                    else:
                        fake_count = fake_review_df[fake_review_df[status_col].str.contains('spam|faux|SPAM', case=False, na=False)].shape[0]
                    
                    st.markdown("**Détection faux avis:**")
                    st.write(f"- Total avis: {len(fake_review_df)}")
                    st.write(f"- Faux avis: {fake_count}")
                    fake_rate = (fake_count / len(fake_review_df) * 100) if len(fake_review_df) > 0 else 0
                    st.write(f"- Taux: {fake_rate:.1f}%")
    
    # Section de génération de recommandations
    st.markdown("### Génération de recommandations marketing")
    
    if not (has_sentiment_data or has_fake_review_data):
        st.warning("Importez d'abord les résultats d'analyse pour générer des recommandations")
        return
    
    # Options de génération
    col1, col2 = st.columns(2)
    
    with col1:
        recommendation_type = st.selectbox(
            "Type de recommandations:",
            ["Optimisation campagnes", "Stratégie contenu", "Amélioration réputation", 
             "Détection fraudes", "Analyse complète"],
            help="Sélectionnez le domaine d'optimisation"
        )
    
    with col2:
        time_horizon = st.selectbox(
            "Horizon temporel:",
            ["Court terme (1-3 mois)", "Moyen terme (3-6 mois)", "Long terme (6-12 mois)"],
            help="Période de mise en œuvre"
        )
    
    # Bouton de génération
    if st.button("Générer les recommandations marketing", type="primary", use_container_width=True):
        with st.spinner("Analyse en cours et génération des recommandations..."):
            # Récupérer les données d'analyse
            sentiment_stats = {}
            fake_review_stats = {}
            
            if has_sentiment_data:
                sentiment_df = st.session_state['sentiment_analysis']
                sentiment_counts = sentiment_df['sentiment'].value_counts()
                sentiment_stats = {
                    'total': len(sentiment_df),
                    'positif': sentiment_counts.get('positif', 0),
                    'negatif': sentiment_counts.get('négatif', 0),
                    'neutre': sentiment_counts.get('neutre', 0),
                    'positif_rate': (sentiment_counts.get('positif', 0) / len(sentiment_df) * 100) if len(sentiment_df) > 0 else 0,
                    'negatif_rate': (sentiment_counts.get('négatif', 0) / len(sentiment_df) * 100) if len(sentiment_df) > 0 else 0
                }
            
            if has_fake_review_data:
                fake_review_df = st.session_state['fake_review_detection']
                status_col = None
                for col in ['is_spam_final', 'faux_avis', 'status', 'statut']:
                    if col in fake_review_df.columns:
                        status_col = col
                        break
                
                if status_col:
                    if fake_review_df[status_col].dtype == 'bool':
                        fake_count = fake_review_df[status_col].sum()
                    else:
                        fake_count = fake_review_df[fake_review_df[status_col].str.contains('spam|faux|SPAM', case=False, na=False)].shape[0]
                    
                    fake_review_stats = {
                        'total': len(fake_review_df),
                        'fake_count': fake_count,
                        'fake_rate': (fake_count / len(fake_review_df) * 100) if len(fake_review_df) > 0 else 0
                    }
            
            # Générer les recommandations basées sur les analyses
            recommendations = generate_marketing_recommendations(
                sentiment_stats=sentiment_stats,
                fake_review_stats=fake_review_stats,
                recommendation_type=recommendation_type,
                time_horizon=time_horizon
            )
            
            # Stocker les recommandations
            st.session_state['marketing_recommendations'] = recommendations
            st.session_state['recommendations_generated'] = True
            
            # Log dans la base de données
            db.log_ai_recommendation(
                user['id'],
                recommendation_type,
                f"Génération de {len(recommendations)} recommandations marketing"
            )
            
            st.success(f"{len(recommendations)} recommandations générées avec succès!")
    
    # Afficher les recommandations si disponibles
    if 'marketing_recommendations' in st.session_state and st.session_state.get('recommendations_generated', False):
        recommendations = st.session_state['marketing_recommendations']
        
        st.markdown("### Recommandations marketing générées")
        
        # Afficher les recommandations
        for i, rec in enumerate(recommendations, 1):
            with st.expander(f"Recommandation {i}: {rec['title']}", expanded=True):
                st.markdown(f"**Catégorie:** {rec['category']}")
                st.markdown(f"**Priorité:** {rec['priority']}")
                st.markdown(f"**Impact estimé:** {rec['impact']}")
                st.markdown(f"**Effort requis:** {rec['effort']}")
                st.markdown(f"**Délai:** {rec['timeframe']}")
                
                st.markdown("**Description:**")
                st.write(rec['description'])
                
                st.markdown("**Actions concrètes:**")
                for action in rec['actions']:
                    st.markdown(f"- {action}")
                
                st.markdown("**Indicateurs de succès:**")
                for kpi in rec['kpis']:
                    st.markdown(f"- {kpi}")
        
        # Section d'export PDF
        st.markdown("---")
        st.markdown("### Export des recommandations")
        
        if st.button("Générer le rapport PDF", type="primary", use_container_width=True):
            # Générer le contenu du rapport
            pdf_content = generate_pdf_report(recommendations, user, sentiment_stats, fake_review_stats)
            
            # Télécharger le PDF
            st.download_button(
                label="Télécharger le rapport PDF",
                data=pdf_content,
                file_name=f"recommandations_marketing_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

def generate_marketing_recommendations(sentiment_stats, fake_review_stats, recommendation_type, time_horizon):
    """Génère des recommandations marketing basées sur les analyses"""
    
    recommendations = []
    
    # Analyse basée sur les sentiments
    if sentiment_stats:
        positif_rate = sentiment_stats.get('positif_rate', 0)
        negatif_rate = sentiment_stats.get('negatif_rate', 0)
        total_reviews = sentiment_stats.get('total', 0)
        
        # Recommandations basées sur le taux de satisfaction
        if negatif_rate > 20:
            recommendations.append({
                'title': "Plan d'action pour réduire les avis négatifs",
                'category': "Gestion de réputation",
                'priority': "Haute",
                'impact': "Élevé",
                'effort': "Moyen",
                'timeframe': time_horizon,
                'description': f"Avec {negatif_rate:.1f}% d'avis négatifs, il est crucial de mettre en place un plan d'action pour améliorer la satisfaction client.",
                'actions': [
                    "Mettre en place un système de suivi des réclamations",
                    "Former le service client à la gestion des insatisfactions",
                    "Créer un programme de fidélisation pour les clients mécontents",
                    "Analyser les causes racines des avis négatifs"
                ],
                'kpis': [
                    "Réduction de 50% des avis négatifs dans les 3 mois",
                    "Amélioration du score de satisfaction de 20%",
                    "Temps de réponse aux réclamations réduit de 30%"
                ]
            })
        
        if positif_rate < 60:
            recommendations.append({
                'title': "Stratégie d'augmentation de la satisfaction client",
                'category': "Expérience client",
                'priority': "Moyenne",
                'impact': "Moyen",
                'effort': "Faible",
                'timeframe': time_horizon,
                'description': f"Un taux de satisfaction de {positif_rate:.1f}% indique une marge d'amélioration significative pour renforcer l'expérience client.",
                'actions': [
                    "Implémenter un système de collecte de feedback en temps réel",
                    "Créer un programme de reconnaissance des meilleurs avis",
                    "Optimiser le processus d'achat et de livraison",
                    "Développer du contenu éducatif pour les clients"
                ],
                'kpis': [
                    "Augmentation de 15% du taux de satisfaction",
                    "Hausse de 25% des recommandations clients",
                    "Amélioration du NPS de 10 points"
                ]
            })
    
    # Analyse basée sur les faux avis
    if fake_review_stats:
        fake_rate = fake_review_stats.get('fake_rate', 0)
        fake_count = fake_review_stats.get('fake_count', 0)
        
        if fake_rate > 5:
            recommendations.append({
                'title': "Plan de lutte contre les faux avis",
                'category': "Intégrité des données",
                'priority': "Haute",
                'impact': "Élevé",
                'effort': "Moyen",
                'timeframe': time_horizon,
                'description': f"Un taux de {fake_rate:.1f}% de faux avis ({fake_count} avis) compromet la crédibilité de votre marque et nécessite une action immédiate.",
                'actions': [
                    "Mettre en place un système de vérification d'authenticité",
                    "Former une équipe de modération dédiée",
                    "Implémenter des algorithmes de détection avancée",
                    "Créer une politique claire de publication d'avis"
                ],
                'kpis': [
                    "Réduction de 80% des faux avis détectés",
                    "Temps de modération réduit de 40%",
                    "Amélioration de la crédibilité des avis de 25%"
                ]
            })
    
    # Recommandations générales basées sur le type
    if recommendation_type == "Optimisation campagnes":
        recommendations.extend([
            {
                'title': "Optimisation du ciblage des campagnes publicitaires",
                'category': "Publicité",
                'priority': "Moyenne",
                'impact': "Élevé",
                'effort': "Faible",
                'timeframe': time_horizon,
                'description': "Basé sur l'analyse des données clients, optimisez le ciblage de vos campagnes pour améliorer le ROI.",
                'actions': [
                    "Segmenter la base client selon les comportements d'achat",
                    "Ajuster les messages publicitaires par segment",
                    "Tester différents canaux de diffusion",
                    "Optimiser les heures de diffusion des campagnes"
                ],
                'kpis': [
                    "Augmentation du CTR de 20%",
                    "Réduction du coût par acquisition de 15%",
                    "Amélioration du ROI des campagnes de 25%"
                ]
            },
            {
                'title': "Stratégie de retargeting personnalisé",
                'category': "Marketing digital",
                'priority': "Basse",
                'impact': "Moyen",
                'effort': "Faible",
                'timeframe': time_horizon,
                'description': "Développez une stratégie de retargeting basée sur le parcours client pour reconquérir les prospects perdus.",
                'actions': [
                    "Créer des audiences de retargeting segmentées",
                    "Développer des messages personnalisés par étape du parcours",
                    "Automatiser les séquences de retargeting",
                    "Tester différentes offres de reconquête"
                ],
                'kpis': [
                    "Taux de conversion retargeting de 3%",
                    "Coût par conversion réduit de 30%",
                    "Taux de réengagement de 15%"
                ]
            }
        ])
    
    elif recommendation_type == "Stratégie contenu":
        recommendations.extend([
            {
                'title': "Plan éditorial basé sur les insights clients",
                'category': "Content Marketing",
                'priority': "Moyenne",
                'impact': "Moyen",
                'effort': "Moyen",
                'timeframe': time_horizon,
                'description': "Développez un plan de contenu qui répond aux besoins et questions de vos clients identifiés dans les avis.",
                'actions': [
                    "Analyser les thèmes récurrents dans les avis clients",
                    "Créer du contenu éducatif sur les points de friction identifiés",
                    "Développer des études de cas clients réussis",
                    "Produire du contenu formatif sur l'utilisation des produits"
                ],
                'kpis': [
                    "Augmentation du trafic organique de 30%",
                    "Temps moyen sur page de 3 minutes",
                    "Taux de partage social de 5%"
                ]
            }
        ])
    
    # Ajouter des recommandations basées sur les deux analyses
    if sentiment_stats and fake_review_stats:
        recommendations.append({
            'title': "Stratégie intégrée de gestion de la réputation",
            'category': "Marketing stratégique",
            'priority': "Haute",
            'impact': "Élevé",
            'effort': "Élevé",
            'timeframe': time_horizon,
            'description': f"Combinez la gestion des avis authentiques ({sentiment_stats.get('total', 0)} avis analysés) et la lutte contre les faux avis ({fake_review_stats.get('fake_count', 0)} détectés) pour une approche complète.",
            'actions': [
                "Créer un tableau de bord de monitoring de la réputation",
                "Établir des protocoles de réponse aux différents types d'avis",
                "Développer un programme d'ambassadeurs clients",
                "Implémenter un système de récompense pour les avis authentiques"
            ],
            'kpis': [
                "Score de réputation globale amélioré de 20%",
                "Taux d'engagement sur les avis de 15%",
                "Nombre d'avis authentiques augmenté de 30%"
            ]
        })
    
    # Si aucune donnée spécifique, donner des recommandations génériques
    if not recommendations:
        recommendations.append({
            'title': "Stratégie marketing de base",
            'category': "Marketing général",
            'priority': "Moyenne",
            'impact': "Moyen",
            'effort': "Faible",
            'timeframe': time_horizon,
            'description': "Recommandations marketing générales pour améliorer vos performances.",
            'actions': [
                "Analyser régulièrement les données de performance",
                "Tester différentes approches marketing",
                "Collecter systématiquement le feedback client",
                "Optimiser le parcours d'achat"
            ],
            'kpis': [
                "Amélioration continue des indicateurs clés",
                "Augmentation progressive de la satisfaction client",
                "Optimisation du retour sur investissement"
            ]
        })
    
    return recommendations

def generate_pdf_report(recommendations, user, sentiment_stats, fake_review_stats):
    """Génère un rapport PDF des recommandations marketing"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    import io
    
    # Créer le buffer pour le PDF
    buffer = io.BytesIO()
    
    # Créer le document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        textColor=colors.HexColor('#1E3A8A')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=12,
        textColor=colors.HexColor('#334155')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=6,
        spaceBefore=12,
        textColor=colors.HexColor('#475569')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Contenu du rapport
    story = []
    
    # Titre
    story.append(Paragraph("RAPPORT DE RECOMMANDATIONS MARKETING", title_style))
    story.append(Spacer(1, 12))
    
    # Informations générales
    story.append(Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
    story.append(Paragraph(f"Généré pour : {user.get('full_name', user.get('username', 'Utilisateur'))}", normal_style))
    story.append(Paragraph(f"Département : {user.get('department', 'Marketing')}", normal_style))
    story.append(Spacer(1, 20))
    
    # Résumé exécutif
    story.append(Paragraph("RÉSUMÉ EXÉCUTIF", subtitle_style))
    story.append(Paragraph(f"Ce rapport présente {len(recommendations)} recommandations marketing basées sur l'analyse des données clients. Les recommandations sont classées par priorité et incluent des actions concrètes ainsi que des indicateurs de performance.", normal_style))
    story.append(Spacer(1, 12))
    
    # Statistiques d'analyse
    story.append(Paragraph("STATISTIQUES D'ANALYSE", subtitle_style))
    
    stats_data = []
    if sentiment_stats:
        stats_data.append(["Analyse des sentiments", f"{sentiment_stats.get('total', 0)} avis analysés"])
        stats_data.append(["", f"Taux positif : {sentiment_stats.get('positif_rate', 0):.1f}%"])
        stats_data.append(["", f"Taux négatif : {sentiment_stats.get('negatif_rate', 0):.1f}%"])
    
    if fake_review_stats:
        stats_data.append(["Détection faux avis", f"{fake_review_stats.get('total', 0)} avis analysés"])
        stats_data.append(["", f"Faux avis détectés : {fake_review_stats.get('fake_count', 0)}"])
        stats_data.append(["", f"Taux de faux avis : {fake_review_stats.get('fake_rate', 0):.1f}%"])
    
    if stats_data:
        stats_table = Table(stats_data, colWidths=[200, 200])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(stats_table)
    
    story.append(Spacer(1, 20))
    
    # Recommandations
    story.append(Paragraph("RECOMMANDATIONS DÉTAILLÉES", subtitle_style))
    
    for i, rec in enumerate(recommendations, 1):
        story.append(Paragraph(f"Recommandation {i}: {rec['title']}", heading_style))
        
        # Métadonnées de la recommandation
        meta_data = [
            ["Catégorie", rec['category']],
            ["Priorité", rec['priority']],
            ["Impact estimé", rec['impact']],
            ["Effort requis", rec['effort']],
            ["Délai de mise en œuvre", rec['timeframe']]
        ]
        
        meta_table = Table(meta_data, colWidths=[100, 300])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(meta_table)
        
        story.append(Spacer(1, 6))
        story.append(Paragraph("Description :", heading_style))
        story.append(Paragraph(rec['description'], normal_style))
        story.append(Spacer(1, 6))
        
        story.append(Paragraph("Actions concrètes :", heading_style))
        for action in rec['actions']:
            story.append(Paragraph(f"• {action}", normal_style))
        
        story.append(Spacer(1, 6))
        story.append(Paragraph("Indicateurs de succès :", heading_style))
        for kpi in rec['kpis']:
            story.append(Paragraph(f"• {kpi}", normal_style))
        
        story.append(Spacer(1, 20))
    
    # Plan d'action synthétique
    story.append(Paragraph("PLAN D'ACTION SYNTHÉTIQUE", subtitle_style))
    
    # Tableau récapitulatif des recommandations
    recap_data = [["N°", "Recommandation", "Priorité", "Impact", "Effort", "Délai"]]
    
    for i, rec in enumerate(recommendations, 1):
        recap_data.append([
            str(i),
            rec['title'][:50] + "..." if len(rec['title']) > 50 else rec['title'],
            rec['priority'],
            rec['impact'],
            rec['effort'],
            rec['timeframe']
        ])
    
    recap_table = Table(recap_data, colWidths=[30, 200, 60, 60, 60, 80])
    recap_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(recap_table)
    
    story.append(Spacer(1, 20))
    
    # Conclusion
    story.append(Paragraph("CONCLUSION", subtitle_style))
    story.append(Paragraph("Les recommandations présentées dans ce rapport sont basées sur l'analyse objective des données clients. Une mise en œuvre progressive, en commençant par les recommandations à haute priorité, permettra d'optimiser significativement vos performances marketing.", normal_style))
    
    story.append(Spacer(1, 12))
    story.append(Paragraph("Pour toute question ou besoin d'accompagnement dans la mise en œuvre de ces recommandations, contactez l'équipe d'analyse AIM.", normal_style))
    
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Généré par AIM Analytics Platform • {datetime.now().strftime('%d/%m/%Y')}", normal_style))
    
    # Générer le PDF
    doc.build(story)
    
    # Récupérer le contenu du buffer
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content
# =============================
#          MAIN APP
# =============================
def main():
    """Fonction principale de l'application"""
    
    # Initialiser la base de données
    db = get_database_manager()
    
    # Vérifier l'état de l'authentification
    if 'user' not in st.session_state:
        # Page de connexion
        render_login_page(db)
    
    elif 'force_password_change' in st.session_state and st.session_state.force_password_change:
        # Page de changement de mot de passe obligatoire
        render_password_change_page(st.session_state.user, db)
    
    else:
        # Dashboard selon le rôle
        user = st.session_state.user
        user_role = user.get('role', 'user')
        
        try:
            if user_role == 'admin':
                dashboard_admin_enhanced(user, db)
            elif user_role == 'data_analyst':
                dashboard_data_analyst(user, db)
            elif user_role == 'marketing':
                dashboard_marketing(user, db)
            elif user_role == 'support':
                dashboard_support(user, db)
            else:
                # Rôle par défaut - Dashboard de base
                st.title(f"Bienvenue {user.get('full_name', 'Utilisateur')}")
                st.info(f"Rôle détecté: {user_role}. Contactez l'administrateur pour un accès personnalisé.")
                
                # Déconnexion
                if st.button("Déconnexion"):
                    db.log_activity(user['id'], "logout", "Déconnexion utilisateur")
                    st.session_state.clear()
                    st.rerun()
        
        except Exception as e:
            st.error(f"Une erreur est survenue : {str(e)}")
            st.info("Veuillez rafraîchir la page ou vous reconnecter.")

# Point d'entrée
if __name__ == "__main__":
    main() 
