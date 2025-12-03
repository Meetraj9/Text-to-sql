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
        # Remove SQL comments before checking patterns (allow legitimate comments)
        query_cleaned = SQLInjectionValidator._remove_comments(query)
        query_upper = query_cleaned.upper()
        
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
    def _remove_comments(query: str) -> str:
        """
        Remove SQL comments from query for validation purposes.
        
        Args:
            query: SQL query string
            
        Returns:
            Query with comments removed
        """
        import re
        
        # Remove single-line comments (-- comment)
        lines = query.split('\n')
        query_without_comments = []
        for line in lines:
            # Find -- that's not inside a string
            comment_pos = -1
            in_string = False
            quote_char = None
            for i, char in enumerate(line):
                if char in ("'", '"') and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                        quote_char = None
                elif not in_string and i < len(line) - 1 and line[i:i+2] == '--':
                    comment_pos = i
                    break
            if comment_pos >= 0:
                line = line[:comment_pos].rstrip()
            query_without_comments.append(line)
        
        # Remove multi-line comments (/* comment */)
        query_cleaned = '\n'.join(query_without_comments)
        query_cleaned = re.sub(r'/\*.*?\*/', '', query_cleaned, flags=re.DOTALL)
        
        return query_cleaned
    
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
        # Remove comments before checking for multiple statements
        query_cleaned = SQLInjectionValidator._remove_comments(query)
        
        # Count semicolons (excluding trailing semicolon)
        query_stripped = query_cleaned.strip().rstrip(';').strip()
        semicolon_count = query_stripped.count(';')
        
        if semicolon_count > 0:
            logger.warning(f"Multiple SQL statements detected: {semicolon_count + 1} statements")
            return False, f"Multiple SQL statements detected ({semicolon_count + 1} found). Only single SELECT queries are allowed."
        
        return True, ""

