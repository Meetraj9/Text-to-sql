"""
Python script to load CSV data into database.
Supports multiple database types via SQLAlchemy (PostgreSQL, Databricks, MySQL, SQLite, etc.).
"""

import csv
import sys
from pathlib import Path
from typing import Dict, Optional
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, BigInteger, DateTime
from sqlalchemy.sql import select
from datetime import datetime

from utils.common.config import get_db_settings
from utils.common.db import build_connection_string
from utils.common.logger import get_logger

logger = get_logger(__name__)


def create_table_if_not_exists(engine, table_name: str = 'icp_data'):
    """
    Create table if it doesn't exist (database-agnostic).
    
    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table to create
    """
    db_settings = get_db_settings()
    db_type = db_settings.db_type.lower()
    
    with engine.connect() as conn:
        # Check if table exists (database-specific queries)
        if db_type == "postgresql":
            check_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = :table_name
                )
            """)
        elif db_type == "mysql":
            check_query = text("""
                SELECT COUNT(*) > 0 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = :table_name
            """)
        elif db_type == "sqlite":
            check_query = text("""
                SELECT COUNT(*) > 0 
                FROM sqlite_master 
                WHERE type='table' AND name=:table_name
            """)
        else:
            # Generic check (may not work for all databases)
            check_query = text("""
                SELECT COUNT(*) > 0 
                FROM information_schema.tables 
                WHERE table_name = :table_name
            """)
        
        result = conn.execute(check_query, {"table_name": table_name})
        table_exists = result.scalar() > 0
        
        if not table_exists:
            logger.info(f"Table '{table_name}' does not exist. Creating table...")
            
            # Database-specific table creation
            if db_type == "postgresql":
                create_query = text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id SERIAL PRIMARY KEY,
                        geography VARCHAR(100) NOT NULL,
                        industry VARCHAR(4) NOT NULL,
                        title VARCHAR(100) NOT NULL,
                        title_tier VARCHAR(10),
                        employee_size INTEGER NOT NULL,
                        sales_volume BIGINT,
                        square_footage INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            elif db_type == "mysql":
                create_query = text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        geography VARCHAR(100) NOT NULL,
                        industry VARCHAR(4) NOT NULL,
                        title VARCHAR(100) NOT NULL,
                        title_tier VARCHAR(10),
                        employee_size INTEGER NOT NULL,
                        sales_volume BIGINT,
                        square_footage INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            elif db_type == "sqlite":
                create_query = text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        geography VARCHAR(100) NOT NULL,
                        industry VARCHAR(4) NOT NULL,
                        title VARCHAR(100) NOT NULL,
                        title_tier VARCHAR(10),
                        employee_size INTEGER NOT NULL,
                        sales_volume INTEGER,
                        square_footage INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                # Generic SQL (may need adjustment for specific databases)
                create_query = text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTO_INCREMENT,
                        geography VARCHAR(100) NOT NULL,
                        industry VARCHAR(4) NOT NULL,
                        title VARCHAR(100) NOT NULL,
                        title_tier VARCHAR(10),
                        employee_size INTEGER NOT NULL,
                        sales_volume BIGINT,
                        square_footage INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            conn.execute(create_query)
            conn.commit()
            logger.info(f"Table '{table_name}' created successfully.")
        else:
            logger.info(f"Table '{table_name}' already exists.")


def load_csv_to_database(
    csv_file: str, 
    table_name: str = 'icp_data', 
    clean_only: bool = False, 
    clean_and_reload: bool = False
):
    """
    Load CSV data into database (database-agnostic).
    
    Args:
        csv_file: Path to CSV file
        table_name: Name of the table to insert into
        clean_only: If True, only truncate the table (don't load data)
        clean_and_reload: If True, truncate the table and then load data
    """
    csv_path = Path(csv_file)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")
    
    db_settings = get_db_settings()
    
    try:
        # Build connection string
        connection_string = build_connection_string(db_settings)
        engine = create_engine(connection_string)
        
        logger.info(f"Connecting to {db_settings.db_type} database at {db_settings.host}:{db_settings.port}")
        
        # Create table if it doesn't exist
        create_table_if_not_exists(engine, table_name)
        
        with engine.connect() as conn:
            # Handle clean/reload flags
            if clean_only or clean_and_reload:
                logger.info(f"Truncating table '{table_name}'...")
                db_type = db_settings.db_type.lower()
                
                if db_type == "sqlite":
                    truncate_query = text(f"DELETE FROM {table_name}")
                else:
                    truncate_query = text(f"TRUNCATE TABLE {table_name}")
                
                conn.execute(truncate_query)
                conn.commit()
                logger.info(f"Table '{table_name}' truncated successfully.")
                
                if clean_only:
                    logger.info("Clean-only mode: Data not loaded.")
                    return
            
            # Read CSV and prepare data
            records = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert empty strings to None for NULL values
                    record = {
                        'geography': row['Geography'],
                        'industry': row['Industry'],
                        'title': row['Title'],
                        'title_tier': row.get('Title Tier') if row.get('Title Tier') else None,
                        'employee_size': int(row['Employee Size']) if row['Employee Size'] else None,
                        'sales_volume': int(row['Sales Volume']) if row.get('Sales Volume') else None,
                        'square_footage': int(row['Square Footage']) if row.get('Square Footage') else None
                    }
                    records.append(record)
            
            logger.info(f"Read {len(records)} records from CSV")
            
            # Insert data using SQLAlchemy (database-agnostic)
            insert_query = text(f"""
                INSERT INTO {table_name} 
                (geography, industry, title, title_tier, employee_size, sales_volume, square_footage)
                VALUES (:geography, :industry, :title, :title_tier, :employee_size, :sales_volume, :square_footage)
            """)
            
            # Insert in batches for better performance
            batch_size = 1000
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                conn.execute(insert_query, batch)
                conn.commit()
                logger.info(f"Inserted batch {i//batch_size + 1} ({len(batch)} records)")
            
            logger.info(f"Successfully inserted {len(records)} records into {table_name}")
            
            # Verify data
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            result = conn.execute(count_query)
            total = result.scalar()
            logger.info(f"Total records in table: {total}")
            
            sqft_query = text(f"SELECT COUNT(*) FROM {table_name} WHERE square_footage IS NOT NULL")
            result = conn.execute(sqft_query)
            with_sqft = result.scalar()
            logger.info(f"Records with square footage: {with_sqft}")
        
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Error loading data: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    
    # Load settings from environment variables or .env file
    db_settings = get_db_settings()
    
    parser = argparse.ArgumentParser(description='Load CSV data into database (supports PostgreSQL, Databricks, MySQL, SQLite, etc.)')
    parser.add_argument('--csv', type=str, default='data/synthetic_icp_data.csv',
                        help='Path to CSV file (default: data/synthetic_icp_data.csv)')
    parser.add_argument('--table', type=str, default='icp_data',
                        help='Table name (default: icp_data)')
    parser.add_argument('--clean-only', action='store_true',
                        help='Truncate table only, do not load data')
    parser.add_argument('--clean-and-reload', action='store_true',
                        help='Truncate table and then load data from CSV')
    
    args = parser.parse_args()
    
    # Validate flags
    if args.clean_only and args.clean_and_reload:
        print("Error: Cannot use both --clean-only and --clean-and-reload flags together.")
        sys.exit(1)
    
    # Validate required parameters from environment
    if not db_settings.name:
        print("Error: Database name is required. Set DB_NAME environment variable.")
        sys.exit(1)
    if not db_settings.user and db_settings.db_type.lower() != "sqlite":
        print("Error: Database user is required. Set DB_USER environment variable.")
        sys.exit(1)
    if not db_settings.password and db_settings.db_type.lower() not in ["sqlite"] and not db_settings.token:
        print("Error: Database password or token is required. Set DB_PASSWORD or DB_TOKEN environment variable.")
        sys.exit(1)
    
    print(f"Using database type: {db_settings.db_type}")
    print(f"Database: {db_settings.name} at {db_settings.host}:{db_settings.port}")
    
    load_csv_to_database(args.csv, args.table, args.clean_only, args.clean_and_reload)
