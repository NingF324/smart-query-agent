"""
Script to build ChromaDB knowledge base from Spider dataset schemas.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService
from services.llm_service import get_llm
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def parse_tables_json(tables_json_path: Path) -> Dict:
    """Parse tables.json from Spider dataset."""
    with open(tables_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_schema_for_kb(db_entry: Dict) -> List[str]:
    """
    Format database schema for ChromaDB indexing.

    Returns list of document strings:
    - Database overview
    - Table DDL for each table
    - Table descriptions
    - Column descriptions
    """
    documents = []
    db_id = db_entry.get('db_id', '')

    # Database overview
    tables = db_entry.get('table_names', [])
    columns = db_entry.get('column_names', [])
    foreign_keys = db_entry.get('foreign_keys', [])

    # Create column mapping
    col_map = {}
    for col_idx, col_name in columns:
        if col_idx >= 0:
            table_name = tables[col_idx]
            col_map[(col_idx, col_name)] = table_name

    # 1. Database overview
    overview = f"""
Database: {db_id}

This database contains {len(tables)} tables:
{', '.join(f'`{t}`' for t in tables)}

Tables:
"""
    for table in tables:
        overview += f"- {table}\n"

    documents.append({
        "content": overview,
        "metadata": {
            "type": "database_overview",
            "db_id": db_id
        }
    })

    # 2. Table DDL and descriptions
    for table_idx, table_name in enumerate(tables):
        # Get columns for this table
        table_columns = []
        for col_idx, col_name in columns:
            if col_idx == table_idx:
                table_columns.append(col_name)

        # Create DDL-like description
        ddl = f"""
Table: {table_name} in database {db_id}

