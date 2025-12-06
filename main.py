# main.py
import streamlit as st

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="AIM Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== VARIABLES DE SESSION ====================
def initialize_session_state():
    """Initialise toutes les variables de session"""
    defaults = {
        'logged_in': False,
        'username': None,
        'user_info': None,
        'force_password_change': False,
        'current_page': "login",
        'admin_data': None,
        'analyst_data': None,
        'marketing_data': None,
        'current_file': None,
        'aim_config': None,  # Sera chargé plus tard
        'analysis_results': {},
        'recommendations': []
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==================== APPLICATION PRINCIPALE ====================
def main():
    """Application principale"""
    # Importer les modules ici pour éviter les problèmes avec set_page_config
    from authentification import show_login_page, show_force_password_change
    from dashboard_admin import show_admin_dashboard
    from dashboard_data_analyst import show_analyst_dashboard
    from dashboard_manager_marketing import show_marketing_dashboard
    from api_utils import load_aim_config  # Note: j'ai changé utils en api_utils car c'est là que load_aim_config est défini
    
    initialize_session_state()
    
    # Charger la configuration AIM si ce n'est pas déjà fait
    if st.session_state.aim_config is None:
        st.session_state.aim_config = load_aim_config()
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        # Vérifier si changement de mot de passe obligatoire
        if st.session_state.get('force_password_change', False):
            show_force_password_change()
            return  # Ne pas afficher le dashboard
        
        user_role = st.session_state.user_info.get('role', 'marketing')
        
        if user_role == 'admin':
            show_admin_dashboard()
        elif user_role == 'data_analyst':
            show_analyst_dashboard()
        else:
            show_marketing_dashboard()

if __name__ == "__main__":
    main()