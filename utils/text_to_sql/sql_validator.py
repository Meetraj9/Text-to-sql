"""
SQL query validation using sqlparse library.
Handles CTEs, subqueries, and complex SELECT forms.
"""

import sqlparse
from sqlparse.sql import Statement, Token
from sqlparse.tokens import Keyword, DML

from utils.common.logger import get_logger
from utils.text_to_sql.sql_injection_validator import SQLInjectionValidator

logger = get_logger(__name__)


class SQLValidator:
    """
    Validate SQL queries for safety and correctness.
    
    Uses sqlparse to properly distinguish between:
    - SQL keywords (DELETE, UPDATE, etc.) - BLOCKED
    - Column names (delete_flag, update_time) - ALLOWED
    - String values ('delete', 'update') - ALLOWED
    
    Examples:
        ✅ SELECT delete_flag FROM table;  # Column name - allowed
        ✅ SELECT * FROM table WHERE status = 'delete';  # String value - allowed
        ❌ DELETE FROM table;  # SQL keyword - blocked
        ❌ UPDATE table SET ...;  # SQL keyword - blocked
    """
    
    @staticmethod
    def validate(query: str) -> tuple[bool, str]:
        """
        Validate SQL query for safety.
        
        CRITICAL SECURITY: This function ensures only safe SELECT queries are allowed.
        All data manipulation operations (DELETE, UPDATE, INSERT, DROP, etc.) are blocked.
        
        Args:
            query: SQL query string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if query is valid and safe, False otherwise
            - error_message: Empty string if valid, error message if invalid
        """
        logger.debug(f"Validating SQL query: {query[:100]}...")
        if not query or not query.strip():
            logger.warning("SQL validation failed: Query is empty")
            return False, "Query is empty"
        
        query_upper = query.strip().upper()
        
        # Quick check: Must start with SELECT or WITH (for CTEs)
        if not (query_upper.startswith('SELECT') or query_upper.startswith('WITH')):
            logger.warning("Query does not start with SELECT or WITH")
            return False, "Only SELECT queries are allowed. Query must start with SELECT or WITH (for CTEs)"
        
        # Check for multiple statements using SQL injection validator
        is_safe, error = SQLInjectionValidator.check_multiple_statements(query)
        if not is_safe:
            logger.warning(f"Multiple statements detected: {error}")
            return False, error
        
        try:
            # Parse SQL query
            parsed = sqlparse.parse(query.strip())
            
            if not parsed:
                logger.warning("SQL validation failed: Failed to parse SQL query")
                return False, "Failed to parse SQL query"
            
            # Check each statement
            for statement in parsed:
                is_valid, error = SQLValidator._validate_statement(statement)
                if not is_valid:
                    logger.warning(f"SQL validation failed: {error}")
                    return False, error
            
            logger.info("SQL validation passed - query is safe")
            return True, ""
            
        except Exception as e:
            logger.error(f"SQL validation error: {e}", exc_info=True)
            return False, f"SQL parsing error: {str(e)}"
    
    @staticmethod
    def _validate_statement(statement: Statement) -> tuple[bool, str]:
        """
        Validate a single SQL statement using sqlparse.
        Handles CTEs, subqueries, and complex SELECT forms.
        
        Args:
            statement: Parsed SQL statement
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug("Validating SQL statement using sqlparse")
        
        # Convert statement to string for pattern matching (for injection detection)
        statement_str = str(statement).upper()
        
        # Dangerous SQL keywords that should be blocked
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 
            'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE', 'EXECUTE IMMEDIATE',
            'MERGE', 'REPLACE', 'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK',
            'LOCK', 'UNLOCK', 'BACKUP', 'RESTORE', 'COPY', 'IMPORT', 'EXPORT'
        ]
        
        # Use sqlparse to properly identify statement type
        # Get all tokens from the statement - sqlparse properly distinguishes:
        # - SQL keywords (DML, Keyword tokens) from column names/identifiers
        
        tokens = list(statement.flatten())
        
        dml_found = False
        first_dml_token = None
        
        for token in tokens:
            if token.ttype is DML:
                dml_found = True
                first_dml_token = token.value.upper()
                if first_dml_token != 'SELECT':
                    logger.warning(f"Dangerous DML operation detected: {first_dml_token}")
                    return False, f"Only SELECT queries are allowed. Found: {first_dml_token}"
                break  # Found the main DML, check if it's SELECT
        

        for token in tokens:
            if token.ttype is Keyword:
                token_upper = token.value.upper()
                if token_upper in dangerous_keywords:
                    logger.warning(f"Dangerous SQL keyword detected: {token_upper}")
                    return False, f"Dangerous operation detected: {token_upper}"
        
        # Check for CTE (WITH clause) - CTEs are valid for SELECT queries
        has_with = False
        has_select = False
        
        # Check statement structure: WITH ... SELECT or just SELECT
        statement_normalized = statement_str.strip()
        if statement_normalized.startswith('WITH'):
            has_with = True
            # CTE must eventually have a SELECT
            if 'SELECT' in statement_normalized:
                has_select = True
            else:
                logger.warning("WITH clause found but no SELECT statement")
                return False, "WITH clause must be followed by a SELECT statement"
        elif statement_normalized.startswith('SELECT'):
            has_select = True
        
        # Must have SELECT somewhere (either directly or after WITH)
        if not has_select:
            logger.warning("No SELECT statement found")
            return False, "Query must contain a SELECT statement"
        
        # If we found a DML token, ensure it's SELECT
        if dml_found and first_dml_token != 'SELECT':
            logger.warning(f"Non-SELECT DML operation detected: {first_dml_token}")
            return False, f"Only SELECT queries are allowed. Found: {first_dml_token}"
        
        # Check for dangerous keywords in tokens
        for token in tokens:
            if token.ttype is Keyword:
                token_upper = token.value.upper()
                if token_upper in dangerous_keywords:
                    logger.warning(f"Dangerous keyword detected: {token_upper}")
                    return False, f"Dangerous operation detected: {token_upper}"
        
        # Check for SQL injection patterns using dedicated validator
        is_safe, error = SQLInjectionValidator.check_injection_patterns(str(statement))
        if not is_safe:
            logger.warning(f"SQL injection detected: {error}")
            return False, error
        
        logger.debug("SQL statement validation passed - query is safe SELECT")
        return True, ""

