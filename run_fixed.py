#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

# ========== FORÇAGE ENCODAGE ==========
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

if sys.platform == "win32":
    os.system("chcp 65001 > nul")

# Nettoyer .env problématique
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    os.remove(env_path)

# Créer .env propre
with open(env_path, 'w', encoding='ascii') as f:
    f.write('DATABASE_URL=postgresql://postgres:postgres@localhost:5432/memoire\n')

# ========== PATCH STREAMLIT ==========
import streamlit as st

# Patching de session_state avant import des dashboards
class PatchedSessionState:
    def __init__(self):
        self._state = {}
    
    def __getattr__(self, name):
        if name not in self._state:
            # Initialiser automatiquement les attributs manquants
            if name == 'db':
                # Initialiser connexion BD
                try:
                    import psycopg2
                    self._state['db'] = psycopg2.connect(
                        host="localhost",
                        database="memoire",
                        user="postgres",
                        password="postgres"
                    )
                except:
                    import sqlite3
                    self._state['db'] = sqlite3.connect(':memory:')
            else:
                self._state[name] = None
        return self._state[name]
    
    def __setattr__(self, name, value):
        if name == '_state':
            super().__setattr__(name, value)
        else:
            self._state[name] = value
    
    def __contains__(self, key):
        return key in self._state

# Appliquer le patch
if not hasattr(st, '_session_state_patched'):
    st.session_state = PatchedSessionState()
    st._session_state_patched = True

# ========== EXÉCUTER MAIN ==========
print("=" * 50)
print("Lancement avec encodage fixé et session_state patché")
print("=" * 50)

# Exécuter main.py
import runpy
runpy.run_path('main.py', run_name='__main__')