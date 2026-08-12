"""
Script de diagnostic : affiche le message d'erreur COMPLET lors de la
tentative de connexion à la base, sans la troncature du traceback Alembic.

Usage : python diagnose_db_connection.py
"""

import sys

import psycopg2

from src.core.config import get_settings

settings = get_settings()

sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

print(f"Tentative de connexion à : {sync_url.split('@')[1] if '@' in sync_url else sync_url}")
print("-" * 60)

try:
    conn = psycopg2.connect(sync_url, connect_timeout=10)
    print("SUCCES : connexion établie.")
    conn.close()
except Exception as e:
    print(f"ECHEC : {type(e).__name__}")
    print(f"Message complet : {e}")
    sys.exit(1)
