# api_routes.py
from flask import jsonify, request
from api_auth import check_credentials_api, register_user_api, validate_user_api
from api_utils import load_users, create_user_response

def register_routes(app):
    """Enregistre toutes les routes de l'API"""
    
    @app.route('/')
    def home():
        """Endpoint de bienvenue"""
        return jsonify({
            "message": "Bienvenue sur l'API AIM (Analyse Marketing Intelligente)",
            "version": "1.0.0",
            "endpoints": {
                "register": "/api/register (POST)",
                "login": "/api/login (POST)",
                "users": "/api/users (GET)",
                "user": "/api/user/<username> (GET)",
                "validate": "/api/validate (POST)"
            }
        })
    
    @app.route('/api/register', methods=['POST'])
    def register():
        """Endpoint d'inscription d'un nouvel utilisateur"""
        try:
            data = request.get_json()
            
            # Vérifier les données requises
            required_fields = ['username', 'email', 'password']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({
                        "success": False,
                        "error": f"Le champ '{field}' est requis"
                    }), 400
            
            username = data['username']
            email = data['email']
            password = data['password']
            role = data.get('role', 'marketing')
            full_name = data.get('full_name', username)
            company = data.get('company', '')
            
            success, result = register_user_api(username, email, password, role, full_name, company)
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Inscription réussie !",
                    "user": result
                }), 201
            else:
                return jsonify({
                    "success": False,
                    "error": result
                }), 400
                
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Erreur lors de l'inscription: {str(e)}"
            }), 500
    
    @app.route('/api/login', methods=['POST'])
    def login():
        """Endpoint de connexion"""
        try:
            data = request.get_json()
            
            # Vérifier les données requises
            if 'identifier' not in data or 'password' not in data:
                return jsonify({
                    "success": False,
                    "error": "Identifiant et mot de passe requis"
                }), 400
            
            identifier = data['identifier']
            password = data['password']
            
            success, result = check_credentials_api(identifier, password)
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Connexion réussie",
                    "user": result
                }), 200
            else:
                return jsonify(result), 401
                
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Erreur lors de la connexion: {str(e)}"
            }), 500
    
    @app.route('/api/users', methods=['GET'])
    def get_users():
        """Endpoint pour récupérer la liste des utilisateurs (sans mots de passe)"""
        try:
            users = load_users()
            
            # Nettoyer les données (enlever les hashs de mot de passe)
            cleaned_users = {}
            for username, user_data in users.items():
                cleaned_users[username] = create_user_response(user_data)
            
            return jsonify({
                "success": True,
                "count": len(cleaned_users),
                "users": cleaned_users
            }), 200
            
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Erreur lors de la récupération des utilisateurs: {str(e)}"
            }), 500
    
    @app.route('/api/user/<username>', methods=['GET'])
    def get_user(username):
        """Endpoint pour récupérer les informations d'un utilisateur spécifique"""
        try:
            users = load_users()
            
            if username not in users:
                return jsonify({
                    "success": False,
                    "error": "Utilisateur non trouvé"
                }), 404
            
            user_data = create_user_response(users[username])
            
            return jsonify({
                "success": True,
                "user": user_data
            }), 200
            
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Erreur lors de la récupération de l'utilisateur: {str(e)}"
            }), 500
    
    @app.route('/api/validate', methods=['POST'])
    def validate_user():
        """Endpoint pour valider un utilisateur (sans connexion)"""
        try:
            data = request.get_json()
            
            if 'identifier' not in data:
                return jsonify({
                    "success": False,
                    "error": "Identifiant requis"
                }), 400
            
            identifier = data['identifier']
            exists, result = validate_user_api(identifier)
            
            if exists:
                return jsonify({
                    "success": True,
                    "exists": True,
                    "user": result
                }), 200
            else:
                return jsonify({
                    "success": True,
                    "exists": False,
                    "message": "Utilisateur non trouvé"
                }), 200
                
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Erreur lors de la validation: {str(e)}"
            }), 500
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Endpoint de vérification de la santé de l'API"""
        return jsonify({
            "status": "healthy",
            "service": "AIM Authentication API",
            "timestamp": datetime.now().isoformat()
        }), 200