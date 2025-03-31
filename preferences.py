# file: preferences.py
import sqlite3
from datetime import datetime

DB_PATH = "image_editor.db"

class Preferences:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._cache = {}
        self._load_preferences()

    def _load_preferences(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM preferences")
        for key, value in cur.fetchall():
            self._cache[key] = value
        conn.close()

    def get(self, key, default=None, cast=str):
        value = self._cache.get(key, default)
        try:
            return cast(value)
        except (ValueError, TypeError):
            return default

    def set(self, key, value):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO preferences (key, value, alterado_em)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, alterado_em = excluded.alterado_em
        """, (key, str(value), now))
        conn.commit()
        conn.close()
        self._cache[key] = str(value)

# Global instance
prefs = Preferences()

# Constantes importáveis
THUMB_CLOSE_ON_SELECT = prefs.get("thumb_close_on_select", 0, int)
THUMB_WINDOW_WIDTH = prefs.get("thumb_window_width", 1024, int)
THUMB_WINDOW_HEIGHT = prefs.get("thumb_window_height", 768, int)
THUMB_WINDOW_X = prefs.get("thumb_window_x", 0, int)
THUMB_WINDOW_Y = prefs.get("thumb_window_y", 0, int)
THUMB_SIZE = prefs.get("thumb_size", 350, int)
THUMB_SHOW_INFO = prefs.get("thumb_show_info", 1, int)
THUMB_SORT_BY_PATH = prefs.get("thumb_sort_by_path", 0, int)
THUMB_AUTO_SCROLL = prefs.get("thumb_auto_scroll", 0, int)
thumb_STRETCH_SMALL = prefs.get("thumb_stretch_small", 0, int)
THUMB_BORDER = prefs.get("thumb_border", 0, int)
THUMB_USE_RESAMPLE = prefs.get("thumb_use_resample", 0, int)

THUMB_CLOSE_ON_SELECT_BOOL = bool(THUMB_CLOSE_ON_SELECT)
THUMB_SHOW_INFO_BOOL = bool(THUMB_SHOW_INFO)
THUMB_SORT_BY_PATH_BOOL = bool(THUMB_SORT_BY_PATH)
THUMB_AUTO_SCROLL_BOOL = bool(THUMB_AUTO_SCROLL)

# Status para debug visual
print(f"[Miniaturas] Tamanho: {THUMB_SIZE}px")
