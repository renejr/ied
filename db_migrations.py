# file: db_migrations.py
import sqlite3

DB_PATH = "image_editor.db"
SCHEMA_VERSION = 11  # Updated from 10 to 11

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
    ''',
    # version 5 - Insert thumbnail preferences defaults
    '''
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_close_on_select', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_use_resample', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_size', '350', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_stretch_small', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_border', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_auto_scroll', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_sort_by_path', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_show_info', '1', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_show_common_shell', '1', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_warn_on_esc', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_try_exif', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_focus_tree_on_click', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_text_template', '$DSF $X\n$W x $H pixels\n$B bpp\n$S\n$T\n$E$E63667', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_mrud_count', '30', datetime('now', '-3 hours'));
    UPDATE preferences SET value = '5' WHERE key = 'schema_version';
    ''',
    # version 6 - Save thumbnail window position/size preferences
    '''
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_window_width', '1024', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_window_height', '768', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_window_x', '0', datetime('now', '-3 hours'));
    INSERT OR IGNORE INTO preferences (key, value, criado_em) VALUES ('thumb_window_y', '0', datetime('now', '-3 hours'));
    UPDATE preferences SET value = '6' WHERE key = 'schema_version';
    ''',
    # version 7 - add alterado_em column
    '''
    PRAGMA foreign_keys = OFF;

    CREATE TABLE preferences_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE,
        value TEXT,
        criado_em TIMESTAMP DEFAULT (datetime('now', '-3 hours')),
        alterado_em TIMESTAMP DEFAULT (datetime('now', '-3 hours'))
    );

    INSERT INTO preferences_new (id, key, value, criado_em, alterado_em)
    SELECT id, key, value, criado_em, datetime('now', '-3 hours') FROM preferences;

    DROP TABLE preferences;
    ALTER TABLE preferences_new RENAME TO preferences;

    PRAGMA foreign_keys = ON;
    UPDATE preferences SET value = '7' WHERE key = 'schema_version';
    ''',
    
    # version 8 - add thumbnail background color preferences
    '''
    INSERT OR IGNORE INTO preferences (key, value, criado_em, alterado_em) 
    VALUES ('thumb_background_color', '#FFFFFF', datetime('now', '-3 hours'), datetime('now', '-3 hours'));
    
    INSERT OR IGNORE INTO preferences (key, value, criado_em, alterado_em) 
    VALUES ('thumb_window_background_color', '#FFFFFF', datetime('now', '-3 hours'), datetime('now', '-3 hours'));
    
    UPDATE preferences SET value = '8' WHERE key = 'schema_version';
    ''',
    # version 9 - Add thumbnail color and text template preferences
    '''
    INSERT OR IGNORE INTO preferences (key, value, criado_em, alterado_em) 
    VALUES ('thumb_border_color', '#000000', datetime('now', '-3 hours'), datetime('now', '-3 hours'));

    INSERT OR IGNORE INTO preferences (key, value, criado_em, alterado_em) 
    VALUES ('thumb_text_color', '#000000', datetime('now', '-3 hours'), datetime('now', '-3 hours'));

    INSERT OR IGNORE INTO preferences (key, value, criado_em, alterado_em) 
    VALUES ('thumb_text_template', '$DSF $X\\n$W x $H pixels\\n$B bpp\\n$S\\n$T\\n$E$E63667', datetime('now', '-3 hours'), datetime('now', '-3 hours'));

    UPDATE preferences SET value = '9' WHERE key = 'schema_version';
    ''',
    
    # version 10 - Add imagens_criadas table for storing created images
    '''
    CREATE TABLE IF NOT EXISTS imagens_criadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fonte VARCHAR(250) NOT NULL,
        img_base64 LONGTEXT NOT NULL,
        data_criacao TIMESTAMP DEFAULT (datetime('now', '-3 hours'))
    );

    UPDATE preferences SET value = '10' WHERE key = 'schema_version';
    ''',
    # version 11
    '''
    -- Tabela para armazenar histórico de edições
    CREATE TABLE IF NOT EXISTS history_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id INTEGER,
        action_type TEXT NOT NULL,
        action_data BLOB,
        timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        description TEXT,
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
    );
    
    -- Tabela para armazenar pontos de restauração
    CREATE TABLE IF NOT EXISTS restoration_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        image_data BLOB NOT NULL,
        timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        description TEXT,
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
    );
    
    -- Tabela para armazenar a posição atual no histórico para cada imagem
    CREATE TABLE IF NOT EXISTS history_state (
        image_id INTEGER PRIMARY KEY,
        current_position INTEGER DEFAULT 0,
        max_position INTEGER DEFAULT 0,
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
    );
    
    -- Atualiza a versão do schema
    UPDATE preferences SET value = '11' WHERE key = 'schema_version';
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