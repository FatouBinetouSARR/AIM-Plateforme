import psycopg2
import bcrypt
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "aim_platform"),
    user=os.getenv("DB_USER", "aim_user"),
    password=os.getenv("DB_PASSWORD", "aim_password"),
    port=os.getenv("DB_PORT", "5432")
)

cursor = conn.cursor(cursor_factory=RealDictCursor)

# Récupérer tous les utilisateurs
cursor.execute("SELECT id, username, password_hash FROM users")
users = cursor.fetchall()

for user in users:
    ph = user["password_hash"] or ""

    # Si ce n’est PAS un vrai hash bcrypt
    if not ph.startswith("$2"):
        # Mot de passe temporaire
        new_password = user["username"] + "123"

        # Hash bcrypt
        new_hash = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        cursor.execute(
            "UPDATE users SET password_hash=%s WHERE id=%s",
            (new_hash, user["id"])
        )

        print(f"✅ {user['username']} → nouveau mot de passe : {new_password}")

conn.commit()
cursor.close()
conn.close()

print("🔐 Re-hash terminé avec succès")
