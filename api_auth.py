# api_auth.py
from datetime import datetime
from api_utils import load_users, save_users, hash_password, validate_email, validate_password, create_user_response
import uuid

def check_credentials_api(identifier, password):
    """Vérifie les identifiants et retourne les données utilisateur si valides"""
    users = load_users()
    
    # Chercher l'utilisateur par email ou username
    user_data = None
    for username, user in users.items():
        if user['email'].lower() == identifier.lower() or username.lower() == identifier.lower():
            user_data = user
            break
    
    if user_data:
        if not user_data.get('is_active', True):
            return False, {"error": "Ce compte est désactivé"}
        
        if user_data['password_hash'] == hash_password(password):
            # Mettre à jour la dernière connexion
            user_data['last_login'] = datetime.now().isoformat()
            users[user_data['username']] = user_data
            save_users(users)
            
            return True, create_user_response(user_data)
    
    return False, {"error": "Identifiant ou mot de passe incorrect"}

def register_user_api(username, email, password, role="marketing", full_name="", company=""):
    """Enregistre un nouvel utilisateur via l'API"""
    users = load_users()
    
    if username in users:
        return False, "Ce nom d'utilisateur est déjà pris"
    
    for user in users.values():
        if user['email'].lower() == email.lower():
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
        "role": role,
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True
    }
    
    save_users(users)
    
    return True, create_user_response(users[username])

def validate_user_api(identifier):
    """Valide l'existence d'un utilisateur sans vérifier le mot de passe"""
    users = load_users()
    
    user_data = None
    for username, user in users.items():
        if user['email'].lower() == identifier.lower() or username.lower() == identifier.lower():
            user_data = user
            break
    
    if user_data:
        return True, create_user_response(user_data)
    else:
        return False, {"message": "Utilisateur non trouvé"}