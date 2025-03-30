# file: db.py
import sqlite3
from typing import Optional, Tuple
from db_migrations import apply_migrations

DB_PATH = "image_editor.db"

def init_db():
    apply_migrations()

def load_global_preferences(key: str = "last_fit_mode") -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM preferences WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def save_global_preferences(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("REPLACE INTO preferences (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def update_last_opened(image_path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE images SET last_opened = datetime('now', '-3 hours')
        WHERE path = ?
    """, (image_path,))
    conn.commit()
    conn.close()