Schema definition:
```sql
CREATE TABLE {table_name} (
"""
        for col in table_columns:
            ddl += f"    {col} TEXT,\n"
        ddl = ddl.rstrip(",\n") + "\n);"

        documents.append({
            "content": ddl,
            "metadata": {
                "type": "table_ddl",
                "db_id": db_id,
                "table_name": table_name
            }
        })

        # Table description document
        desc = f"""
Table: {table_name}
Database: {db_id}

Columns: {', '.join(f'`{c}`' for c in table_columns)}

This table contains data related to {table_name.replace('_', ' ')}.
"""
        documents.append({
            "content": desc,
            "metadata": {
                "type": "table_description",
                "db_id": db_id,
                "table_name": table_name,
                "columns": table_columns
            }
        })

        # 3. Column descriptions
        for col in table_columns:
            col_desc = f"""
Column: {col}
Table: {table_name}
Database: {db_id}

The `{col}` column stores information about {col.replace('_', ' ')} in the {table_name} table.
"""
            documents.append({
                "content": col_desc,
                "metadata": {
                    "type": "column_description",
                    "db_id": db_id,
                    "table_name": table_name,
                    "column_name": col
                }
            })

    # 4. Foreign keys
    if foreign_keys:
        fk_desc = f"""
Database: {db_id}

Foreign Key Relationships:
"""
        for fk in foreign_keys:
            src_table = tables[fk[0]]
            src_col = columns[fk[1]][1]
            tgt_table = tables[fk[2]]
            tgt_col = columns[fk[3]][1]

            fk_desc += f"- {src_table}.{src_col} → {tgt_table}.{tgt_col}\n"

        documents.append({
            "content": fk_desc,
            "metadata": {
                "type": "foreign_keys",
                "db_id": db_id
            }
        })

    return documents


def build_kb_from_spider(
    tables_json_path: Path,
    db_list: Optional[List[str]] = None,
    max_databases: Optional[int] = None
):
    """Build ChromaDB knowledge base from Spider schemas."""
    print(f"Building knowledge base from {tables_json_path}")

    # Parse tables.json
    tables_data = parse_tables_json(tables_json_path)

    # Filter databases if needed
    if db_list:
        tables_data = [db for db in tables_data if db['db_id'] in db_list]
    elif max_databases:
        tables_data = tables_data[:max_databases]

    print(f"Processing {len(tables_data)} databases...")

    # Initialize services
    kb = KnowledgeBase()
    llm = get_llm()

    # Text splitter for chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""]
    )

    total_documents = 0

    for db_entry in tables_data:
        db_id = db_entry['db_id']
        print(f"Processing database: {db_id}")

        # Format schema documents
        raw_docs = format_schema_for_kb(db_entry)

        # Chunk documents
        for raw_doc in raw_docs:
            chunks = text_splitter.split_text(raw_doc['content'])
            for chunk in chunks:
                doc = Document(
                    page_content=chunk,
                    metadata=raw_doc['metadata']
                )
                kb.add_document(doc)
                total_documents += 1

        print(f"  Added {len(raw_docs)} schema documents for {db_id}")

    print(f"\nTotal documents added: {total_documents}")
    print(f"Knowledge base built successfully!")


def build_kb_with_postgres_schema(
    db_list: Optional[List[str]] = None
):
    """Build knowledge base by reading actual PostgreSQL schemas."""
    print("Building knowledge base from PostgreSQL schemas...")

    kb = KnowledgeBase()

    # Connect to PostgreSQL
    db_service = DatabaseService("postgresql://postgres:password@localhost:55432/spider")

    # Get all schemas (databases)
    all_schemas = db_service.execute_query("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('public', 'information_schema', 'pg_catalog')
        ORDER BY schema_name
    """)

    if db_list:
        schemas = [row[0] for row in all_schemas if row[0] in db_list]
    else:
        schemas = [row[0] for row in all_schemas]

    print(f"Found {len(schemas)} databases: {', '.join(schemas)}")

    total_docs = 0

    for schema_name in schemas:
        print(f"\nProcessing schema: {schema_name}")

        # Set search path to schema
        db_service.execute_query(f"SET search_path TO {schema_name}, public")

        # Get all tables
        tables = db_service.execute_query("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
            ORDER BY table_name
        """)

        # Database overview
        overview = f"""
Database: {schema_name}

This database contains {len(tables)} tables:
"""
        for table_row in tables:
            overview += f"- {table_row[0]}\n"

        kb.add_document(Document(
            page_content=overview,
            metadata={"type": "database_overview", "db_id": schema_name}
        ))
        total_docs += 1

        # For each table, get columns and create DDL
        for table_row in tables:
            table_name = table_row[0]

            # Get columns
            columns = db_service.execute_query(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                AND table_schema = current_schema()
                ORDER BY ordinal_position
            """)

            # Create DDL
            ddl = f"CREATE TABLE {table_name} (\n"
            for col_row in columns:
                ddl += f"    {col_row[0]} {col_row[1]},\n"
            ddl = ddl.rstrip(",\n") + "\n);"

            kb.add_document(Document(
                page_content=ddl,
                metadata={
                    "type": "table_ddl",
                    "db_id": schema_name,
                    "table_name": table_name
                }
            ))
            total_docs += 1

            # Column descriptions
            for col_row in columns:
                col_desc = f"""
Column: {col_row[0]}
Table: {table_name}
Database: {schema_name}

The `{col_row[0]}` column stores {col_row[1]} data in the {table_name} table.
"""
                kb.add_document(Document(
                    page_content=col_desc,
                    metadata={
                        "type": "column_description",
                        "db_id": schema_name,
                        "table_name": table_name,
                        "column_name": col_row[0]
                    }
                ))
                total_docs += 1

    print(f"\nTotal documents added: {total_docs}")
    print("Knowledge base built successfully!")


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Build ChromaDB KB from Spider")
    parser.add_argument(
        "--tables-json",
        type=str,
        default="E:/spider_data/spider_data/tables.json",
        help="Path to Spider tables.json"
    )
    parser.add_argument(
        "--use-postgres",
        action="store_true",
        help="Build KB from PostgreSQL schemas instead of JSON"
    )
    parser.add_argument(
        "--db-list",
        type=str,
        nargs="+",
        help="List of specific databases to process"
    )
    parser.add_argument(
        "--max-db",
        type=int,
        help="Maximum number of databases to process"
    )

    args = parser.parse_args()

    if args.use_postgres:
        build_kb_with_postgres_schema(db_list=args.db_list)
    else:
        build_kb_from_spider(
            Path(args.tables_json),
            db_list=args.db_list,
            max_databases=args.max_db
        )
