CREATE TABLE IF NOT EXISTS icp_data (
    id SERIAL PRIMARY KEY,
    geography VARCHAR(100) NOT NULL,
    industry VARCHAR(4) NOT NULL,  -- 4-digit SIC code (0000-8999)
    title VARCHAR(100) NOT NULL,
    title_tier VARCHAR(10),  -- 'tier_i', 'tier_ii', 'tier_iii', or NULL
    employee_size INTEGER NOT NULL,
    sales_volume BIGINT,
    square_footage INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

