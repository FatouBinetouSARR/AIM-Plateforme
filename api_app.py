# -*- coding: utf-8 -*-
"""
AIM - Intelligent Marketing API
Analyse automatique des données marketing d'une entreprise
Version avec authentification JWT
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
import pandas as pd
import joblib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import jwt
import bcrypt
import sqlite3
from contextlib import contextmanager
import secrets
import re

# ----------------------------
# INITIALISATION API
# ----------------------------
app = FastAPI(
    title="AIM - Intelligent Marketing API",
    description="Analyse intelligente : spam, sentiment social, avis clients",
    version="3.0.0",
    docs_url=None,
    redoc_url=None
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# CONFIGURATION DE SÉCURITÉ
# ----------------------------
# Clés JWT (en production, utiliser des variables d'environnement)
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 heures
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Schéma de sécurité
security = HTTPBearer()

# ----------------------------
# BASE DE DONNÉES
# ----------------------------
def init_database():
    """Initialise la base de données SQLite"""
    conn = sqlite3.connect('aim_api.db')
    c = conn.cursor()
    
    # Table utilisateurs
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company TEXT,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            api_key TEXT UNIQUE
        )
    ''')
    
    # Table des tokens révoqués
    c.execute('''
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            expires_at TIMESTAMP,
            revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des appels API
    c.execute('''
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            endpoint TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status_code INTEGER,
            duration_ms INTEGER
        )
    ''')
    
    # Créer un admin par défaut si non existant
    c.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not c.fetchone():
        admin_password = hash_password("Admin123!")
        c.execute('''
            INSERT INTO users (username, email, password_hash, role, api_key)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin@aim.com', admin_password, 'admin', secrets.token_urlsafe(32)))
    
    conn.commit()
    conn.close()

# Initialiser la base de données au démarrage
init_database()

@contextmanager
def get_db_connection():
    """Contexte pour gérer les connexions à la base de données"""
    conn = sqlite3.connect('aim_api.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ----------------------------
# MODÈLES PYDANTIC
# ----------------------------
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    company: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule')
        if not re.search(r'[a-z]', v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule')
        if not re.search(r'\d', v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

class APIKeyResponse(BaseModel):
    api_key: str

class UserProfile(BaseModel):
    username: str
    email: str
    company: Optional[str]
    role: str
    created_at: str
    last_login: Optional[str]
    api_calls_today: int

class ChangePassword(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        return UserRegister.validate_password(cls, v)

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        return UserRegister.validate_password(cls, v)

class TextInput(BaseModel):
    text: str

class BatchInput(BaseModel):
    texts: List[str]

# ----------------------------
# UTILITAIRES D'AUTHENTIFICATION
# ----------------------------
def hash_password(password: str) -> str:
    """Hachage du mot de passe avec bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie le mot de passe"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crée un token JWT d'accès"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    """Crée un token JWT de rafraîchissement"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Vérifie et décode un token JWT"""
    try:
        # Vérifier si le token est révoqué
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM revoked_tokens WHERE token = ?', (token,))
            if c.fetchone():
                return None
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dépendance pour obtenir l'utilisateur courant"""
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = payload.get("sub")
    user_id = payload.get("user_id")
    
    if username is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return TokenData(username=username, user_id=user_id, role=payload.get("role"))

def get_current_admin(current_user: TokenData = Depends(get_current_user)):
    """Dépendance pour vérifier les droits admin"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions insuffisantes"
        )
    return current_user

def get_user_by_api_key(api_key: str = Header(None, alias="X-API-Key")):
    """Dépendance pour l'authentification par clé API"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API requise"
        )
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE api_key = ? AND is_active = 1', (api_key,))
        user = c.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou expirée"
        )
    
    return TokenData(username=user['username'], user_id=user['id'], role=user['role'])

