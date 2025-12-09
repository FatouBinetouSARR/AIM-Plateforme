@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

cd "C:\Users\ADMIN PC\Documents\Mémoire master\modele"

REM Supprimer TOUS les .env problématiques
del .env 2>nul
del .env.* 2>nul

REM Créer .env en ASCII pur (pas d'accents)
echo DATABASE_URL=postgresql://postgres:postgres@localhost:5432/memoire > .env

REM Démarrer l'application
python -X utf8 main.py
pause