import sqlite3
import os

if os.path.exists("/app/data"):
    DB_FILE = "/app/data/bot_data.db"
else:
    DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table
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
    
    # Tasks table
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
    
    # Submissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            proof TEXT,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def execute_query(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def fetch_query(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results
