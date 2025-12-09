import streamlit as st

# Comptes autorisés
authorized_users = {
    "admin": "admin123",
    "analyst": "analyst123",
    "marketing": "marketing123",
    "support": "support123"
}

def login_page():

    st.title("🔐 Connexion AIM Analytics")

    st.write("Utilisez un des comptes ci-dessous :")

    with st.container():
        st.markdown("""
        - **admin / admin123**  
        - **analyst / analyst123**  
        - **marketing / marketing123**  
        - **support / support123**
        """)

    st.write("---")

    username = st.text_input("Nom d'utilisateur")
    password = st.text_input("Mot de passe", type="password")

    login_button = st.button("Se connecter")

    if login_button:
        if username in authorized_users and authorized_users[username] == password:
            st.session_state["authenticated"] = True
            st.session_state["role"] = username
            st.success("Connexion réussie 🎉")
            st.rerun()
        else:
            st.error("❌ Identifiants incorrects")


def dashboard_page():
    st.success(f"Bienvenue sur le Dashboard, rôle : **{st.session_state['role']}** 📌")
    st.write("🎯 Ici tu vas afficher tes graphiques, KPIs etc.")


# --- Gestion Navigation ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"] is False:
    login_page()
else:
    dashboard_page()
