# create_admin.py
import bcrypt
import getpass

def create_admin_password():
    """Génère un hash bcrypt pour l'admin"""
    print("Création du mot de passe admin")
    password = getpass.getpass("Entrez le mot de passe pour l'admin: ")
    
    # Générer le hash
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode(), salt)
    
    print(f"\nHash bcrypt généré:")
    print(f"{hashed_password.decode()}")
    
    # Mettre à jour la base de données
    import psycopg2
    conn = psycopg2.connect(
        host="localhost",
        database="aim_platform",
        user="aim_user",
        password="aim_password"
    )
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET password_hash = %s 
        WHERE username = 'admin'
    """, (hashed_password.decode(),))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Mot de passe admin mis à jour dans la base de données!")

if __name__ == "__main__":
    create_admin_password()