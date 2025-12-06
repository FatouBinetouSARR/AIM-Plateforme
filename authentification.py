# auth.py
import streamlit as st
from api_utils import (
    page_bg_css, 
    load_users, 
    save_users, 
    hash_password, 
    validate_email, 
    validate_password, 
    check_credentials,
    change_password,
    check_first_login
)

def show_login_page():
    """Affiche la page de connexion"""
    st.markdown(page_bg_css(), unsafe_allow_html=True)
    
    st.markdown("""
    <div class="login-container">
        <h1 style="text-align: center; color: #172B4D; margin-bottom: 10px;">AIM Platform</h1>
        <p style="text-align: center; color: #6B7280; margin-bottom: 30px;">
            Analyse Marketing Intelligente
        </p>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        identifier = st.text_input("Email ou Nom d'utilisateur",
                                 placeholder="Entrez vos identifiants")
        
        password = st.text_input("Mot de passe",
                               type="password",
                               placeholder="Votre mot de passe")
        
        login_button = st.form_submit_button("Se connecter",
                                           type="primary",
                                           use_container_width=True)
        
        if login_button:
            if not identifier or not password:
                st.error("Veuillez remplir tous les champs")
            else:
                success, user_data = check_credentials(identifier, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = user_data['username']
                    st.session_state.user_info = user_data
                    
                    # Vérifier si changement de mot de passe obligatoire
                    if not user_data.get('password_changed', True):
                        st.session_state.force_password_change = True
                    
                    if user_data['role'] == 'admin':
                        st.session_state.current_page = "admin_dashboard"
                    elif user_data['role'] == 'data_analyst':
                        st.session_state.current_page = "analyst_dashboard"
                    else:
                        st.session_state.current_page = "marketing_dashboard"
                    
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect")
    
    st.markdown("""
        <div style="text-align: center; margin-top: 20px; color: #6B7280; font-size: 0.9em;">
            <p>Demandez vos identifiants à l'administrateur système</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def show_force_password_change():
    """Affiche la page de changement obligatoire de mot de passe"""
    st.markdown("""
    <div style="text-align: center; padding: 40px 20px;">
        <h1 style="color: #FF5630;">⚠️ Changement de mot de passe requis</h1>
        <p style="font-size: 1.2em; margin-bottom: 30px;">
            Pour des raisons de sécurité, vous devez changer votre mot de passe temporaire.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("change_password_form"):
        current_password = st.text_input("Mot de passe temporaire (reçu par email)", 
                                       type="password")
        new_password = st.text_input("Nouveau mot de passe", 
                                   type="password",
                                   help="8 caractères minimum, majuscule et chiffre")
        confirm_password = st.text_input("Confirmer le nouveau mot de passe", 
                                       type="password")
        
        change_button = st.form_submit_button("Changer le mot de passe", 
                                            type="primary",
                                            use_container_width=True)
        
        if change_button:
            if new_password != confirm_password:
                st.error("Les nouveaux mots de passe ne correspondent pas")
            else:
                # Appeler la fonction de changement
                success, message = change_password(
                    st.session_state.username,
                    current_password,
                    new_password
                )
                
                if success:
                    st.success("✅ Mot de passe changé avec succès !")
                    st.session_state.force_password_change = False
                    st.rerun()
                else:
                    st.error(f"❌ {message}")