def log_api_usage(user_id: int, endpoint: str, status_code: int, duration_ms: int):
    """Journalise l'utilisation de l'API"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO api_usage (user_id, endpoint, status_code, duration_ms)
                VALUES (?, ?, ?, ?)
            ''', (user_id, endpoint, status_code, duration_ms))
            conn.commit()
    except Exception as e:
        logging.error(f"Erreur lors du journal : {e}")

# ----------------------------
# LOGGING
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Logger initialisé avec succès")

# ----------------------------
# CHARGEMENT DES MODÈLES
# ----------------------------
try:
    # Charger les modèles YouTube
    youtube_models = joblib.load("model_youtube.sav") if "model_youtube.sav" in joblib.load.__code__.co_filename else {
        'lr': joblib.load("model_lr_youtube.sav"),
        'nb': joblib.load("model_nb_youtube.sav")
    }
    
    # Charger les modèles Tweets
    tweets_models = joblib.load("model_tweets.sav") if "model_tweets.sav" in joblib.load.__code__.co_filename else {
        'lr': joblib.load("model_lr_tweets.sav"),
        'nb': joblib.load("model_nb_tweets.sav")
    }
    
    # Charger les modèles Reviews
    reviews_models = joblib.load("model_reviews.sav") if "model_reviews.sav" in joblib.load.__code__.co_filename else {
        'lr': joblib.load("model_lr_reviews.sav"),
        'nb': joblib.load("model_nb_reviews.sav")
    }
    
    # Charger les vectoriseurs
    youtube_vectorizer = joblib.load("youtube_vectorizer.sav") if "youtube_vectorizer.sav" in joblib.load.__code__.co_filename else None
    tweets_vectorizer = joblib.load("tweets_vectorizer.sav") if "tweets_vectorizer.sav" in joblib.load.__code__.co_filename else None
    reviews_vectorizer = joblib.load("reviews_vectorizer.sav") if "reviews_vectorizer.sav" in joblib.load.__code__.co_filename else None
    
    logger.info("Tous les modèles chargés avec succès")
except Exception as e:
    logger.error(f"Erreur de chargement des modèles : {e}")
    # Chargement individuel en cas d'erreur
    try:
        youtube_models = {'lr': joblib.load("model_lr_youtube.sav"), 'nb': joblib.load("model_nb_youtube.sav")}
        tweets_models = {'lr': joblib.load("model_lr_tweets.sav"), 'nb': joblib.load("model_nb_tweets.sav")}
        reviews_models = {'lr': joblib.load("model_lr_reviews.sav"), 'nb': joblib.load("model_nb_reviews.sav")}
        logger.info("Modèles chargés individuellement avec succès")
    except Exception as e2:
        logger.error(f"Erreur de chargement individuel : {e2}")
        youtube_models = tweets_models = reviews_models = {'lr': None, 'nb': None}

# ----------------------------
# ENDPOINTS D'AUTHENTIFICATION
# ----------------------------
@app.post("/auth/register", response_model=Dict)
async def register(user_data: UserRegister):
    """Inscription d'un nouvel utilisateur"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Vérifier si l'utilisateur existe déjà
        c.execute('SELECT * FROM users WHERE username = ? OR email = ?', 
                 (user_data.username, user_data.email))
        if c.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom d'utilisateur ou email déjà utilisé"
            )
        
        # Hacher le mot de passe
        password_hash = hash_password(user_data.password)
        api_key = secrets.token_urlsafe(32)
        
        # Créer l'utilisateur
        c.execute('''
            INSERT INTO users (username, email, password_hash, company, api_key)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_data.username, user_data.email, password_hash, user_data.company, api_key))
        
        user_id = c.lastrowid
        conn.commit()
    
    return {
        "message": "Inscription réussie",
        "api_key": api_key,
        "user_id": user_id
    }

@app.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    """Connexion et obtention de tokens"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', 
                 (user_data.username,))
        user = c.fetchone()
    
    if not user or not verify_password(user_data.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects"
        )
    
    # Mettre à jour la dernière connexion
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                 (datetime.utcnow(), user['id']))
        conn.commit()
    
    # Créer les tokens
    token_data = {
        "sub": user['username'],
        "user_id": user['id'],
        "role": user['role']
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # en secondes
    }

@app.post("/auth/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """Rafraîchir le token d'accès"""
    payload = verify_token(refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de rafraîchissement invalide"
        )
    
    # Vérifier que l'utilisateur existe toujours
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', 
                 (payload.get("sub"),))
        user = c.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé"
        )
    
    # Créer un nouveau token d'accès
    token_data = {
        "sub": user['username'],
        "user_id": user['id'],
        "role": user['role']
    }
    
    new_access_token = create_access_token(token_data)
    
    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,  # Le refresh token reste le même
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.post("/auth/logout")
async def logout(current_user: TokenData = Depends(get_current_user)):
    """Déconnexion et révocation du token"""
    # En production, on révoquerait le token ici
    return {"message": "Déconnexion réussie"}

@app.get("/auth/profile", response_model=UserProfile)
async def get_profile(current_user: TokenData = Depends(get_current_user)):
    """Obtenir le profil de l'utilisateur"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Récupérer les informations utilisateur
        c.execute('SELECT * FROM users WHERE id = ?', (current_user.user_id,))
        user = c.fetchone()
        
        # Compter les appels API aujourd'hui
        today = datetime.utcnow().date()
        c.execute('''
            SELECT COUNT(*) as count FROM api_usage 
            WHERE user_id = ? AND DATE(timestamp) = ?
        ''', (current_user.user_id, today))
        api_calls = c.fetchone()['count']
    
    return {
        "username": user['username'],
        "email": user['email'],
        "company": user['company'],
        "role": user['role'],
        "created_at": user['created_at'],
        "last_login": user['last_login'],
        "api_calls_today": api_calls
    }

@app.post("/auth/change-password")
async def change_password(
    password_data: ChangePassword,
    current_user: TokenData = Depends(get_current_user)
):
    """Changer le mot de passe"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT password_hash FROM users WHERE id = ?', 
                 (current_user.user_id,))
        user = c.fetchone()
    
    if not user or not verify_password(password_data.current_password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe actuel incorrect"
        )
    
    # Mettre à jour le mot de passe
    new_password_hash = hash_password(password_data.new_password)
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                 (new_password_hash, current_user.user_id))
        conn.commit()
    
    return {"message": "Mot de passe changé avec succès"}

@app.post("/auth/regenerate-api-key", response_model=APIKeyResponse)
async def regenerate_api_key(current_user: TokenData = Depends(get_current_user)):
    """Régénérer la clé API"""
    new_api_key = secrets.token_urlsafe(32)
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET api_key = ? WHERE id = ?',
                 (new_api_key, current_user.user_id))
        conn.commit()
    
    return {"api_key": new_api_key}

# ----------------------------
# ENDPOINTS ADMIN
# ----------------------------
@app.get("/admin/users", dependencies=[Depends(get_current_admin)])
async def get_all_users():
    """Obtenir la liste de tous les utilisateurs (admin seulement)"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT id, username, email, company, role, is_active, 
                   created_at, last_login 
            FROM users ORDER BY created_at DESC
        ''')
        users = [dict(row) for row in c.fetchall()]
    
    return users

