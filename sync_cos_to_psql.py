import os
import csv
import sys
import getpass
import psycopg2
from qcloud_cos import CosConfig, CosS3Client

# Import your existing config for COS credentials
try:
    import config
except ImportError:
    print("Error: Could not import 'config.py'. Make sure it exists in the same directory.")
    sys.exit(1)

# --- Configuration ---
# DB Connection Config
# NOTE: Requires SSH Tunnel: ssh -L 5435:localhost:5435 -i ~/wandou_key.pem ubuntu@140.143.246.128
DB_HOST = "127.0.0.1"
DB_PORT = ""
DB_NAME = ""
DB_USER = ""
# DB_PASS will be prompted or read from env var

# Target Table
TABLE_NAME = "zh_journals.zh_journal_metadata"

# Project Root
PROJECT_ROOT = "/Users/oushu/Desktop/豌豆数据源crawler"

def get_cos_client():
    """Initialize COS client using config.py credentials"""
    cos_config = CosConfig(
        Region=config.region_name,
        SecretId=config.access_key,
        SecretKey=config.secret_key,
    )
    return CosS3Client(cos_config)

def get_db_connection():
    """Connect to PostgreSQL"""
    
    # Get password from Env Var or Prompt
    # db_pass = os.environ.get('DB_PASS', 'oushu123')
    db_pass = "Oushu666" # Force hardcode for debugging
    
    if not db_pass:
        try:
            db_pass = getpass.getpass(prompt=f"Enter password for user '{DB_USER}': ")
        except Exception:
            # Fallback for non-interactive environments
            print("Error: DB_PASS environment variable not set and cannot prompt for password.")
            sys.exit(1)

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=db_pass
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"\n[DB Connection Error] Could not connect to {DB_HOST}:{DB_PORT}")
        print(f"Details: {e}")
        print("\nPossible solutions:")
        print("1. Check if the SSH tunnel is running.")
        print("2. Verify the DB_PASS and DB_USER in this script.")
        sys.exit(1)

