import pymysql

src_conf = {
    'host': '121.173.150.103',
    'user': 'nmap',
    'password': 'Tech1324',
    'database': 'nmap',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def main():
    print("Connecting to FSD source database...")
    try:
        conn = pymysql.connect(**src_conf)
        with conn.cursor() as cursor:
            # Check if place_keywords table exists
            cursor.execute("SHOW TABLES LIKE 'place_keywords'")
            t = cursor.fetchone()
            if t:
                print("Table place_keywords exists in FSD.")
                cursor.execute("SELECT COUNT(*) as cnt FROM place_keywords")
                print("Total rows in FSD place_keywords:", cursor.fetchone()['cnt'])
            else:
                print("Table place_keywords does NOT exist in FSD.")
                
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print("All tables in FSD:", [list(t.values())[0] for t in tables])
        conn.close()
    except Exception as e:
        print("Error connecting to FSD:", e)

if __name__ == '__main__':
    main()
