import sqlite3
import os

db_path = r"C:\Users\veerg\AppData\Local\arb\auto-resume-builder\Cache\arb_cache.sqlite"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT namespace, key_hash, payload FROM cache WHERE namespace = 'llm_facts'")
rows = c.fetchall()

print(f"Found {len(rows)} cached facts")
for row in rows:
    print(f"Hash: {row[1]}")
    print(f"Payload: {row[2][:200]}...")
    print("---")
