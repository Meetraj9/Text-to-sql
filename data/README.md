# Data Generation & Database Setup

This guide explains how to generate synthetic ICP data and set up the database. The system supports multiple database types: PostgreSQL, Databricks, MySQL, SQLite, and other SQLAlchemy-compatible databases.

## Data Generation

### Generate Synthetic Data

```bash
# Generate 50k records (default)
uv run data/generate_synthetic_data.py

# Generate custom number of records
uv run data/generate_synthetic_data.py --num-records 10000

# Generate a large, highly varied dataset (e.g., 100k rows)
uv run data/generate_synthetic_data.py --num-records 100000

# Custom output file
uv run data/generate_synthetic_data.py --output data/my_data.csv
```

### Configuration

Edit `config.json` to customize:
- US states and cities
- SIC codes (4-digit industry codes)
- Common industry codes used for weighted sampling
- Decision maker titles
- Employee size segments
- Square footage buckets
- Generation probabilities and settings (e.g., `common_industry_weight` to reduce emphasis on common industries)

### Output

The script generates a CSV file with the following columns:
- Geography (State or City)
- Industry (4-digit SIC code between 0000 and 8999)
- Title (Decision maker role)
- Title Tier (tier_i, tier_ii, or tier_iii - classification of the title)
- Employee Size (Numeric value)
- Sales Volume (Numeric value, related to employee size)
- Square Footage (Numeric value for every record)

## Database Setup

### Prerequisites

- Database installed and running (PostgreSQL, Databricks, MySQL, SQLite, etc.)
- Database created
- Python dependencies installed (if using Python script)
- Database driver installed (see [DATABASE_CONFIG.md](../DATABASE_CONFIG.md) for details)

## Environment Variables

Create a `.env` file in the project root with your database credentials:

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

See [DATABASE_CONFIG.md](../DATABASE_CONFIG.md) for detailed database-specific configuration examples.

## Option 1: Using SQL Scripts (PostgreSQL)

**Note**: SQL scripts are PostgreSQL-specific. For other databases, use Option 2 (Python script) which is database-agnostic.

### Step 1: Create the Table

```bash
psql -U your_username -d your_database -f data/create_table.sql
```

Or connect to psql and run:

```sql
\i data/create_table.sql
```

### Step 2: Load CSV Data

Update the file path in `data/load_data.sql` to match your CSV location, then:

```bash
psql -U your_username -d your_database -f data/load_data.sql
```

Or use COPY command directly:

```sql
COPY icp_data(geography, industry, title, title_tier, employee_size, sales_volume, square_footage)
FROM '/absolute/path/to/synthetic_icp_data.csv'
WITH (FORMAT csv, HEADER true, NULL '');
```

**For other databases**: Use Option 2 (Python script) which automatically adapts to your database type.

## Option 2: Using Python Script (Recommended for Multi-Database)

The Python script is database-agnostic and works with PostgreSQL, Databricks, MySQL, SQLite, and other SQLAlchemy-compatible databases.

### Step 1: Install Dependencies

```bash
uv sync

# Install database driver (choose one)
uv sync --extra postgresql    # For PostgreSQL
uv sync --extra databricks    # For Databricks
uv sync --extra mysql        # For MySQL
```

### Step 2: Run the Load Script

With environment variables (recommended):

```bash
# Make sure .env file is configured with DB_TYPE and connection details
uv run data/load_data.py --csv data/synthetic_icp_data.csv
```

Or with command-line arguments:

```bash
uv run data/load_data.py \
  --csv data/synthetic_icp_data.csv \
  --host localhost \
```

**Note:** If you're regenerating data with the new `title_tier` column, use `--clean-and-reload` to drop and recreate the table:

```bash
uv run data/load_data.py --csv data/synthetic_icp_data.csv --clean-and-reload
```

Or manually drop the table in psql:

```sql
DROP TABLE IF EXISTS icp_data CASCADE;
```
  --port 5432 \
  --database your_database \
  --user your_username \
  --password your_password
```

Note: Command-line arguments override environment variables.

## Table Schema

The `icp_data` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key (auto-incrementing) |
| geography | VARCHAR(100) | US state or city |
| industry | VARCHAR(4) | 4-digit SIC code |
| title | VARCHAR(100) | Decision maker title |
| title_tier | VARCHAR(10) | Title tier classification (tier_i, tier_ii, tier_iii, or NULL) |
| employee_size | INTEGER | Number of employees |
| sales_volume | BIGINT | Sales volume in USD (nullable) |
| square_footage | INTEGER | Square footage in sq ft |
| created_at | TIMESTAMP | Record creation timestamp |

## Example Queries

### Filter by Employee Size Bucket

```sql
-- Micro (1-20 employees)
SELECT * FROM icp_data WHERE employee_size BETWEEN 1 AND 20;

-- Small-Medium (21-200 employees)
SELECT * FROM icp_data WHERE employee_size BETWEEN 21 AND 200;

-- Enterprise (200+ employees)
SELECT * FROM icp_data WHERE employee_size >= 201;
```

### Filter by Square Footage Bucket

```sql
-- Small (<5,000 sq ft)
SELECT * FROM icp_data WHERE square_footage < 5000;

-- Medium (5,000-20,000 sq ft)
SELECT * FROM icp_data WHERE square_footage BETWEEN 5000 AND 20000;

-- Large (20,000+ sq ft)
SELECT * FROM icp_data WHERE square_footage >= 20000;
```

### Filter by Sales Volume Bucket

```sql
-- Low (<$5M)
SELECT * FROM icp_data WHERE sales_volume < 5000000;

-- Medium ($5M-$50M)
SELECT * FROM icp_data WHERE sales_volume BETWEEN 5000000 AND 50000000;

-- High ($50M+)
SELECT * FROM icp_data WHERE sales_volume >= 50000000;
```

### Complex Queries

```sql
-- Find companies in California with 50+ employees and sales > $10M
SELECT * FROM icp_data 
WHERE geography = 'California' 
  AND employee_size >= 50 
  AND sales_volume > 10000000;

-- Find commercial cleaning companies with square footage
SELECT * FROM icp_data 
WHERE industry LIKE '73%' 
  AND square_footage IS NOT NULL;

-- Count records by state
SELECT geography, COUNT(*) as count 
FROM icp_data 
GROUP BY geography 
ORDER BY count DESC;
```

## Notes

- The `id` column is auto-generated and doesn't need to be provided when loading CSV
- Empty values in CSV are treated as NULL in the database
- Square footage is included for every generated record and scaled relative to employee size

