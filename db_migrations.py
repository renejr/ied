# file: db_migrations.py
import sqlite3

DB_PATH = "image_editor.db"
SCHEMA_VERSION = 4

MIGRATIONS = [
    # version 1
    '''
    CREATE TABLE IF NOT EXISTS images (
        path TEXT PRIMARY KEY,
        zoom REAL DEFAULT 1.0,
        scroll_x REAL DEFAULT 0.0,
        scroll_y REAL DEFAULT 0.0,
        fit_mode TEXT DEFAULT 'fit'
    );
    CREATE TABLE IF NOT EXISTS preferences (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    INSERT OR IGNORE INTO preferences (key, value) VALUES ('schema_version', '1');
    ''',
    # version 2
    '''
    ALTER TABLE images ADD COLUMN favorito INTEGER DEFAULT 0;
    ALTER TABLE images ADD COLUMN last_opened TIMESTAMP DEFAULT (datetime('now', '-3 hours'));
    UPDATE preferences SET value = '2' WHERE key = 'schema_version';
    ''',
    # version 3
    '''
    PRAGMA foreign_keys = OFF;

    CREATE TABLE IF NOT EXISTS images_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        zoom REAL DEFAULT 1.0,
        scroll_x REAL DEFAULT 0.0,
        scroll_y REAL DEFAULT 0.0,
        fit_mode TEXT DEFAULT 'fit',
        favorito INTEGER DEFAULT 0,
        last_opened TIMESTAMP DEFAULT (datetime('now', '-3 hours')),
        criado_em TIMESTAMP DEFAULT (datetime('now', '-3 hours'))
    );

    INSERT INTO images_new (path, zoom, scroll_x, scroll_y, fit_mode, favorito, last_opened)
    SELECT path, zoom, scroll_x, scroll_y, fit_mode, favorito, last_opened FROM images;

    DROP TABLE images;
    ALTER TABLE images_new RENAME TO images;

    PRAGMA foreign_keys = ON;
    UPDATE preferences SET value = '3' WHERE key = 'schema_version';
    ''',
    # version 4
    '''
    PRAGMA foreign_keys = OFF;

    CREATE TABLE preferences_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE,
        value TEXT,
        criado_em TIMESTAMP DEFAULT (datetime('now', '-3 hours'))
    );

    INSERT INTO preferences_new (key, value)
    SELECT key, value FROM preferences;

    DROP TABLE preferences;
    ALTER TABLE preferences_new RENAME TO preferences;

    PRAGMA foreign_keys = ON;
    UPDATE preferences SET value = '4' WHERE key = 'schema_version';
    '''
]

def get_schema_version(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM preferences WHERE key = 'schema_version'")
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0

def apply_migrations():
    conn = sqlite3.connect(DB_PATH)
    current_version = get_schema_version(conn)

    for version in range(current_version + 1, SCHEMA_VERSION + 1):
        print(f"Applying migration v{version}...")
        try:
            conn.executescript(MIGRATIONS[version - 1])
            conn.commit()
        except Exception as e:
            print(f"Migration v{version} failed: {e}")
            conn.rollback()
            break

    conn.close()

if __name__ == "__main__":
    apply_migrations()
