from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration PostgreSQL (la même que Streamlit)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "aim_platform"),
    "user": os.getenv("DB_USER", "aim_user"),
    "password": os.getenv("DB_PASSWORD", "aim_password"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    """Établir une connexion à la base de données"""
    return psycopg2.connect(**DB_CONFIG)

@app.route('/')
def home():
    return jsonify({"message": "AIM Analytics API", "status": "running"})

@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint de connexion qui utilise la même DB que Streamlit"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT * FROM users 
            WHERE (username=%s OR email=%s) 
            AND is_active=TRUE
        """, (username, username))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Vérifier le mot de passe avec bcrypt
        if bcrypt.checkpw(
            password.encode('utf-8'),
            user['password_hash'].encode('utf-8')
        ):
            # Mettre à jour last_login
            cursor.execute("""
                UPDATE users SET last_login=%s WHERE id=%s
            """, (datetime.now(), user['id']))
            conn.commit()
            
            # Retirer le hash du mot de passe pour la réponse
            user.pop('password_hash')
            return jsonify({
                "success": True,
                "user": user,
                "message": "Login successful"
            })
        else:
            return jsonify({"error": "Invalid password"}), 401
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/users', methods=['GET'])
def get_users():
    """Récupérer tous les utilisateurs (pour admin)"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT id, username, email, full_name, role, 
                   is_active, created_at, last_login
            FROM users
            ORDER BY id
        """)
        users = cursor.fetchall()
        return jsonify({"users": users})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Vérifier la santé de l'API et de la DB"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 API AIM Analytics avec PostgreSQL")
    print("=" * 60)
    print("URL: http://127.0.0.1:5000")
    print("\n📡 Endpoints:")
    print("  - GET  /              : Page d'accueil")
    print("  - POST /api/login     : Connexion")
    print("  - GET  /api/users     : Liste des utilisateurs")
    print("  - GET  /api/health    : Vérification de santé")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)