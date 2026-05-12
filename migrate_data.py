import sqlite3
import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DB_PATH = "Data/drugs.db"

def migrate():
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"Error: {SQLITE_DB_PATH} not found.")
        return

    print(f"Connecting to legacy SQLite database: {SQLITE_DB_PATH}...")
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_cursor = sqlite_conn.cursor()

    print("Connecting to PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"PostgreSQL connection error: {e}")
        return

    # Fetch data from SQLite
    print("Fetching data from SQLite 'processed_drugs' table...")
    sqlite_cursor.execute("SELECT drug_name, generic_name, therapeutic_class, dosage_form, strength, indication, plan_id, source_pdf, page_number, extracted_at FROM processed_drugs")
    rows = sqlite_cursor.fetchall()
    print(f"Found {len(rows)} records to migrate.")

    # Prepare for insert
    insert_query = """
    INSERT INTO processed_drugs 
    (drug_name, generic_name, therapeutic_class, dosage_form, strength, indication, plan_id, source_pdf, page_number, created_at, is_insured, safety_score)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    print("Migrating data to PostgreSQL...")
    count = 0
    batch_size = 500
    batch_data = []

    for row in rows:
        # Convert row to list for mutation
        data = list(row)
        
        # Handle extracted_at timestamp
        try:
            if data[9]:
                dt = datetime.strptime(data[9], '%Y-%m-%d %H:%M:%S')
            else:
                dt = datetime.now()
        except:
            dt = datetime.now()
        data[9] = dt
        
        # Add default values for is_insured and safety_score
        data.append(True)  # is_insured
        data.append(100)   # safety_score
        
        batch_data.append(tuple(data))
        count += 1
        
        if len(batch_data) >= batch_size:
            pg_cursor.executemany(insert_query, batch_data)
            pg_conn.commit()
            print(f" Migrated {count}/{len(rows)} records...")
            batch_data = []

    # Final batch
    if batch_data:
        pg_cursor.executemany(insert_query, batch_data)
        pg_conn.commit()
        print(f" Migrated {count}/{len(rows)} records.")

    print("\n✅ Migration complete!")
    print(f"Total records migrated: {count}")

    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    migrate()
