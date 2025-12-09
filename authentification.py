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
        <div style="text-align: center; margin-bottom: 40px;">
            <h1 style="color: #172B4D; margin-bottom: 10px;">🎯 AIM Platform</h1>
            <p style="color: #6B7280; font-size: 1.1em;">
                Analyse Marketing Intelligente
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form", clear_on_submit=False):
                st.markdown("<h3 style='text-align: center; color: #344563;'>Connexion</h3>", 
                          unsafe_allow_html=True)
                
                identifier = st.text_input(
                    "**Email ou Nom d'utilisateur**",
                    placeholder="exemple@entreprise.com ou votre_nom_utilisateur",
                    key="login_identifier"
                )
                
                password = st.text_input(
                    "**Mot de passe**",
                    type="password",
                    placeholder="Votre mot de passe sécurisé",
                    key="login_password"
                )
                
                # Option "Mot de passe oublié"
                st.markdown(
                    '<p style="text-align: right; font-size: 0.9em; margin-top: -10px;">'
                    '<a href="#" style="color: #0052CC; text-decoration: none;">Mot de passe oublié ?</a>'
                    '</p>',
                    unsafe_allow_html=True
                )
                
                login_button = st.form_submit_button(
                    "**Se connecter**",
                    type="primary",
                    use_container_width=True,
                    help="Cliquez pour vous connecter à la plateforme"
                )
    
    if login_button:
        with st.spinner("Vérification de vos identifiants..."):
            if not identifier.strip():
                st.error("❌ Veuillez saisir votre identifiant")
                st.stop()
            
            if not password.strip():
                st.error("❌ Veuillez saisir votre mot de passe")
                st.stop()
            
            success, user_data = check_credentials(identifier, password)
            
            if success:
                # Mettre à jour la session
                st.session_state.update({
                    'logged_in': True,
                    'username': user_data['username'],
                    'user_info': user_data,
                    'user_role': user_data['role'],
                    'login_time': st.session_state.get('login_time', st.session_state.get('_last_report_step', ''))
                })
                
                # Vérifier si changement de mot de passe obligatoire
                if not user_data.get('password_changed', True):
                    st.session_state['force_password_change'] = True
                    st.info("🔒 Un changement de mot de passe est requis pour continuer")
                
                # Déterminer la page de destination
                role_pages = {
                    'admin': "admin_dashboard",
                    'data_analyst': "analyst_dashboard",
                    'marketing': "marketing_dashboard"
                }
                
                st.session_state['current_page'] = role_pages.get(
                    user_data['role'], 
                    "marketing_dashboard"
                )
                
                st.success(f"✅ Connexion réussie ! Bienvenue {user_data.get('full_name', user_data['username'])}")
                
                # Petit délai pour afficher le message de succès
                import time
                time.sleep(1)
                st.rerun()
            else:
                st.error("🔐 Identifiant ou mot de passe incorrect")
                
                # Suggestions d'aide
                with st.expander("Besoin d'aide ?"):
                    st.markdown("""
                    **Problèmes courants :**
                    - Vérifiez la casse (majuscules/minuscules)
                    - Vérifiez les espaces avant/après
                    - Assurez-vous que votre compte est actif
                    
                    **Contact :**
                    - Administrateur système : admin@entreprise.com
                    - Support : support@entreprise.com
                    """)
    
    # Pied de page
    st.markdown("""
        <div style="text-align: center; margin-top: 60px; color: #6B7280; font-size: 0.9em;">
            <hr style="border: none; height: 1px; background-color: #E5E7EB; margin: 20px 0;">
            <p>
                <strong>Première connexion ?</strong><br>
                Demandez vos identifiants à l'administrateur système
            </p>
            <p style="font-size: 0.8em; margin-top: 10px;">
                © 2024 AIM Platform • Version 2.0
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def show_force_password_change():
    """Affiche la page de changement obligatoire de mot de passe"""
    st.markdown(page_bg_css(), unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; padding: 30px 20px 40px;">
        <div style="background: linear-gradient(135deg, #FF5630 0%, #FF7452 100%); 
                    color: white; 
                    padding: 25px; 
                    border-radius: 12px;
                    margin-bottom: 30px;
                    box-shadow: 0 4px 12px rgba(255, 86, 48, 0.2);">
            <h1 style="margin: 0;">🔒 Changement de mot de passe requis</h1>
            <p style="font-size: 1.2em; margin-top: 10px;">
                Pour des raisons de sécurité, vous devez modifier votre mot de passe temporaire.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Instructions
    with st.expander("📋 Instructions de sécurité", expanded=True):
        st.markdown("""
        **Exigences pour votre nouveau mot de passe :**
        - Minimum 8 caractères
        - Au moins une majuscule (A-Z)
        - Au moins un chiffre (0-9)
        - Au moins un caractère spécial (!@#$%^&*)
        
        **Recommandations :**
        - N'utilisez pas de mots courants
        - Évitez les informations personnelles
        - Utilisez une phrase unique
        """)
    
    # Formulaire de changement
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("change_password_form", clear_on_submit=True):
                st.markdown("<h3 style='text-align: center;'>Nouveau mot de passe</h3>", 
                          unsafe_allow_html=True)
                
                current_password = st.text_input(
                    "**Mot de passe temporaire actuel**",
                    type="password",
                    placeholder="Saisissez le mot de passe reçu par email",
                    help="Le mot de passe temporaire fourni par l'administrateur"
                )
                
                st.markdown("---")
                
                new_password = st.text_input(
                    "**Nouveau mot de passe**",
                    type="password",
                    placeholder="Créez un mot de passe sécurisé",
                    help="Doit respecter les exigences de sécurité ci-dessus"
                )
                
                # Indicateur de force du mot de passe
                if new_password:
                    strength = "Faible"
                    color = "#FF5630"
                    
                    if len(new_password) >= 8:
                        if any(c.isupper() for c in new_password) and any(c.isdigit() for c in new_password):
                            strength = "Fort"
                            color = "#36B37E"
                        else:
                            strength = "Moyen"
                            color = "#FFAB00"
                    
                    st.markdown(
                        f'<p style="font-size: 0.9em; color: {color}; margin-top: -10px;">'
                        f'Force du mot de passe : <strong>{strength}</strong></p>',
                        unsafe_allow_html=True
                    )
                
                confirm_password = st.text_input(
                    "**Confirmer le nouveau mot de passe**",
                    type="password",
                    placeholder="Resaisissez votre nouveau mot de passe"
                )
                
                # Boutons
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    cancel_btn = st.form_submit_button(
                        "Annuler",
                        use_container_width=True,
                        type="secondary"
                    )
                
                with col_btn2:
                    change_button = st.form_submit_button(
                        "**Changer le mot de passe**",
                        type="primary",
                        use_container_width=True
                    )
                
                if change_button:
                    # Validation
                    if not all([current_password, new_password, confirm_password]):
                        st.error("❌ Veuillez remplir tous les champs")
                        st.stop()
                    
                    if new_password != confirm_password:
                        st.error("❌ Les mots de passe ne correspondent pas")
                        st.stop()
                    
                    # Validation de la force du mot de passe
                    validation_result = validate_password(new_password)
                    if not validation_result[0]:
                        st.error(f"❌ {validation_result[1]}")
                        st.stop()
                    
                    # Vérification que le nouveau mot de passe est différent de l'ancien
                    if current_password == new_password:
                        st.error("❌ Le nouveau mot de passe doit être différent de l'ancien")
                        st.stop()
                    
                    # Appeler la fonction de changement
                    success, message = change_password(
                        st.session_state.username,
                        current_password,
                        new_password
                    )
                    
                    if success:
                        st.success("✅ Mot de passe changé avec succès !")
                        st.balloons()
                        
                        # Mettre à jour la session
                        st.session_state.force_password_change = False
                        st.session_state.user_info['password_changed'] = True
                        
                        # Redirection après succès
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ Échec du changement : {message}")
                        
                        # Aide supplémentaire
                        if "incorrect" in message.lower():
                            with st.expander("🆘 Aide supplémentaire"):
                                st.markdown("""
                                **Si vous avez oublié votre mot de passe temporaire :**
                                1. Contactez votre administrateur système
                                2. Demandez une réinitialisation de mot de passe
                                3. Vérifiez vos emails (y compris les spams)
                                """)
    
    # Message de pied de page
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; padding: 20px; background-color: #F4F5F7; border-radius: 8px;">
        <p style="color: #6B7280; font-size: 0.9em;">
            <strong>Important :</strong> Votre session sera sécurisée après ce changement.<br>
            Vous serez redirigé automatiquement vers votre tableau de bord.
        </p>
    </div>
    """, unsafe_allow_html=True)

# Fonction supplémentaire pour la déconnexion
def logout_user():
    """Déconnecte l'utilisateur et nettoie la session"""
    keys_to_keep = ['_last_report_step']  # Conserver certaines clés si nécessaire
    
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
    
    st.session_state['logged_in'] = False
    st.session_state['current_page'] = "login"
    st.success("Déconnexion réussie !")
    st.rerun()

# Fonction pour vérifier l'authentification
def check_auth():
    """Vérifie si l'utilisateur est authentifié, redirige sinon"""
    if not st.session_state.get('logged_in', False):
        st.session_state.current_page = "login"
        st.rerun()
    
    if st.session_state.get('force_password_change', False):
        show_force_password_change()
        st.stop()