@app.post("/admin/users/{user_id}/toggle")
async def toggle_user_active(
    user_id: int,
    current_user: TokenData = Depends(get_current_admin)
):
    """Activer/désactiver un utilisateur (admin seulement)"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Récupérer l'état actuel
        c.execute('SELECT is_active FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )
        
        # Inverser l'état
        new_state = 0 if user['is_active'] else 1
        c.execute('UPDATE users SET is_active = ? WHERE id = ?', 
                 (new_state, user_id))
        conn.commit()
    
    return {"message": f"Utilisateur {'activé' if new_state else 'désactivé'}"}

@app.get("/admin/usage-stats")
async def get_usage_stats(
    days: int = 7,
    current_user: TokenData = Depends(get_current_admin)
):
    """Obtenir les statistiques d'utilisation (admin seulement)"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Statistiques globales
        c.execute('SELECT COUNT(*) as total_users FROM users')
        total_users = c.fetchone()['total_users']
        
        c.execute('SELECT COUNT(*) as active_users FROM users WHERE is_active = 1')
        active_users = c.fetchone()['active_users']
        
        # Utilisation par jour
        c.execute('''
            SELECT DATE(timestamp) as date, 
                   COUNT(*) as calls,
                   COUNT(DISTINCT user_id) as users
            FROM api_usage 
            WHERE timestamp >= DATE('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        ''', (f'-{days} days',))
        
        daily_stats = [dict(row) for row in c.fetchall()]
        
        # Top utilisateurs
        c.execute('''
            SELECT u.username, COUNT(a.id) as calls
            FROM api_usage a
            JOIN users u ON a.user_id = u.id
            WHERE a.timestamp >= DATE('now', ?)
            GROUP BY a.user_id
            ORDER BY calls DESC
            LIMIT 10
        ''', (f'-{days} days',))
        
        top_users = [dict(row) for row in c.fetchall()]
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "daily_stats": daily_stats,
        "top_users": top_users
    }

