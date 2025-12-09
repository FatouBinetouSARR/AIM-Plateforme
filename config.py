import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "aim_platform"),
    "user": os.getenv("DB_USER", "aim_user"),
    "password": os.getenv("DB_PASSWORD", "aim_password"),
    "port": os.getenv("DB_PORT", "5432")
}