def create_table_if_not_exists(cursor):
    """Create the target table if it doesn't exist"""
    # Columns: id (auto), article_id, title, author, year, issue, volume, pdf_url, cos_name
    print(f"Checking table '{TABLE_NAME}'...")
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id SERIAL PRIMARY KEY,
        article_id VARCHAR(255),
        title TEXT,
        author TEXT,
        year VARCHAR(50),
        issue VARCHAR(50),
        volume VARCHAR(50),
        pdf_url TEXT,
        cos_name TEXT,
        source TEXT  
    );
    """
    cursor.execute(create_sql)
    print("Table check complete.")

def parse_cos_filename(filename):
    """
    Parse '中华细胞与干细胞杂志（电子版）_12062.pdf' 
    Returns (journal_name, article_id)
    """
    if not filename.endswith('.pdf'):
        return None, None
    
    # Remove extension
    name_no_ext = filename[:-4]
    
    # Find the last underscore
    last_underscore_idx = name_no_ext.rfind('_')
    if last_underscore_idx == -1:
        return None, None
    
    journal_name = name_no_ext[:last_underscore_idx]
    article_id = name_no_ext[last_underscore_idx+1:]
    
    return journal_name, article_id

def load_csv_data(journal_name):
    """
    Load CSV data for a specific journal.
    Returns a dict: {article_id: row_dict}
    """
    csv_path = os.path.join(PROJECT_ROOT, journal_name, "all_pdfs.csv")
    
    if not os.path.exists(csv_path):
        print(f"  [Warn] CSV not found: {csv_path}")
        return {}
        
    data_map = {}
    try:
        # Try utf-8-sig first (common for Excel CSVs)
        encoding = 'utf-8-sig'
        rows = []
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except UnicodeDecodeError:
            # Fallback to GBK
            with open(csv_path, 'r', encoding='gbk') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        
        for row in rows:
            # Clean keys (remove BOM or spaces)
            clean_row = {k.strip(): v for k, v in row.items() if k}
            if 'article_id' in clean_row:
                data_map[clean_row['article_id']] = clean_row
                
    except Exception as e:
        print(f"  [Error] Failed reading CSV {csv_path}: {e}")
        
    return data_map

def main():
    print("=== Starting Sync Process ===")
    
    # 1. Initialize Connections
    cos_client = get_cos_client()
    conn = get_db_connection()
    cur = conn.cursor()
    
    # create_table_if_not_exists(cur)
    conn.commit()
    
    # --- Deduplication: Load existing cos_names ---
    print("Loading existing records for deduplication...")
    cur.execute(f"SELECT cos_name FROM {TABLE_NAME}")
    existing_files = set(row[0] for row in cur.fetchall())
    print(f"Found {len(existing_files)} existing records in DB.")
    
    # 2. List COS Files
    print(f"\nListing files in COS bucket: {config.bucket_name}...")
    cos_files = []
    marker = ""
    while True:
        # Using prefix from config if available, else root
        prefix = getattr(config, 'COS_PREFIX', '')
        response = cos_client.list_objects(
            Bucket=config.bucket_name,
            Prefix=prefix, 
            Marker=marker
        )
        
        if 'Contents' in response:
            cos_files.extend(response['Contents'])
            
        if response['IsTruncated'] == 'false':
            break
        marker = response['NextMarker']
        
    print(f"Total objects found in COS: {len(cos_files)}")
    
    # 3. Process Files
    inserted_count = 0
    skipped_count = 0
    journal_cache = {} # Cache CSV data: {journal_name: {article_id: row}}
    
    print("\nProcessing files (FULL SYNC MODE)...")
    
    total_scanned = 0
    for file_obj in cos_files:
        total_scanned += 1
        if total_scanned % 1000 == 0:
            print(f"  ...Scanned {total_scanned}/{len(cos_files)} files...")

        # LIMIT REMOVED for full sync
        # if inserted_count >= 10:
        #    print("\nReached test limit of 10 records. Stopping.")
        #    break

        cos_key = file_obj['Key']
        filename = os.path.basename(cos_key)
        
        # Skip if already exists in DB
        if filename in existing_files:
            # Optional: print debug info
            # print(f"  [Skip] Already exists: {filename}")
            skipped_count += 1
            continue

        # Filter: Must contain "中华烧伤与创面修复杂志" and be a PDF
        if "中国全科医学" not in filename or not filename.endswith('.pdf'):
            continue
            
        journal_name, article_id = parse_cos_filename(filename)
        if not journal_name or not article_id:
            continue
            
        # Load CSV data if not in cache
        if journal_name not in journal_cache:
            journal_cache[journal_name] = load_csv_data(journal_name)
            
        journal_data = journal_cache[journal_name]
        
        if article_id not in journal_data:
            # Only print warning if we haven't warned about this journal/article combo yet
            # (Reducing noise)
            # print(f"  [Skip] ID {article_id} not found in CSV for {journal_name}")
            skipped_count += 1
            continue
            
        row = journal_data[article_id]
        
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_NAME} 
                (article_id, title, author, year, issue, volume, pdf_url, cos_name, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row.get('article_id', ''),
                row.get('title', ''),
                row.get('author', ''),
                row.get('year', ''),
                row.get('issue', ''),
                row.get('volume', ''),
                row.get('pdf_url', ''),
                filename,
                journal_name  # Insert parsed journal name into 'source' column
            ))
            inserted_count += 1
            
            # Commit every 100 records
            if inserted_count % 100 == 0:
                conn.commit()
                print(f"  -> Inserted {inserted_count} records...")
                
        except Exception as e:
            print(f"  [Error] Failed to insert {filename}: {e}")
            conn.rollback()
            skipped_count += 1

    # Final commit
    conn.commit()
    cur.close()
    conn.close()
    
    print("\n" + "=" * 30)
    print("SYNC COMPLETED")
    print(f"Total Inserted: {inserted_count}")
    print(f"Total Skipped:  {skipped_count}")
    print("=" * 30)

if __name__ == "__main__":
    main()