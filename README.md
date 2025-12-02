# Text-to-SQL ICP Builder

A sophisticated conversational text-to-SQL system built with LangGraph that generates SQL queries from natural language through intelligent dialogue. Features conversation memory, human-in-the-loop (HITL) interrupts, and multi-database support.

## 🚀 Features

### Core Capabilities
- **Conversational Interface**: Natural language query building through dialogue
- **LangGraph Workflow**: State machine-based orchestration with checkpointing
- **Conversation Memory**: Maintains context across multiple turns
- **Human-in-the-Loop (HITL)**: Asks clarifying questions when needed
- **Multi-Database Support**: PostgreSQL, Databricks, MySQL, SQLite, and more
- **Smart Updates**: Preserves unmentioned filters when updating queries
- **Structured Output**: Uses Pydantic models for reliable LLM responses
- **SQL Validation**: Multi-layer security to prevent unsafe queries

### Advanced Features
- **Contextual Questions**: Asks relevant follow-up questions beyond required fields
- **Industry Mapping**: Maps industry descriptions to SIC codes with detailed rationale
- **Title Tier Mapping**: Rule-based title classification with LLM fallback
- **Sales Volume Filtering**: Supports revenue-based filtering
- **Update Preservation**: Only updates mentioned fields, preserves others
- **Database Connection Test**: Automatically tests connection on startup

## 📋 Project Overview

This project consists of three main components:

1. **Data Generation** (`data/`) - Generate synthetic ICP data based on configurable schemas
2. **Database Setup** - Database-agnostic table creation and data loading utilities
3. **Text-to-SQL Application** - LangGraph-based conversational workflow for SQL generation

## 🏗️ Architecture

### LangGraph Workflow

The system uses a state machine workflow with the following nodes:

- **Conversation Manager**: Updates conversation history and context
- **Extract Info**: Extracts structured information using LLM with `ExtractedInfoWithMentioned`
- **Validate Completeness**: Checks required vs recommended fields
- **Request Clarification**: Generates context-aware questions (HITL interrupt point)
- **Map Industry**: Maps industry to SIC codes using LLM
- **Map Title**: Maps titles to tier-based SQL conditions (rule-based with LLM fallback)
- **Generate SQL**: Creates SQL query with full conversation context
- **Validate SQL**: Validates query safety
- **Handle Update**: Processes update requests while preserving unmentioned fields

### Workflow Features

- **State Persistence**: Uses LangGraph checkpointing for state management
- **Conditional Edges**: Routes based on completeness, update requests, and follow-up needs
- **HITL Interrupts**: Pauses workflow to wait for user input
- **Conversation Memory**: Tracks Q&A pairs, corrections, and updates

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync

# Install database driver (choose one)
uv sync --extra postgresql    # For PostgreSQL
uv sync --extra databricks    # For Databricks
uv sync --extra mysql        # For MySQL
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Database Configuration
# Supported: postgresql, databricks, mysql, sqlite, and other SQLAlchemy-compatible databases
DB_TYPE=postgresql  # postgresql, databricks, mysql, sqlite, etc.
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password
# Optional: For Databricks, use DB_TOKEN instead of DB_PASSWORD
# DB_TOKEN=your_databricks_token
# Optional: Database driver (e.g., 'psycopg2', 'pymysql')
# DB_DRIVER=psycopg2
# Optional: Schema name
# DB_SCHEMA=public

# LLM Configuration
LLM_API_KEY=your_api_key
# Optional overrides (defaults shown)
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.3
```

See [DATABASE_CONFIG.md](DATABASE_CONFIG.md) for detailed database configuration examples.

### 3. Generate and Load Data

```bash
# Generate synthetic data (50k records by default)
uv run data/generate_synthetic_data.py

# Create database table and load data
uv run data/load_data.py --csv data/synthetic_icp_data.csv
```

See `data/README.md` for detailed database setup instructions.

### 4. Run the Text-to-SQL Application

```bash
uv run streamlit run app.py
```

The application will:
- **Automatically test database connection** on startup
- Open at `http://localhost:8501`
- Show error and stop if database is not accessible

## 📁 Project Structure

```
text-to-sql/
├── workflows/              # LangGraph workflow implementation
│   ├── __init__.py        # Workflow exports
│   ├── state.py           # WorkflowState TypedDict
│   ├── models.py          # Pydantic models for structured output
│   ├── memory.py          # Conversation memory management
│   ├── text_to_sql_graph.py  # Main workflow graph definition
│   ├── edges.py           # Conditional edge logic
│   └── nodes/             # Modular node implementations
│       ├── __init__.py
│       ├── shared.py      # Shared resources (LLM, prompts, mappers)
│       ├── conversation.py    # Conversation management
│       ├── extraction.py       # Information extraction
│       ├── clarification.py   # Question generation
│       ├── mapping.py         # Industry and title mapping
│       ├── sql_generation.py  # SQL generation and validation
│       └── update.py          # Update request handling
├── prompts/                # LLM prompt templates (YAML)
│   ├── information_extraction_prompt.yaml
│   ├── question_generation_prompt.yaml
│   ├── sql_generation_prompt.yaml
│   └── industry_sic_prompt.yaml
├── data/                   # Data generation and database utilities
│   ├── README.md          # Database setup guide
│   ├── config.json        # Data generation configuration
│   ├── generate_synthetic_data.py
│   ├── load_data.py
│   └── create_table.sql
├── utils/                  # Utility modules
│   ├── common/            # Common utilities
│   │   ├── config.py      # Database and LLM settings
│   │   ├── config_loader.py
│   │   ├── db.py          # Database wrapper (multi-database support)
│   │   └── logger.py      # Centralized logging
│   └── agent/             # Agent-specific utilities
│       ├── industry_mapper.py    # Industry → SIC code mapping
│       ├── title_tier_mapper.py  # Title → Tier mapping
│       ├── sql_validator.py      # SQL validation
│       ├── llm_client.py         # LLM client creation
│       └── prompt_loader.py      # Prompt template loading
├── app.py                  # Main Streamlit application
├── workflow_config.json    # Workflow-specific configuration
├── pyproject.toml         # Project dependencies
├── README.md               # This file
├── DATABASE_CONFIG.md      # Database configuration guide
└── WORKFLOW_DIAGRAM.html   # Interactive workflow diagrams
```

