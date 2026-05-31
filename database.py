import sqlite3
import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        if os.path.exists("/app/data"):
            return sqlite3.connect("/app/data/bot_data.db")
        return sqlite3.connect("bot_data.db")

def init_db():
    conn = get_connection()
    try:
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
                    referral_credited INTEGER DEFAULT 0,
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
                    max_user_claims INTEGER DEFAULT 1,
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
            conn.commit()
            
            # Self-healing Migration: Auto-add missing columns to Postgres
            try:
                cursor.execute(
                    "ALTER TABLE tasks ADD COLUMN max_user_claims "
                    "INTEGER DEFAULT 1"
                )
                conn.commit()
                print("[MIGRATION] Added max_user_claims to tasks table.")
            except Exception:
                conn.rollback()

            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN referral_credited "
                    "INTEGER DEFAULT 0"
                )
                conn.commit()
                print("[MIGRATION] Added referral_credited to users table.")
            except Exception:
                conn.rollback()

        else:
            # SQLite Schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0.0,
                    wallet_address TEXT,
                    referred_by INTEGER,
                    referral_credited INTEGER DEFAULT 0,
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
                    max_user_claims INTEGER DEFAULT 1,
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
            
            # Self-healing Migration: Auto-add missing columns to SQLite
            try:
                cursor.execute(
                    "ALTER TABLE tasks ADD COLUMN max_user_claims "
                    "INTEGER DEFAULT 1"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN referral_credited "
                    "INTEGER DEFAULT 0"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass
                
    finally:
        conn.close()

def execute_query(query, params=()):
    conn = get_connection()
    last_id = None
    try:
        cursor = conn.cursor()
        if DATABASE_URL:
            query = query.replace("?", "%s")
        cursor.execute(query, params)
        conn.commit()
        
        # Capture last row ID across SQL engines safely
        try:
            if DATABASE_URL and "returning" in query.lower():
                last_id = cursor.fetchone()[0]
            else:
                last_id = cursor.lastrowid
        except Exception:
            pass
    finally:
        conn.close()
    return last_id

def fetch_query(query, params=()):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if DATABASE_URL:
            query = query.replace("?", "%s")
        cursor.execute(query, params)
        results = cursor.fetchall()
    finally:
        conn.close()
    return results