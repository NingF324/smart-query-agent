"""
Script to build ChromaDB knowledge base from Spider dataset schemas.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService
from services.llm_service import get_llm_service
import sqlite3


def parse_tables_json(tables_json_path: Path) -> Dict:
    """Parse tables.json from Spider dataset."""
    with open(tables_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_schema_for_kb(db_entry: Dict) -> Dict:
    """
    Format database schema for ChromaDB indexing.

    Returns dictionary with DDL and descriptions.
    """
    result = {
        "db_id": db_entry.get('db_id', ''),
        "tables": []
    }

    tables = db_entry.get('table_names', [])
    columns = db_entry.get('column_names', [])
    foreign_keys = db_entry.get('foreign_keys', [])

    # 2. Table DDL and descriptions
    for table_idx, table_name in enumerate(tables):
        # Get columns for this table
        table_columns = []
        for col_idx, col_name in columns:
            if col_idx == table_idx:
                table_columns.append(col_name)

        # Create DDL
        ddl = f"CREATE TABLE {table_name} (\n"
        for col in table_columns:
            ddl += f"    {col} TEXT,\n"
        ddl = ddl.rstrip(",\n") + "\n);"

        result["tables"].append({
            "name": table_name,
            "ddl": ddl,
            "columns": table_columns,
            "description": f"This table contains data related to {table_name.replace('_', ' ')}."
        })

    return result


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
    llm = get_llm_service()

    total_documents = 0

    for db_entry in tables_data:
        db_id = db_entry['db_id']
        print(f"Processing database: {db_id}")

        # Format schema documents
        schema_data = format_schema_for_kb(db_entry)

        # Add each table DDL to knowledge base
        for table in schema_data["tables"]:
            kb.add_ddl(
                table_name=f"{db_id}.{table['name']}",
                ddl=table['ddl'],
                columns=[{"name": col, "type": "TEXT"} for col in table['columns']],
                description=table['description']
            )
            total_documents += 1

        print(f"  Added {len(schema_data['tables'])} schema documents for {db_id}")

    print(f"\nTotal documents added: {total_documents}")
    print(f"Knowledge base built successfully!")


def build_kb_from_sqlite_dir(
    spider_db_path: Path,
    db_list: Optional[List[str]] = None,
    max_databases: Optional[int] = None
):
    """
    Build knowledge base from SQLite databases.

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

    total_docs = 0

    for db_name in databases:
        db_path = spider_db_path / db_name
        sqlite_file = db_path / f"{db_name}.sqlite"

        if not sqlite_file.exists():
            print(f"  [Warning] SQLite file not found: {db_name}")
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

            # For each table, get schema
            for table_name in tables:
                # Get columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                # Build DDL
                ddl = f"CREATE TABLE {table_name} (\n"
                column_info = []
                for col in columns:
                    col_name = col[1]
                    col_type = col[2].upper()
                    ddl += f"    {col_name} {col_type},\n"
                    column_info.append({"name": col_name, "type": col_type})
                ddl = ddl.rstrip(",\n") + "\n);"

                # Add to knowledge base
                kb.add_ddl(
                    table_name=f"{db_name}.{table_name}",
                    ddl=ddl,
                    columns=column_info,
                    description=f"Table {table_name} from database {db_name}"
                )
                total_docs += 1

            conn.close()
            print(f"  Added {len(tables)} tables for {db_name}")

        except Exception as e:
            print(f"  [Error] Error processing {db_name}: {e}")
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