# ----------------------------
# FONCTIONS D'ANALYSE
# ----------------------------
def predict_with_ensemble(text, vectorizer, lr_model, nb_model):
    """Fait une prédiction en combinant Logistic Regression et Naïve Bayes"""
    if not text or not vectorizer:
        return "neutre"
    
    text_vectorized = vectorizer.transform([text])
    
    predictions = []
    confidences = []
    
    # Prédiction avec Logistic Regression
    if lr_model is not None:
        try:
            lr_pred = lr_model.predict(text_vectorized)[0]
            lr_prob = lr_model.predict_proba(text_vectorized)[0].max() if hasattr(lr_model, 'predict_proba') else 0.5
            predictions.append(lr_pred)
            confidences.append(lr_prob)
        except:
            pass
    
    # Prédiction avec Naïve Bayes
    if nb_model is not None:
        try:
            nb_pred = nb_model.predict(text_vectorized)[0]
            nb_prob = nb_model.predict_proba(text_vectorized)[0].max() if hasattr(nb_model, 'predict_proba') else 0.5
            predictions.append(nb_pred)
            confidences.append(nb_prob)
        except:
            pass
    
    if not predictions:
        return "neutre"
    
    if len(predictions) == 2 and predictions[0] == predictions[1]:
        return predictions[0]
    
    max_confidence_idx = confidences.index(max(confidences))
    return predictions[max_confidence_idx]

def detect_text_columns(df, min_avg_len: int = 20):
    cols = []
    for col in df.columns:
        if df[col].dtype == object:
            avg_len = df[col].astype(str).str.len().mean()
            if avg_len >= min_avg_len:
                cols.append(col)
    return cols

def guess_model(column_name):
    col = column_name.lower()
    if any(w in col for w in ["tweet", "post", "message", "social", "commentaire"]):
        return "tweets"
    if any(w in col for w in ["review", "avis", "feedback", "note", "commentaire_client"]):
        return "reviews"
    return "youtube"

# ----------------------------
# ENDPOINTS D'ANALYSE (PROTÉGÉS)
# ----------------------------
@app.post("/analyze/auto")
async def predict_auto(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user)
):
    """Analyse automatique d'un fichier CSV"""
    import time
    start_time = time.time()
    
    try:
        logger.info(f"Analyse demandée par {current_user.username}")
        df = pd.read_csv(file.file, sep=None, engine="python", encoding="utf-8-sig")
        logger.info(f"Fichier chargé : {df.shape[0]} lignes")
        
        text_cols = detect_text_columns(df)
        logger.info(f"Colonnes textuelles détectées : {text_cols}")
        
        results = df.copy()
        for col in text_cols:
            model_name = guess_model(col)
            
            if model_name == "youtube":
                vectorizer = youtube_vectorizer
                lr_model = youtube_models.get('lr')
                nb_model = youtube_models.get('nb')
                results[col + "_prediction"] = df[col].apply(
                    lambda x: predict_with_ensemble(str(x), vectorizer, lr_model, nb_model)
                )
                results[col + "_algo"] = "ensemble_lr_nb"
            
            elif model_name == "tweets":
                vectorizer = tweets_vectorizer
                lr_model = tweets_models.get('lr')
                nb_model = tweets_models.get('nb')
                results[col + "_prediction"] = df[col].apply(
                    lambda x: predict_with_ensemble(str(x), vectorizer, lr_model, nb_model)
                )
                results[col + "_algo"] = "ensemble_lr_nb"
            
            elif model_name == "reviews":
                vectorizer = reviews_vectorizer
                lr_model = reviews_models.get('lr')
                nb_model = reviews_models.get('nb')
                results[col + "_prediction"] = df[col].apply(
                    lambda x: predict_with_ensemble(str(x), vectorizer, lr_model, nb_model)
                )
                results[col + "_algo"] = "ensemble_lr_nb"
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_usage(current_user.user_id, "/analyze/auto", 200, duration_ms)
        
        return results.to_dict(orient="records")
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_usage(current_user.user_id, "/analyze/auto", 500, duration_ms)
        logger.error(f"Erreur d'analyse : {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/text")
