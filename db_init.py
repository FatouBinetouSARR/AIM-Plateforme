import streamlit as st
import psycopg2
import sqlite3
import os

def init_database():
    """Initialise la connexion à la base de données"""
    if 'db' not in st.session_state:
        try:
            # Essayer PostgreSQL d'abord
            conn = psycopg2.connect(
                host="localhost",
                database="memoire",
                user="postgres",
                password="postgres"
            )
            st.session_state.db = conn
            st.session_state.db_type = "postgresql"
            print("Connexion PostgreSQL établie")
        except Exception as e:
            print(f"PostgreSQL échoué: {e}, bascule vers SQLite")
            # Fallback SQLite
            conn = sqlite3.connect('memoire_fallback.db')
            st.session_state.db = conn
            st.session_state.db_type = "sqlite"
    
    return st.session_state.db

# Dans main.py, importez et appelez init_database() au début