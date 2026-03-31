"""
Script to convert Spider SQLite databases to PostgreSQL.
"""

import json
import sqlite3
import psycopg2
from pathlib import Path
import re
from typing import Dict, List


def parse_sqlite_schema(schema_file: Path) -> List[str]:
    """
    Parse schema.sql file and extract CREATE TABLE statements.
    Convert SQLite types to PostgreSQL types.
    """
    with open(schema_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract CREATE TABLE statements
    create_tables = re.findall(
        r'CREATE TABLE.*?;',
        content,
        re.DOTALL
    )

    converted_statements = []
    for stmt in create_tables:
        # Convert SQLite to PostgreSQL syntax
        converted = (
            stmt
            .replace('INTEGER', 'INTEGER')
            .replace('TEXT', 'TEXT')
            .replace('REAL', 'NUMERIC')
            .replace('BOOLEAN', 'BOOLEAN')
        )
        converted_statements.append(converted)

    return converted_statements


def extract_insert_statements(schema_file: Path) -> List[str]:
    """Extract INSERT statements from schema.sql."""
    with open(schema_file, 'r', encoding='utf-8') as f:
        content = f.read()

    insert_statements = re.findall(
        r'INSERT INTO.*?;',
        content,
        re.DOTALL
    )

    return insert_statements


def copy_data_from_sqlite(sqlite_path: Path, pg_conn, table_name: str):
    """Copy data from SQLite to PostgreSQL."""
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    if rows:
        pg_cursor = pg_conn.cursor()

        # Get column names
        columns = [desc[0] for desc in cursor.description]

        # Build INSERT statement
        placeholders = ', '.join(['%s'] * len(columns))
        cols_str = ', '.join([f'"{col}"' for col in columns])
        insert_stmt = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'

        for row in rows:
            values = [row[col] for col in columns]
            try:
                pg_cursor.execute(insert_stmt, values)
            except Exception as e:
                print(f"Error inserting into {table_name}: {e}")
                continue

        pg_conn.commit()
        print(f"Copied {len(rows)} rows to {table_name}")

    sqlite_conn.close()


def get_table_names(sqlite_path: Path) -> List[str]:
    """Get all table names from SQLite database."""
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    cursor = sqlite_conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    sqlite_conn.close()
    return tables


def convert_single_database(
    db_name: str,
    spider_db_path: Path,
    pg_conn_params: Dict,
    drop_existing: bool = True
):
    """Convert a single Spider SQLite database to PostgreSQL."""
    db_path = spider_db_path / db_name

    # Find schema.sql and sqlite file
    schema_file = db_path / "schema.sql"
    sqlite_file = db_path / f"{db_name}.sqlite"

    if not schema_file.exists():
        print(f"Schema file not found for {db_name}")
        return

    print(f"\nConverting database: {db_name}")

    try:
        # Connect to PostgreSQL
        pg_conn = psycopg2.connect(**pg_conn_params)
        pg_conn.autocommit = True
        pg_cursor = pg_conn.cursor()

        # Drop existing database if requested
        if drop_existing:
            pg_cursor.execute(f"DROP SCHEMA IF EXISTS {db_name} CASCADE;")
            pg_cursor.execute(f"CREATE SCHEMA {db_name};")
            pg_cursor.execute(f"SET search_path TO {db_name}, public;")

        # Create tables from schema
        create_statements = parse_sqlite_schema(schema_file)
        for stmt in create_statements:
            try:
                pg_cursor.execute(stmt)
                print(f"Created table: {stmt.split('CREATE TABLE')[1].split('(')[0].strip()}")
            except Exception as e:
                print(f"Error creating table: {e}")

        pg_conn.commit()

        # Copy data from SQLite
        if sqlite_file.exists():
            tables = get_table_names(sqlite_file)
            for table in tables:
                copy_data_from_sqlite(sqlite_file, pg_conn, table)

        pg_conn.close()
        print(f"Successfully converted {db_name}")

    except Exception as e:
        print(f"Error converting {db_name}: {e}")


def convert_all_databases(
    spider_db_path: Path,
    pg_conn_params: Dict,
    max_databases: int = None,
    db_list: List[str] = None
):
    """Convert all Spider SQLite databases to PostgreSQL."""
    spider_db_path = Path(spider_db_path)

    if db_list:
        databases = db_list
    else:
        databases = [d.name for d in spider_db_path.iterdir() if d.is_dir()]
        if max_databases:
            databases = databases[:max_databases]

    print(f"Converting {len(databases)} databases...")

    for db_name in databases:
        convert_single_database(db_name, spider_db_path, pg_conn_params)


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Convert Spider SQLite to PostgreSQL")
    parser.add_argument(
        "--spider-path",
        type=str,
        default="E:/spider_data/spider_data/database",
        help="Path to Spider database directory"
    )
    parser.add_argument(
        "--db-list",
        type=str,
        nargs="+",
        help="List of specific databases to convert"
    )
    parser.add_argument(
        "--max-db",
        type=int,
        help="Maximum number of databases to convert"
    )

    args = parser.parse_args()

    pg_params = {
        "host": "localhost",
        "port": 55432,
        "database": "spider",
        "user": "postgres",
        "password": "password"
    }

    # Create spider database if it doesn't exist
    conn = psycopg2.connect(
        host="localhost",
        port=55432,
        database="postgres",
        user="postgres",
        password="password"
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'spider'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE spider")
        print("Created spider database")
    conn.close()

    convert_all_databases(
        args.spider_path,
        pg_params,
        max_databases=args.max_db,
        db_list=args.db_list
    )
