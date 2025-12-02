"""
Database wrapper for LangChain SQLDatabase integration.
Supports multiple database types via SQLAlchemy (PostgreSQL, Databricks, MySQL, etc.).
"""

from typing import List, Dict, Any, Optional, Tuple
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import InfoSQLDatabaseTool
from sqlalchemy import create_engine, text

from utils.common.config import get_db_settings
from utils.common.logger import get_logger

logger = get_logger(__name__)


def build_connection_string(db_settings) -> str:
    """
    Build SQLAlchemy connection string based on database type.
    
    Args:
        db_settings: DatabaseSettings instance
        
    Returns:
        SQLAlchemy connection string
    """
    db_type = db_settings.db_type.lower()
    
    if db_type == "postgresql":
        driver = db_settings.driver or "psycopg2"
        return (
            f"postgresql+{driver}://{db_settings.user}:{db_settings.password}"
            f"@{db_settings.host}:{db_settings.port}/{db_settings.name}"
        )
    elif db_type == "databricks":
        # Databricks connection using token
        token = db_settings.token or db_settings.password
        return (
            f"databricks+connector://token:{token}@{db_settings.host}:{db_settings.port}/{db_settings.name}"
        )
    elif db_type == "mysql":
        driver = db_settings.driver or "pymysql"
        return (
            f"mysql+{driver}://{db_settings.user}:{db_settings.password}"
            f"@{db_settings.host}:{db_settings.port}/{db_settings.name}"
        )
    elif db_type == "sqlite":
        # SQLite uses file path, not host/port
        return f"sqlite:///{db_settings.name}"
    else:
        # Generic SQLAlchemy connection string
        # Format: {db_type}://{user}:{password}@{host}:{port}/{database}
        if db_settings.driver:
            db_type = f"{db_type}+{db_settings.driver}"
        return (
            f"{db_type}://{db_settings.user}:{db_settings.password}"
            f"@{db_settings.host}:{db_settings.port}/{db_settings.name}"
        )


def get_sql_database() -> SQLDatabase:
    """
    Create and return LangChain SQLDatabase instance.
    Supports multiple database types via SQLAlchemy.
    
    Returns:
        SQLDatabase instance connected to the configured database
    """
    db_settings = get_db_settings()
    
    # Build connection string based on database type
    connection_string = build_connection_string(db_settings)
    
    logger.info(f"Connecting to {db_settings.db_type} database at {db_settings.host}:{db_settings.port}")
    
    # Create SQLAlchemy engine
    engine = create_engine(connection_string)
    
    # Create SQLDatabase instance
    # Use schema if provided, otherwise None (will use default schema)
    schema = db_settings.db_schema if db_settings.db_schema else None
    db = SQLDatabase(engine, schema=schema, include_tables=["icp_data"])
    
    return db


def get_info_sql_database_tool() -> InfoSQLDatabaseTool:
    """
    Create and return InfoSQLDatabaseTool instance.
    
    Returns:
        InfoSQLDatabaseTool instance for getting table schema information
    """
    db = get_sql_database()
    return InfoSQLDatabaseTool(db=db)


def test_connection() -> Tuple[bool, str, Optional[str]]:
    """
    Test database connection to verify if database is live and accessible.
    
    Returns:
        Tuple of (success: bool, message: str, install_command: Optional[str])
        install_command is the uv command to install the missing driver, if applicable
    """
    db_settings = get_db_settings()
    
    try:
        # Build connection string
        connection_string = build_connection_string(db_settings)
        engine = create_engine(connection_string)
        
        # Try to connect and execute a simple query
        with engine.connect() as conn:
            # Database-specific test queries
            db_type = db_settings.db_type.lower()
            
            if db_type == "postgresql":
                test_query = text("SELECT 1")
            elif db_type == "databricks":
                test_query = text("SELECT 1")
            elif db_type == "mysql":
                test_query = text("SELECT 1")
            elif db_type == "sqlite":
                test_query = text("SELECT 1")
            else:
                # Generic test query
                test_query = text("SELECT 1")
            
            result = conn.execute(test_query)
            result.fetchone()  # Consume the result
            
            return True, f"✅ Connection successful! Database '{db_settings.name}' at {db_settings.host}:{db_settings.port} is live.", None
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Database connection test failed: {error_msg}", exc_info=True)
        
        # Detect missing database driver and provide install command
        install_command = None
        db_type = db_settings.db_type.lower()
        
        if "No module named 'psycopg2'" in error_msg or "psycopg2" in error_msg.lower():
            install_command = "uv sync --extra postgresql"
        elif "databricks" in error_msg.lower() or "databricks-sql-connector" in error_msg.lower():
            install_command = "uv sync --extra databricks"
        elif "pymysql" in error_msg.lower() or ("mysql" in error_msg.lower() and "module" in error_msg.lower()):
            install_command = "uv sync --extra mysql"
        elif db_type == "postgresql" and ("module" in error_msg.lower() or "import" in error_msg.lower()):
            install_command = "uv sync --extra postgresql"
        elif db_type == "databricks" and ("module" in error_msg.lower() or "import" in error_msg.lower()):
            install_command = "uv sync --extra databricks"
        elif db_type == "mysql" and ("module" in error_msg.lower() or "import" in error_msg.lower()):
            install_command = "uv sync --extra mysql"
        
        return False, f"❌ Connection failed: {error_msg}", install_command


