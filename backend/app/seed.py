from app.db import connect

WISH_COLUMNS = [
    ("target_amount", "ALTER TABLE wishes ADD COLUMN target_amount REAL"),
    ("target_snapshot", "ALTER TABLE wishes ADD COLUMN target_snapshot REAL"),
    ("pledged_total", "ALTER TABLE wishes ADD COLUMN pledged_total REAL NOT NULL DEFAULT 0"),
    ("pledged_snapshot", "ALTER TABLE wishes ADD COLUMN pledged_snapshot REAL"),
]

def migrate(c):
    """Idempotent ALTERs so DBs created before chip-in keep their data."""
    cols = {r["name"] for r in c.execute("PRAGMA table_info(wishes)")}
    for name, ddl in WISH_COLUMNS:
        if name not in cols:
            c.execute(ddl)
    c.execute("""
    CREATE TABLE IF NOT EXISTS chipins(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      wish_id INTEGER NOT NULL,
      backer TEXT NOT NULL,
      amount REAL NOT NULL,
      created_at TEXT NOT NULL
    );
    """)

def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS wishes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, note TEXT, status TEXT,
      claimer TEXT, claimed_at TEXT, expires_at TEXT, data_quality TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    migrate(c)
    if c.execute("SELECT COUNT(*) c FROM wishes").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO wishes(title,note,status,claimer,claimed_at,expires_at,data_quality,target_amount) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                ("机械键盘", "红轴", "open", None, None, None, "clean", None),
                ("围巾", "羊毛", "open", None, None, None, "clean", None),
                ("降噪耳机", "大家凑个份子", "open", None, None, None, "clean", 200.0),
                ("脏愿望-空标题", "", "open", None, None, None, "dirty", None),
                ("过期锁样例", "应被TTL释放", "claimed", "ghost", "2020-01-01T00:00:00+00:00",
                 "2020-01-01T01:00:00+00:00", "dirty", 100.0),
            ],
        )
        c.execute("INSERT INTO settings(key,value) VALUES ('ttl_seconds','86400')")
        c.execute("INSERT INTO settings(key,value) VALUES ('wall_title','暖粉愿望墙')")
        c.commit()
    c.close()
