# Knowledge Base Build Script
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_URI, CHROMA_HOST, CHROMA_PORT
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService


def main():
    print("\n" + "="*60)
    print("Building Knowledge Base")
    print("="*60)

    try:
        # Initialize database service
        print("\n[1] Initializing database service...")
        db_service = DatabaseService(DB_URI)

        # Test connection
        if not db_service.test_connection():
            print("    [FAIL] Database connection failed, please check configuration")
            return

        # Initialize knowledge base
        print(f"[2] Initializing knowledge base service ({CHROMA_HOST}:{CHROMA_PORT})...")
        kb = KnowledgeBase(host=CHROMA_HOST, port=CHROMA_PORT)

        # Clear old knowledge base
        print("[3] Clearing old knowledge base...")
        kb.clear_collection()

        # Get all table names
        tables = db_service.get_table_names()
        print(f"[4] Found {len(tables)} tables: {', '.join(tables)}")

        # Build knowledge base for each table
        for table_name in tables:
            print(f"\n[5] Processing table: {table_name}")

            # Get table info
            table_info = db_service.get_table_info(table_name)
            ddl = db_service.get_table_schema(table_name)

            # Add to knowledge base
            kb.add_ddl(
                table_name=table_name,
                ddl=ddl,
                columns=table_info['columns'],
                description=f"Contains {table_info['row_count']} records"
            )
            print(f"    [OK] Added {table_name} ({len(table_info['columns'])} columns, {table_info['row_count']} rows)")

        # Add SQL examples
        print("\n[6] Adding SQL examples...")
        sql_examples = [
            {
                "question": "Query order count for current month",
                "sql": "SELECT COUNT(*) as order_count FROM orders WHERE EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE)",
                "table": "orders"
            },
            {
                "question": "Sales ranking by category",
                "sql": "SELECT p.category, SUM(SI.quantity * SI.unit_price) as total_sales FROM order_items SI JOIN products p ON SI.product_id = p.product_id GROUP BY p.category ORDER BY total_sales DESC",
                "table": "order_items, products"
            },
            {
                "question": "Top 10 products with highest ratings",
                "sql": "SELECT p.product_name, AVG(r.rating) as avg_rating, COUNT(*) as review_count FROM reviews r JOIN products p ON r.product_id = p.product_id GROUP BY p.product_id, p.product_name HAVING COUNT(*) >= 5 ORDER BY avg_rating DESC LIMIT 10",
                "table": "reviews, products"
            },
            {
                "question": "User distribution by city",
                "sql": "SELECT city, COUNT(*) as user_count FROM users GROUP BY city ORDER BY user_count DESC",
                "table": "users"
            }
        ]

        for example in sql_examples:
            kb.add_sql_example(
                question=example['question'],
                sql=example['sql'],
                table_name=example['table']
            )
            print(f"    [OK] Added example: {example['question']}")

        # Add business terms
        print("\n[7] Adding business terms...")
        terms = [
            {
                "term": "Average Order Value (AOV)",
                "definition": "Average amount per order, calculated as total sales divided by order count",
                "table": "orders"
            },
            {
                "term": "Repurchase Rate",
                "definition": "Percentage of users who made repeat purchases, indicating customer loyalty",
                "table": "orders, users"
            },
            {
                "term": "Sales Revenue",
                "definition": "Total sum of order amounts, representing business revenue",
                "table": "order_items"
            }
        ]

        for term in terms:
            kb.add_business_term(
                term=term['term'],
                definition=term['definition'],
                related_table=term['table']
            )
            print(f"    [OK] Added term: {term['term']}")

        # Show statistics
        print("\n[8] Knowledge base statistics:")
        stats = kb.get_stats()
        print(f"    Total documents: {stats['total']}")
        print(f"    DDL documents: {stats['ddl_count']}")
        print(f"    SQL examples: {stats['sql_example_count']}")
        print(f"    Business terms: {stats['business_term_count']}")

        print("\n" + "="*60)
        print("[SUCCESS] Knowledge base construction completed!")
        print("="*60)
        print("\nNow you can use the knowledge base for retrieval!")

    except Exception as e:
        print(f"\n[FAIL] Knowledge base construction failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
