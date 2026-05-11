import sqlite3

def check_cache():
    try:
        conn = sqlite3.connect("cache/search_cache.db")
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM cache")
        rows = cursor.fetchall()
        print(f"Total cache entries: {len(rows)}")
        for row in rows:
            print(f" - {row[0]}")
        conn.close()
    except Exception as e:
        print(f"Error checking cache: {e}")

if __name__ == "__main__":
    check_cache()
