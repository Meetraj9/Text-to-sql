# Database Configuration Guide

This application supports multiple database types through SQLAlchemy. You can easily switch between PostgreSQL, Databricks, MySQL, SQLite, and other SQLAlchemy-compatible databases.

## Supported Databases

- **PostgreSQL** (default)
- **Databricks**
- **MySQL**
- **SQLite**
- Any other SQLAlchemy-compatible database

## Configuration

### Environment Variables

Set the following in your `.env` file:

```env
# Database Type (required)
DB_TYPE=postgresql  # Options: postgresql, databricks, mysql, sqlite, etc.

# Connection Details (required)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password

# Optional: For Databricks, use token instead of password
# DB_TOKEN=your_databricks_token

# Optional: Database driver (e.g., 'psycopg2', 'pymysql')
# DB_DRIVER=psycopg2

# Optional: Schema name
# DB_SCHEMA=public
```

### Database-Specific Examples

#### PostgreSQL
```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=icp_data
DB_USER=postgres
DB_PASSWORD=your_password
DB_DRIVER=psycopg2
DB_SCHEMA=public
```

#### Databricks
```env
DB_TYPE=databricks
DB_HOST=your-workspace.cloud.databricks.com
DB_PORT=443
DB_NAME=default
DB_TOKEN=your_databricks_token
# Note: For Databricks, use DB_TOKEN instead of DB_PASSWORD
```

#### MySQL
```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=icp_data
DB_USER=root
DB_PASSWORD=your_password
DB_DRIVER=pymysql
```

#### SQLite
```env
DB_TYPE=sqlite
DB_NAME=/path/to/database.db
# Note: SQLite doesn't use host/port/user/password
```

## Installing Database Drivers

Install the appropriate driver for your database:

```bash
# PostgreSQL
uv sync --extra postgresql
# or
pip install psycopg2-binary

# Databricks
uv sync --extra databricks
# or
pip install databricks-sql-connector

# MySQL
uv sync --extra mysql
# or
pip install pymysql
```

## SQL Syntax Compatibility

The application generates database-agnostic SQL using:
- `LOWER()` + `LIKE` instead of PostgreSQL-specific `ILIKE`
- Standard SQL functions that work across databases
- Database type is passed to the LLM for context-aware SQL generation

## Connection String Format

The application automatically builds SQLAlchemy connection strings:

- **PostgreSQL**: `postgresql+psycopg2://user:password@host:port/database`
- **Databricks**: `databricks+connector://token:token@host:port/database`
- **MySQL**: `mysql+pymysql://user:password@host:port/database`
- **SQLite**: `sqlite:///path/to/database.db`

## Notes

- The application uses SQLAlchemy for database abstraction
- LangChain's `SQLDatabase` is used for schema introspection
- Query execution uses SQLAlchemy's `text()` for safe parameterized queries
- Read-only transaction mode is set when supported by the database