def execute_query(sql_query: str, max_rows: int = 5) -> Tuple[List[Dict[str, Any]], int]:
    """
    Execute a SQL query and return results.
    Uses SQLAlchemy for database-agnostic query execution.
    
    SAFETY: Only SELECT queries are allowed. All queries are validated before execution.
    
    Args:
        sql_query: SQL SELECT query to execute
        max_rows: Maximum number of rows to return (default: 5)
        
    Returns:
        Tuple of (list of row dictionaries, total count)
        
    Raises:
        ValueError: If query is not a safe SELECT query
    """
    from utils.text_to_sql.sql_validator import SQLValidator
    
    # CRITICAL: Validate query before execution
    is_valid, error_message = SQLValidator.validate(sql_query)
    if not is_valid:
        logger.error(f"Query validation failed before execution: {error_message}")
        raise ValueError(f"Unsafe query detected: {error_message}")
    
    # Additional safety check: Ensure query starts with SELECT or WITH (for CTEs)
    query_upper = sql_query.strip().upper()
    if not (query_upper.startswith('SELECT') or query_upper.startswith('WITH')):
        logger.error(f"Query does not start with SELECT or WITH: {sql_query[:50]}...")
        raise ValueError("Only SELECT queries are allowed (including CTEs with WITH clause)")
    
    # Check for multiple statements (prevent SQL injection via semicolons)
    if sql_query.count(';') > 1 or (sql_query.count(';') == 1 and not sql_query.strip().endswith(';')):
        logger.error("Multiple SQL statements detected - potential SQL injection")
        raise ValueError("Multiple SQL statements detected. Only single SELECT queries are allowed.")
    
    db_settings = get_db_settings()
    
    try:
        # Build connection string and create engine
        connection_string = build_connection_string(db_settings)
        engine = create_engine(connection_string)
        
        # Clean up query (remove trailing semicolon, whitespace)
        clean_query = sql_query.strip().rstrip(';').strip()
        
        with engine.connect() as conn:
            # Set transaction to read-only mode (if supported by database)
            # This prevents any write operations even if validation fails
            try:
                if db_settings.db_type.lower() == "postgresql":
                    conn.execute(text("SET TRANSACTION READ ONLY"))
                elif db_settings.db_type.lower() == "mysql":
                    conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
                # Note: Not all databases support read-only transactions
            except Exception as read_only_error:
                logger.warning(f"Could not set read-only mode (may not be supported): {read_only_error}")
            
            # First, get total count by wrapping the query
            # Note: Some databases may need different syntax for subquery counting
            count_query = f"SELECT COUNT(*) FROM ({clean_query}) AS count_subquery"
            total_count = 0
            
            try:
                result = conn.execute(text(count_query))
                total_count = result.scalar()
            except Exception as count_error:
                logger.warning(f"Could not get count using subquery, executing query directly: {count_error}")
                # If count fails, execute query and count manually
                result = conn.execute(text(clean_query))
                all_rows = result.fetchall()
                total_count = len(all_rows)
            
            # Execute main query with limit
            # Note: LIMIT syntax may vary by database, but SQLAlchemy handles it
            # For databases that don't support LIMIT, we'll fetch and slice
            limited_query = f"{clean_query} LIMIT {max_rows}"
            try:
                result = conn.execute(text(limited_query))
            except Exception as limit_error:
                # If LIMIT not supported, execute without limit and slice results
                logger.warning(f"LIMIT not supported, fetching all and slicing: {limit_error}")
                result = conn.execute(text(clean_query))
                rows = result.fetchall()
                rows = rows[:max_rows]
                
                # Get column names
                columns = result.keys()
                
                # Convert to list of dictionaries
                results = [dict(zip(columns, row)) for row in rows]
                logger.info(f"Executed query: {len(results)} rows returned (total: {total_count})")
                return results, total_count
            
            # Get column names
            columns = result.keys()
            
            # Fetch results
            rows = result.fetchall()
            
            # Convert to list of dictionaries
            results = [dict(zip(columns, row)) for row in rows]
            
            logger.info(f"Executed query: {len(results)} rows returned (total: {total_count})")
            return results, total_count
        
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}", exc_info=True)
        raise

