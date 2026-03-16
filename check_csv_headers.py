import os
import csv

def check_csv_headers(root_dir):
    print(f"Scanning directory for journals containing '电子' (Electronic): {root_dir}\n")
    
    # Store consistency data: {sorted_tuple_of_headers: [list of files]}
    header_patterns = {} 

    count = 0
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip hidden directories and pycache
        if '__pycache__' in dirpath or '/.' in dirpath:
            continue
            
        journal_name = os.path.basename(dirpath)
        
        # FILTER: Only process if journal name contains "电子"
        if "电子" not in journal_name:
            continue

        for filename in filenames:
            if filename.endswith('.csv'):
                count += 1
                full_path = os.path.join(dirpath, filename)
                
                try:
                    # Try reading with utf-8-sig to handle BOM
                    try:
                        with open(full_path, 'r', encoding='utf-8-sig') as f:
                            reader = csv.reader(f)
                            try:
                                headers = next(reader)
                            except StopIteration:
                                print(f"[EMPTY] {journal_name}/{filename} is empty.")
                                continue
                    except UnicodeDecodeError:
                        # Fallback to gbk if utf-8 fails
                        with open(full_path, 'r', encoding='gbk') as f:
                            reader = csv.reader(f)
                            try:
                                headers = next(reader)
                            except StopIteration:
                                print(f"[EMPTY] {journal_name}/{filename} is empty.")
                                continue
                            
                    # Clean headers (strip whitespace) and sort them for consistency comparison
                    # Using sorted tuple ensures that order differences don't count as inconsistent if content is same
                    # If order matters, remove 'sorted'
                    headers_list = [h.strip() for h in headers if h.strip()]
                    headers_tuple = tuple(headers_list) # Keep original order to check strict consistency
                    
                    if headers_tuple not in header_patterns:
                        header_patterns[headers_tuple] = []
                    header_patterns[headers_tuple].append(f"{journal_name}/{filename}")
                                
                except Exception as e:
                    print(f"[ERROR] Could not read {full_path}: {e}")

    # --- Output Results ---
    print("-" * 60)
    print(f"Found {count} CSV files in '电子' journals.")
    print("-" * 60)
    
    if not header_patterns:
        print("No matching files found.")
        return

    # Check if there is only one pattern
    if len(header_patterns) == 1:
        print("✅ All '电子' journals have the EXACT SAME headers:")
        headers = list(header_patterns.keys())[0]
        print(f"  {', '.join(headers)}")
    else:
        print("⚠️  Inconsistent headers found. Listing variations:\n")
        # Sort patterns by frequency (most common first)
        sorted_patterns = sorted(header_patterns.items(), key=lambda x: len(x[1]), reverse=True)
        
        for i, (headers, files) in enumerate(sorted_patterns, 1):
            print(f"Pattern #{i} (Found in {len(files)} files):")
            print(f"  Headers: {', '.join(headers)}")
            print("  Files:")
            for f in files:
                print(f"    - {f}")
            print()

if __name__ == "__main__":
    root_directory = "/Users/oushu/Desktop/豌豆数据源crawler"
    check_csv_headers(root_directory)