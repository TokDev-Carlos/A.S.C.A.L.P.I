from __future__ import annotations
import sqlite3

def next_id(conn: sqlite3.Connection, entity: str, prefix: str) -> str:
    row = conn.execute('SELECT value FROM counters WHERE entity=?', (entity,)).fetchone()
    current = int(row[0]) if row else 0
    new = current + 1
    conn.execute('INSERT INTO counters(entity,value) VALUES(?,?) ON CONFLICT(entity) DO UPDATE SET value=excluded.value', (entity,new))
    return f'{prefix}-{new:06d}'
