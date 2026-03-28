# Complete Week 2 Services Test
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db_service import DatabaseService
from services.knowledge_base import KnowledgeBase
from config import DB_URI, CHROMA_HOST, CHROMA_PORT


def main():
    print("\n" + "="*60)
    print("Week 2 Services Test")
    print("="*60)

    # Test Database Service
    print("\n[Database Service]")
    try:
        print("[1] Initializing database service...")
        db_service = DatabaseService(DB_URI)
        print("    [OK] Initialized")

        print("[2] Testing connection...")
        is_connected = db_service.test_connection()
        if is_connected:
            print("    [OK] Connected")
        else:
            print("    [FAIL] Connection failed")
            sys.exit(1)

        print("[3] Getting tables...")
        tables = db_service.get_table_names()
        print(f"    [OK] Found {len(tables)} tables")

        print("[4] Testing SQL execution...")
        result = db_service.execute_query("SELECT COUNT(*) as cnt FROM users")
        print(f"    [OK] Query result: {result[0]['cnt']} rows")

    except Exception as e:
        print(f"    [FAIL] {e}")
        sys.exit(1)

    # Test Knowledge Base Service
    print("\n[Knowledge Base Service]")
    try:
        print(f"[1] Initializing knowledge base ({CHROMA_HOST}:{CHROMA_PORT})...")
        kb = KnowledgeBase(host=CHROMA_HOST, port=CHROMA_PORT)
        print("    [OK] Initialized")

        print("[2] Health check...")
        is_healthy = kb.health_check()
        if is_healthy:
            print("    [OK] Connected")
        else:
            print("    [FAIL] Connection failed")
            sys.exit(1)

        print("[3] Getting statistics...")
        stats = kb.get_stats()
        print(f"    [OK] Total documents: {stats['total']}")
        print(f"    [OK] DDL: {stats['ddl_count']}")
        print(f"    [OK] SQL examples: {stats['sql_example_count']}")
        print(f"    [OK] Business terms: {stats['business_term_count']}")

        print("[4] Testing search...")
        results = kb.search("order sales", n_results=2)
        print(f"    [OK] Found {len(results)} results")

    except Exception as e:
        print(f"    [FAIL] {e}")
        sys.exit(1)

    # Summary
    print("\n" + "="*60)
    print("[SUCCESS] Week 2 services test passed!")
    print("="*60)


if __name__ == "__main__":
    main()
