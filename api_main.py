# api_main.py
from flask import Flask
from flask_cors import CORS
import os
from api_routes import register_routes
from api_utils import save_users

# ================================================================
#  CONFIGURATION DE L'APPLICATION
# ================================================================

def create_app():
    """Crée et configure l'application Flask"""
    app = Flask(__name__)
    CORS(app)  # Activer CORS pour toutes les routes
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'votre_cle_secrete_tres_longue_et_complexe')
    
    # Enregistrer les routes
    register_routes(app)
    
    return app

# ================================================================
# 🚀 LANCEMENT DE L'APPLICATION
# ================================================================

if __name__ == '__main__':
    # Créer l'application
    app = create_app()
    
    # Créer le fichier users.json s'il n'existe pas
    USERS_FILE = "users.json"
    if not os.path.exists(USERS_FILE):
        save_users({})
        print(f"✓ Fichier {USERS_FILE} créé avec succès.")
    
    # Démarrer le serveur Flask
    print("=" * 60)
    print("🚀 Démarrage de l'API AIM Authentication...")
    print("=" * 60)
    print("URL: http://127.0.0.1:5000")
    print("\n📡 Endpoints disponibles:")
    print("  - GET  /              : Page d'accueil")
    print("  - POST /api/register  : Inscription d'un utilisateur")
    print("  - POST /api/login     : Connexion")
    print("  - GET  /api/users     : Liste des utilisateurs")
    print("  - GET  /api/user/<username> : Informations d'un utilisateur")
    print("  - POST /api/validate  : Validation d'un identifiant")
    print("  - GET  /api/health    : Vérification de santé")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)