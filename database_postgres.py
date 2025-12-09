# database_postgres.py
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
from datetime import datetime

class PostgresDatabase:
    def __init__(self):
        self.conn_params = {
            'host': 'localhost',
            'database': 'aim_platform',
            'user': 'postgres',
            'password': 'votre_mot_de_passe',  # Remplacez par votre mot de passe
            'port': 5432
        }
        print("✅ Connexion à PostgreSQL établie")
    
    def get_connection(self):
        """Établir la connexion"""
        return psycopg2.connect(**self.conn_params, cursor_factory=RealDictCursor)
    
    def hash_password(self, password):
        """Hasher un mot de passe"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password, hashed):
        """Vérifier un mot de passe"""
        return self.hash_password(password) == hashed
    
    def authenticate_user(self, username, password):
        """Authentifier un utilisateur"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, username, email, full_name, role, password, status, avatar_color
            FROM users WHERE username = %s
            ''', (username,))
            
            user = cursor.fetchone()
            conn.close()
            
            if user:
                # Vérifier le mot de passe
                if user['password'] == self.hash_password(password) and user['status'] == 'active':
                    # Mettre à jour la dernière connexion
                    self.update_last_login(user['id'])
                    return {
                        'id': user['id'],
                        'username': user['username'],
                        'email': user['email'],
                        'full_name': user['full_name'],
                        'role': user['role'],
                        'status': user['status'],
                        'avatar_color': user['avatar_color']
                    }
            return None
        except Exception as e:
            print(f"Erreur d'authentification: {e}")
            return None
    
    def update_last_login(self, user_id):
        """Mettre à jour la dernière connexion"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_login = NOW() WHERE id = %s', (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erreur update_last_login: {e}")
    
    def get_users(self, filters=None):
        """Récupérer les utilisateurs"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = 'SELECT * FROM users ORDER BY created_at DESC'
            cursor.execute(query)
            users = cursor.fetchall()
            conn.close()
            
            return users
        except Exception as e:
            print(f"Erreur get_users: {e}")
            return []
    
    def create_user(self, user_data):
        """Créer un nouvel utilisateur"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            hashed_password = self.hash_password(user_data['password'])
            
            cursor.execute('''
            INSERT INTO users (username, email, password, full_name, role, department, avatar_color)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (
                user_data['username'],
                user_data['email'],
                hashed_password,
                user_data['full_name'],
                user_data['role'],
                user_data.get('department', ''),
                user_data.get('avatar_color', self.get_role_color(user_data['role']))
            ))
            
            user_id = cursor.fetchone()['id']
            
            # Logger l'activité
            cursor.execute('''
            INSERT INTO activities (user_id, activity_type, description)
            VALUES (%s, %s, %s)
            ''', (user_id, 'user_creation', f'Création compte: {user_data["username"]}'))
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'user_id': user_id}
            
        except psycopg2.IntegrityError as e:
            return {'success': False, 'error': 'Cet utilisateur ou email existe déjà'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_role_color(self, role):
        """Couleur par rôle"""
        colors = {'admin': '#FF5630', 'marketing': '#36B37E', 'analyst': '#6554C0'}
        return colors.get(role, '#6B7280')
    
    def get_user_stats(self):
        """Statistiques des utilisateurs"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Total utilisateurs
            cursor.execute('SELECT COUNT(*) as count FROM users')
            stats['total_users'] = cursor.fetchone()['count']
            
            # Utilisateurs par rôle
            cursor.execute('SELECT role, COUNT(*) as count FROM users GROUP BY role')
            stats['users_by_role'] = {row['role']: row['count'] for row in cursor.fetchall()}
            
            conn.close()
            return stats
        except Exception as e:
            print(f"Erreur get_user_stats: {e}")
            return {'total_users': 0, 'users_by_role': {}}