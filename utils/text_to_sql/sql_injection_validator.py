"""
SQL injection pattern detection and validation.
"""

from utils.common.logger import get_logger

logger = get_logger(__name__)


class SQLInjectionValidator:
    """Validate SQL queries for injection patterns."""
    
    # SQL injection patterns to detect
    INJECTION_PATTERNS = [
        '; DROP',
        '; DELETE',
        '; INSERT',
        '; UPDATE',
        '; TRUNCATE',
        '; ALTER',
        '; CREATE',
        'OR 1=1',
        'OR \'1\'=\'1\'',
        'OR "1"="1"',
        '--',  # SQL comment (can hide malicious code)
        '/*',  # Multi-line comment start
        '*/',  # Multi-line comment end
        'EXEC(',  # Function execution
        'EXECUTE(',
        'xp_',  # Extended stored procedures
        'sp_',  # Stored procedures
    ]
    
    # Dangerous SQL statement patterns
    DANGEROUS_STATEMENT_PATTERNS = [
        'DELETE FROM',
        'DROP TABLE',
        'DROP DATABASE',
        'INSERT INTO',
        'UPDATE SET',
        'TRUNCATE TABLE',
        'ALTER TABLE',
        'CREATE TABLE',
    ]
    
    @staticmethod
    def check_injection_patterns(query: str) -> tuple[bool, str]:
        """
        Check for SQL injection patterns in the query.
        
        Args:
            query: SQL query string to check
            
        Returns:
            Tuple of (is_safe, error_message)
            - is_safe: True if no injection patterns found, False otherwise
            - error_message: Empty string if safe, error message if injection detected
        """
        query_upper = query.upper()
        
        # Check for injection patterns
        for pattern in SQLInjectionValidator.INJECTION_PATTERNS:
            if pattern in query_upper:
                # Special handling for UNION SELECT - allow legitimate UNION
                if pattern == 'UNION SELECT':
                    # Check if UNION is used legitimately
                    union_pos = query_upper.find('UNION')
                    select_before = query_upper[:union_pos].count('SELECT')
                    select_after = query_upper[union_pos:].count('SELECT')
                    # Legitimate UNION should have at least one SELECT before and after
                    if select_before >= 1 and select_after >= 1:
                        logger.debug("Legitimate UNION SELECT detected - allowing")
                        continue  # Allow legitimate UNION
                    else:
                        logger.warning("Suspicious UNION usage detected")
                        return False, "Potential SQL injection detected: UNION SELECT"
                
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return False, f"Potential SQL injection detected: {pattern}"
        
        # Check for dangerous statement patterns
        for pattern in SQLInjectionValidator.DANGEROUS_STATEMENT_PATTERNS:
            if pattern in query_upper:
                logger.warning(f"Dangerous SQL statement pattern detected: {pattern}")
                return False, f"Dangerous operation detected: {pattern.split()[0]}"
        
        logger.debug("No SQL injection patterns detected")
        return True, ""
    
    @staticmethod
    def check_multiple_statements(query: str) -> tuple[bool, str]:
        """
        Check for multiple SQL statements (potential SQL injection).
        
        Args:
            query: SQL query string to check
            
        Returns:
            Tuple of (is_safe, error_message)
            - is_safe: True if single statement, False if multiple detected
            - error_message: Empty string if safe, error message if multiple statements found
        """
        # Count semicolons (excluding trailing semicolon)
        query_stripped = query.strip().rstrip(';').strip()
        semicolon_count = query_stripped.count(';')
        
        if semicolon_count > 0:
            logger.warning(f"Multiple SQL statements detected: {semicolon_count + 1} statements")
            return False, f"Multiple SQL statements detected ({semicolon_count + 1} found). Only single SELECT queries are allowed."
        
        return True, ""

