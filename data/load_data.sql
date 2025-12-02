-- Copy data from CSV file
-- Note: Adjust the file path to match your CSV location
COPY icp_data(geography, industry, title, title_tier, employee_size, sales_volume, square_footage)
FROM '/path/to/synthetic_icp_data.csv'
WITH (FORMAT csv, HEADER true, NULL '');

-- Verify data loaded correctly
SELECT COUNT(*) as total_records FROM icp_data;
SELECT COUNT(*) as records_with_square_footage FROM icp_data WHERE square_footage IS NOT NULL;
