@echo off
echo ============================================
echo   FIX ENCODING - CORRECTION UTF-8 FORCÉE
echo ============================================
echo.

REM 1. Changer le code page de Windows en UTF-8
chcp 65001 > nul
echo [OK] Code page change en UTF-8 (65001)

REM 2. Forcer les variables d'environnement Python UTF-8
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo [OK] Variables Python UTF-8 definies

REM 3. Nettoyer les anciens fichiers .env
if exist .env (
    echo [INFO] Suppression ancien .env
    del .env
)

REM 4. Créer un nouveau .env PROPRE
echo DATABASE_URL=postgresql://postgres:postgres@localhost:5432/memoire > .env
echo [OK] Fichier .env cree

REM 5. Vérifier PostgreSQL
echo.
echo Verification de PostgreSQL...
net start | findstr /i postgresql > nul
if %errorlevel% equ 0 (
    echo [OK] PostgreSQL est demarre
) else (
    echo [ATTENTION] PostgreSQL n'est pas demarre
    echo Essayez de le demarrer avec: net start postgresql-x64-18
)

REM 6. Exécuter l'application avec UTF-8 forcé
echo.
echo ============================================
echo   LANCEMENT DE L'APPLICATION
echo ============================================
echo.
python -X utf8 main.py

if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   L'APPLICATION S'EST ARRETEE AVEC ERREUR
    echo ============================================
    pause
)