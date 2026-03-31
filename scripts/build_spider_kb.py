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
import sqlite3


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

The `{col}` column stores information about {col.replace('_', ' ')} in {table_name} table.
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


def build_kb_from_sqlite_dir(
    spider_db_path: Path,
    db_list: Optional[List[str]] = None,
    max_databases: Optional[int] = None
):
    """
    Build knowledge base from SQLite SQLite databases.

    This reads actual schema from SQLite files.
    """
    print(f"Building knowledge base from SQLite databases in {spider_db_path}")

    spider_db_path = Path(spider_db_path)

    # Get database directories
    all_dbs = [d.name for d in spider_db_path.iterdir() if d.is_dir()]

    if db_list:
        databases = db_list
    elif max_databases:
        databases = all_dbs[:max_databases]
    else:
        databases = all_dbs

    print(f"Processing {len(databases)} databases...")

    kb = KnowledgeBase()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""]
    )

    total_docs = 0

    for db_name in databases:
        db_path = spider_db_path / db_name
        sqlite_file = db_path / f"{db_name}.sqlite"

        if not sqlite_file.exists():
            print(f"  ⚠️ SQLite file not found: {db_name}")
            continue

        print(f"Processing database: {db_name}")

        try:
            # Connect to SQLite
            conn = sqlite3.connect(str(sqlite_file))
            cursor = conn.cursor()

            # Get all tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]

            # Database overview
            overview = f"""
Database: {db_name}

This database contains {len(tables)} tables:
"""
            for table in tables:
                overview += f"- {table}\n"

            kb.add_document(Document(
                page_content=overview,
                metadata={"type": "database_overview", "db_id": db_name}
            ))
            total_docs += 1

            # For each table, get schema
            for table_name in tables:
                # Get columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                # Build DDL
                ddl = f"CREATE TABLE {table_name} (\n"
                for col in columns:
                    col_name = col[1]
                    col_type = col[2].upper()
                    ddl += f"    {col_name} {col_type},\n"
                ddl = ddl.rstrip(",\n") + "\n);"

                kb.add_document(Document(
                    page_content=ddl,
                    metadata={
                        "type": "table_ddl",
                        "db_id": db_name,
                        "table_name": table_name
                    }
                ))
                total_docs += 1

                # Column descriptions
                for col in columns:
                    col_name = col[1]
                    col_type = col[2].upper()
                    col_desc = f"""
Column: {col_name}
Table: {table_name}
Database: {db_name}

The `{col_name}` column stores {col_type} data in {table_name} table.
"""
                    kb.add_document(Document(
                        page_content=col_desc,
                        metadata={
                            "type": "column_description",
                            "db_id": db_name,
                            "table_name": table_name,
                            "column_name": col_name
                        }
                    ))
                    total_docs += 1

            # Get foreign keys
            cursor.execute("SELECT * FROM sqlite_master WHERE type='index'")
            indexes = cursor.fetchall()

            fk_desc = ""
            for idx in indexes:
                sql = idx[4]
                if 'FOREIGN KEY' in sql:
                    fk_desc += f"{sql}\n"

            if fk_desc:
                kb.add_document(Document(
                    page_content=fk_desc,
                    metadata={
                        "type": "foreign_keys",
                        "db_id": db_name
                    }
                ))
                total_docs += 1

            conn.close()
            print(f"  Added schema documents for {db_name}")

        except Exception as e:
            print(f"  ❌ Error processing {db_name}: {e}")
            continue

    print(f"\nTotal documents added: {total_docs}")
    print("Knowledge base built successfully!")


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Build ChromaDB KB from Spider")
    parser.add_argument(
        "--spider-path",
        type=str,
        default="E:/spider_data/spider_data/database",
        help="Path to Spider database directory"
    )
    parser.add_argument(
        "--tables-json",
        type=str,
        default="E:/spider_data/spider_data/tables.json",
        help="Path to Spider tables.json"
    )
    parser.add_argument(
        "--use-sqlite",
        action="store_true",
        help="Build KB from SQLite database files (recommended)"
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

    if args.use_sqlite:
        build_kb_from_sqlite_dir(
            spider_db_path=Path(args.spider_path),
            db_list=args.db_list,
            max_databases=args.max_db
        )
    else:
        build_kb_from_spider(
            tables_json_path=Path(args.tables_json),
            db_list=args.db_list,
            max_databases=args.max_db
        )
