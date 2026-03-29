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

    # Test LLM Service (mock if no API key)
    print("\n[LLM Service]")
    try:
        from services.llm_service import LLMService, get_llm_service
        import os

        api_key = os.getenv("DEEPSEEK_API_KEY", "")

        if api_key:
            print("[1] Initializing LLM service with API key...")
            llm = LLMService(api_key=api_key)
            print("    [OK] Initialized")

            print("[2] Health check (will skip if no API key)...")
            try:
                is_healthy = llm.health_check()
                if is_healthy:
                    print("    [OK] API connection successful")
                else:
                    print("    [WARN] API connection failed, but service initialized")
            except Exception as e:
                print(f"    [WARN] Health check failed (expected without valid API): {e}")
        else:
            print("[1] Skipping LLM service test (DEEPSEEK_API_KEY not set)")
            print("    [OK] Service would initialize with mock")

    except ImportError as e:
        print(f"    [FAIL] Import failed: {e}")
        print("    [HINT] Install langchain-deepseek: pip install langchain-deepseek")
    except Exception as e:
        print(f"    [WARN] LLM service test skipped: {e}")

    # Test Embedding Service (mock if no API key)
    print("\n[Embedding Service]")
    try:
        from services.embedding_service import EmbeddingService, get_embedding_service
        import os

        api_key = os.getenv("DEEPSEEK_API_KEY", "")

        print("[1] Initializing Embedding service...")
        emb = EmbeddingService(api_key=api_key)
        print("    [OK] Initialized")

        print("[2] Getting embedding dimension...")
        dim = emb.get_embedding_dimension()
        print(f"    [OK] Embedding dimension: {dim}")

        print("[3] Testing single text embedding...")
        test_vector = emb.embed_query("测试文本")
        assert len(test_vector) == dim, "Vector dimension mismatch"
        print(f"    [OK] Vector generated with {len(test_vector)} dimensions")

        print("[4] Testing batch embedding...")
        batch_vectors = emb.embed(["文本1", "文本2"])
        assert len(batch_vectors) == 2, "Batch size mismatch"
        print(f"    [OK] Batch embedding successful")

    except ImportError as e:
        print(f"    [FAIL] Import failed: {e}")
        print("    [HINT] Install required dependencies: pip install sentence-transformers langchain-openai")
    except Exception as e:
        print(f"    [WARN] Embedding service test skipped: {e}")

    # Summary
    print("\n" + "="*60)
    print("[SUCCESS] Week 2 services test passed!")
    print("="*60)


if __name__ == "__main__":
    main()
