# file: viewer_state.py
import sqlite3
import json
from typing import Optional, Tuple, Dict, Any

DB_PATH = "image_editor.db"

def load_view_state(image_path: str) -> Optional[Tuple[float, float, float, str]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT zoom, scroll_x, scroll_y, fit_mode FROM images WHERE path = ?", (image_path,))
    row = cur.fetchone()
    conn.close()
    return row if row else None

def save_view_state(image_path: str, zoom: float, scroll_x: float, scroll_y: float, fit_mode: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO images (path, zoom, scroll_x, scroll_y, fit_mode)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            zoom = excluded.zoom,
            scroll_x = excluded.scroll_x,
            scroll_y = excluded.scroll_y,
            fit_mode = excluded.fit_mode
    """, (image_path, zoom, scroll_x, scroll_y, fit_mode))
    conn.commit()
    conn.close()

def toggle_favorite(image_path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT favorito FROM images WHERE path = ?", (image_path,))
    row = cur.fetchone()
    new_value = 0 if row and row[0] else 1
    cur.execute("UPDATE images SET favorito = ? WHERE path = ?", (new_value, image_path))
    conn.commit()
    conn.close()
    return new_value

def get_view_state_json(image_path: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT path, zoom, scroll_x, scroll_y, fit_mode, favorito FROM images WHERE path = ?", (image_path,))
    row = cur.fetchone()
    conn.close()
    if row:
        keys = ["path", "zoom", "scroll_x", "scroll_y", "fit_mode", "favorito"]
        return json.dumps(dict(zip(keys, row)), indent=2)
    return json.dumps({})