async def predict_text(
    text_input: TextInput,
    current_user: TokenData = Depends(get_current_user)
):
    """Analyse d'un texte unique"""
    import time
    start_time = time.time()
    
    try:
        results = {}
        
        # YouTube
        if youtube_vectorizer and youtube_models['lr']:
            pred_youtube = predict_with_ensemble(
                text_input.text, 
                youtube_vectorizer, 
                youtube_models['lr'], 
                youtube_models['nb']
            )
            results["youtube"] = pred_youtube
        
        # Tweets
        if tweets_vectorizer and tweets_models['lr']:
            pred_tweets = predict_with_ensemble(
                text_input.text, 
                tweets_vectorizer, 
                tweets_models['lr'], 
                tweets_models['nb']
            )
            results["tweets"] = pred_tweets
        
        # Reviews
        if reviews_vectorizer and reviews_models['lr']:
            pred_reviews = predict_with_ensemble(
                text_input.text, 
                reviews_vectorizer, 
                reviews_models['lr'], 
                reviews_models['nb']
            )
            results["reviews"] = pred_reviews
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_usage(current_user.user_id, "/analyze/text", 200, duration_ms)
        
        return {"text": text_input.text, "predictions": results}
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_usage(current_user.user_id, "/analyze/text", 500, duration_ms)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/batch")
async def predict_batch(
    batch_input: BatchInput,
    model_type: str = "youtube",
    current_user: TokenData = Depends(get_current_user)
):
    """Analyse par lot de plusieurs textes"""
    import time
    start_time = time.time()
    
    try:
        results = []
        
        if model_type == "youtube":
            vectorizer = youtube_vectorizer
            lr_model = youtube_models.get('lr')
            nb_model = youtube_models.get('nb')
        elif model_type == "tweets":
            vectorizer = tweets_vectorizer
            lr_model = tweets_models.get('lr')
            nb_model = tweets_models.get('nb')
        elif model_type == "reviews":
            vectorizer = reviews_vectorizer
            lr_model = reviews_models.get('lr')
            nb_model = reviews_models.get('nb')
        else:
            raise HTTPException(status_code=400, detail="Type de modèle invalide")
        
        if not vectorizer:
            raise HTTPException(status_code=500, detail="Modèle non disponible")
        
        for text in batch_input.texts:
            prediction = predict_with_ensemble(text, vectorizer, lr_model, nb_model)
            results.append({
                "text": text,
                "prediction": prediction,
                "model": model_type
            })
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_usage(current_user.user_id, f"/analyze/batch/{model_type}", 200, duration_ms)
        
        return {"results": results}
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_usage(current_user.user_id, f"/analyze/batch/{model_type}", 500, duration_ms)
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------
# ENDPOINT API-KEY (alternative)
# ----------------------------
@app.post("/analyze/api-key/auto")
async def predict_auto_with_api_key(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_user_by_api_key)
):
    """Même fonction que /analyze/auto mais avec clé API"""
    return await predict_auto(file, current_user)

# ----------------------------
# ENDPOINTS PUBLICS
# ----------------------------
@app.get("/")
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "Bienvenue sur AIM Marketing API",
        "version": "3.0.0",
        "status": "actif",
        "documentation": "/docs",
        "authentification_requise": True
    }

@app.get("/health")
async def health_check():
    """Vérification de la santé de l'API"""
    model_status = {
        "youtube": youtube_vectorizer is not None,
        "tweets": tweets_vectorizer is not None,
        "reviews": reviews_vectorizer is not None
    }
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) as count FROM users')
        user_count = c.fetchone()['count']
    
    return {
        "status": "healthy",
        "models": model_status,
        "users": user_count,
        "timestamp": datetime.utcnow().isoformat()
    }

# ----------------------------
# CUSTOM SWAGGER UI
# ----------------------------
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{app.title} - Swagger</title>
        <link type="text/css" rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.18.2/swagger-ui.css">
        <style>
            body {{ background-color: #FFF176 !important; }}
            .swagger-ui .topbar {{ background-color: #FFD54F !important; }}
            .swagger-ui .info {{ color: #333 !important; }}
            .swagger-ui .scheme-container {{ background-color: #FFF9C4 !important; }}
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.18.2/swagger-ui-bundle.js"></script>
        <script>
            const ui = SwaggerUIBundle({{
                url: '{app.openapi_url}',
                dom_id: '#swagger-ui',
                presets: [SwaggerUIBundle.presets.apis],
                layout: "BaseLayout"
            }})
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{app.title} - Redoc</title>
        <style>
            body {{ background-color: #FFF176 !important; }}
            .menu-content {{ background-color: #FFF9C4 !important; }}
        </style>
        <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
    </head>
    <body>
        <redoc spec-url="{app.openapi_url}"></redoc>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# ----------------------------
# DÉMARRAGE
# ----------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)