## 🎯 Usage Examples

### Basic Query

```
User: "I sell healthcare insurance in Texas"
Copilot: "What role do you target? What company size?"
User: "owners, below 50 employees"
Copilot: ✅ SQL Query Generated
```

### Update Query

```
User: "add Arizona too"
Copilot: ✅ Updated SQL Query (preserves: healthcare, owners, <50, adds: Arizona)
```

### Contextual Questions

After SQL generation, the system may ask:
- "Would you like to add or remove any filters?"
- "Any specific sales volume you're looking for?"

## ⚙️ Configuration

### Workflow Configuration

Edit `workflow_config.json` to customize:
- Conversation history limits
- Question generation settings
- SQL query max results
- Contextual question limits
- And more...

### Data Generation Configuration

Edit `data/config.json` to customize:
- US states and cities
- SIC codes and domains
- Title tiers and keywords
- Employee size buckets
- Square footage buckets
- Generation probabilities

### Environment Variables

See `.env` example above for:
- Database credentials (`DB_*`)
- LLM configuration (`LLM_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`)

## 🔧 Key Technologies

- **LangGraph**: Workflow orchestration with state machines and checkpointing
- **LangChain**: LLM framework with structured output support
- **OpenAI GPT-4o mini**: LLM for information extraction and SQL generation
- **Streamlit**: Web UI for conversational interface
- **SQLAlchemy**: Database abstraction layer (multi-database support)
- **Pydantic**: Type-safe data models for structured LLM output
- **sqlparse**: SQL query validation

## 🔒 Security & Query Protection

The system implements multiple layers of security to prevent data manipulation and SQL injection attacks:

### 1. **SQL Query Validation** (`utils/agent/sql_validator.py`)
   - **SELECT-only enforcement**: Only SELECT queries are allowed
   - **Dangerous keyword blocking**: Blocks DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, CREATE, EXEC, etc.
   - **SQL injection detection**: Detects common injection patterns
   - **Multiple statement prevention**: Blocks queries with multiple statements
   - **Query parsing**: Uses `sqlparse` library to validate SQL structure

### 2. **Pre-execution Validation** (`utils/common/db.py`)
   - **Double validation**: Queries are validated again before execution
   - **SELECT prefix check**: Ensures query starts with SELECT
   - **Read-only transaction**: Sets database transaction to READ ONLY mode (if supported)

### 3. **Database-Level Protection** (Recommended)
   - **Read-only database user**: Use a database user with only SELECT permissions
   - **Limited table access**: Grant access only to the `icp_data` table
   - **No write permissions**: Database user should not have INSERT, UPDATE, DELETE, DROP permissions

### Example: Creating a Read-Only Database User (PostgreSQL)

```sql
-- Create read-only user
CREATE USER readonly_user WITH PASSWORD 'secure_password';

-- Grant SELECT only on icp_data table
GRANT SELECT ON TABLE icp_data TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;

-- Update .env to use readonly_user
DB_USER=readonly_user
DB_PASSWORD=secure_password
```

## 📊 Workflow Diagrams

View interactive workflow diagrams:
- **WORKFLOW_DIAGRAM.html**: Open in browser for business and technical perspectives
- Includes: Simple flow, sequence diagram, update flow, memory flow, and data flow

## 🧪 Development

### Project Dependencies

Managed via `uv` and `pyproject.toml`:
- LangChain ecosystem (langchain, langchain-openai, langchain-community)
- LangGraph for workflow orchestration
- Streamlit for UI
- Database drivers (install as needed):
  - PostgreSQL: `uv sync --extra postgresql`
  - Databricks: `uv sync --extra databricks`
  - MySQL: `uv sync --extra mysql`
- Pydantic for data validation
- sqlparse for SQL validation

### Code Organization

- **Modular nodes**: Each workflow node in separate file
- **Shared resources**: Singleton pattern for LLM, prompts, mappers
- **Type safety**: Pydantic models for structured output
- **Configuration**: Centralized in `workflow_config.json` and `.env`

## 📚 Documentation

- **README.md**: This file - project overview
- **DATABASE_CONFIG.md**: Database configuration guide
- **data/README.md**: Database setup and data loading guide
- **WORKFLOW_DIAGRAM.html**: Interactive workflow diagrams
- **example_queries.txt**: Example natural language queries for testing

## 🤖 LLM Calls

The system makes 5 LLM calls per workflow execution:

1. **Extract Info**: Extracts structured information from user input
2. **Generate Question**: Creates clarifying questions when needed
3. **Map Industry**: Maps industry descriptions to SIC codes
4. **Generate SQL**: Creates SQL query with conversation context
5. **Follow-up Question**: Generates follow-up questions after SQL generation

Title mapping is primarily rule-based (keyword matching), with LLM fallback during SQL generation if no match is found.

## 📝 License

[Add your license here]
