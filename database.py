import sqlite3
import os
import psycopg2

# Check if PostgreSQL is available (Render/Railway), otherwise fallback to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        # Fallback to local SQLite
        if os.path.exists("/app/data"):
            return sqlite3.connect("/app/data/bot_data.db")
        return sqlite3.connect("bot_data.db")

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL Schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                wallet_address TEXT,
                referred_by BIGINT,
                check_in_count INTEGER DEFAULT 0,
                last_check_in TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                description TEXT,
                reward REAL,
                max_claims INTEGER DEFAULT 999999,
                claims_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_id INTEGER,
                proof TEXT,
                status TEXT DEFAULT 'PENDING'
            )
        ''')
    else:
        # SQLite Schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                wallet_address TEXT,
                referred_by INTEGER,
                check_in_count INTEGER DEFAULT 0,
                last_check_in TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT,
                reward REAL,
                max_claims INTEGER DEFAULT 999999,
                claims_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                proof TEXT,
                status TEXT DEFAULT 'PENDING'
            )
        ''')
        
    conn.commit()
    conn.close()

def execute_query(query, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        query = query.replace("?", "%s")
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def fetch_query(query, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        query = query.replace("?", "%s")
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results