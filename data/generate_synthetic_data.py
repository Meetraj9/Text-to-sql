"""
Script to generate synthetic ICP (Ideal Customer Profile) data based on the schema.
Generates core filters (Geography, Industry, Title, Employee Size) and square footage ranges.
"""

import csv
import random
from pathlib import Path
from typing import Dict, Optional

from faker import Faker

from utils.common.config_loader import load_config

fake = Faker('en_US')


class DataGenerator:
    """Generate synthetic ICP data based on configuration."""
    
    def __init__(self, config_path: str = None):
        """Initialize generator with configuration."""
        if config_path is None:
            # Default to config.json in same directory (data folder)
            config_path = Path(__file__).parent / 'config.json'
        self.config = load_config(config_path)
        self.us_states = self.config['us_states']
        configured_codes = self.config.get('sic_codes', [])
        if configured_codes:
            self.sic_codes = [self._normalize_sic_code(code) for code in configured_codes]
        else:
            self.sic_codes = [f"{i:04d}" for i in range(0, 9000)]
        self.title_tiers = self.config.get('title_tiers', {})
        self.employee_size_buckets = self.config.get('employee_size_buckets', {})
        
        # Generation settings
        settings = self.config.get('generation_settings', {})
        self.state_probability = settings.get('state_probability', 0.7)
        self.tier_i_probability = settings.get('tier_i_probability', 0.83)
        self.tier_ii_probability = settings.get('tier_ii_probability', 0.12)
        self.tier_iii_probability = settings.get('tier_iii_probability', 0.05)
        
        # Build domain mapping from SIC codes
        self.common_industry_codes = [
            self._normalize_sic_code(code)
            for code in self.config.get(
                'common_industry_codes',
                ["7342", "5812", "7349", "1521", "1522", "1531", "1541", "1542"]
            )
        ]
        self.common_industry_weight = settings.get('common_industry_weight', 0.2)
        
        # Pre-shuffle SIC codes to guarantee broad coverage before repeats
        self._diverse_pool = self.sic_codes.copy()
        random.shuffle(self._diverse_pool)
        self._diverse_index = 0
    def _next_diverse_sic_code(self) -> str:
        """Return SIC codes in a shuffled cycle to ensure full coverage."""
        if not self._diverse_pool:
            self._diverse_pool = self.sic_codes.copy()
            random.shuffle(self._diverse_pool)
            self._diverse_index = 0
        
        if self._diverse_index >= len(self._diverse_pool):
            random.shuffle(self._diverse_pool)
            self._diverse_index = 0
        
        code = self._diverse_pool[self._diverse_index]
        self._diverse_index += 1
        return code
    
    
    @staticmethod
    def _normalize_sic_code(code: str) -> str:
        """Ensure SIC code is a zero-padded 4-digit string."""
        digits = ''.join(filter(str.isdigit, str(code)))
        if not digits:
            return "0000"
        digits = digits[:4]
        return digits.zfill(4)
    
    def generate_geography(self) -> str:
        """Generate geography (state or city)."""
        if random.random() < self.state_probability:
            return random.choice(self.us_states)
        else:
            return fake.city()
    
    def generate_industry(self) -> str:
        """Generate a 4-digit SIC code string (0000-8999) with diverse coverage."""
        if not self.sic_codes:
            return f"{random.randint(0, 8999):04d}"
        return self._next_diverse_sic_code()
    
    def generate_industry_weighted(self) -> str:
        """
        Generate industry with weighted selection to ensure common industries appear more often.
        Returns a 4-digit SIC code string.
        """
        if (
            self.common_industry_codes
            and random.random() < self.common_industry_weight
        ):
            sic_code = random.choice(self.common_industry_codes)
            return self._normalize_sic_code(sic_code)
        
        return self.generate_industry()
    
    def generate_title(self) -> tuple[str, str]:
        """Generate decision maker title based on tiers. Returns (title, tier)."""
        rand = random.random()
        if rand < self.tier_i_probability:
            title = random.choice(self.title_tiers.get('tier_i', []))
            return title, 'tier_i'
        elif rand < self.tier_i_probability + self.tier_ii_probability:
            title = random.choice(self.title_tiers.get('tier_ii', []))
            return title, 'tier_ii'
        else:
            title = random.choice(self.title_tiers.get('tier_iii', []))
            return title, 'tier_iii'
    
    def generate_employee_size(self) -> tuple:
        """Generate employee size bucket and single value."""
        bucket_name = random.choice(list(self.employee_size_buckets.keys()))
        bucket = self.employee_size_buckets[bucket_name]
        employee_count = random.randint(bucket['min'], bucket['max'])
        return bucket_name, employee_count
    
    def generate_square_footage(self, employee_count: int) -> int:
        """
        Generate numeric square footage value for every record.
        Relates square footage loosely to employee size with random variation.
        """
        if employee_count <= 20:
            base_min, base_max = 500, 4000
        elif employee_count <= 200:
            base_min, base_max = 2000, 18000
        else:
            base_min, base_max = 10000, 50000
        
        return random.randint(base_min, base_max)
    
    def generate_sales_volume(self, employee_count: int) -> int:
        """Generate numeric sales volume value based on employee size."""
        # Relate sales volume to employee size
        # Rough estimate: $100K-$500K revenue per employee
        # Buckets for filtering: Low (<$5M), Medium ($5M-$50M), High ($50M+)
        
        if employee_count <= 20:
            # Micro: Low sales volume (<$5M)
            # Range: $100K - $4.5M
            sales_volume = random.randint(100000, 4500000)
        elif employee_count <= 200:
            # Small-Medium: Mix of Low and Medium ($100K - $45M)
            # Most will be in Low-Medium range
            if random.random() < 0.6:
                # Low range: $100K - $4.5M
                sales_volume = random.randint(100000, 4500000)
            else:
                # Medium range: $5M - $45M
                sales_volume = random.randint(5000000, 45000000)
        else:
            # Enterprise: Medium to High ($5M - $200M+)
            if random.random() < 0.3:
                # Medium range: $5M - $45M
                sales_volume = random.randint(5000000, 45000000)
            else:
                # High range: $50M - $200M
                sales_volume = random.randint(50000000, 200000000)
        
        return sales_volume
    
    def generate_record(self) -> Dict[str, Optional[str]]:
        """Generate a single ICP record."""
        industry = self.generate_industry_weighted()
        employee_bucket, employee_count = self.generate_employee_size()
        square_footage = self.generate_square_footage(employee_count)
        sales_volume = self.generate_sales_volume(employee_count)
        title, title_tier = self.generate_title()
        
        record = {
            'Geography': self.generate_geography(),
            'Industry': industry,
            'Title': title,
            'Title Tier': title_tier,
            'Employee Size': str(employee_count),
            'Sales Volume': str(sales_volume),
            'Square Footage': str(square_footage),  # Square footage is generated for every record
        }
        
        return record
    
    def generate_synthetic_data(self, num_records: int = 50000, output_file: str = None):
        """
        Generate synthetic ICP data and save to CSV.
        
        Args:
            num_records: Number of records to generate
            output_file: Output CSV file path (defaults to data/synthetic_icp_data.csv)
        """
        if output_file is None:
            output_file = Path(__file__).parent / 'synthetic_icp_data.csv'
        records = []
        
        print(f"Generating {num_records:,} synthetic ICP records...")
        print("Progress: ", end="", flush=True)
        
        for i in range(num_records):
            records.append(self.generate_record())
            
            # Progress indicator (more frequent for large datasets)
            if (i + 1) % 500 == 0:
                print(".", end="", flush=True)
            if (i + 1) % 5000 == 0:
                print(f" {i + 1:,}", end="", flush=True)
        
        # Write to CSV
        fieldnames = ['Geography', 'Industry', 'Title', 'Title Tier', 'Employee Size', 
                    'Sales Volume', 'Square Footage']
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for record in records:
                # Convert None to empty string for CSV
                csv_record = {k: (v if v is not None else '') for k, v in record.items()}
                writer.writerow(csv_record)
        
        print(f"\nSuccessfully generated {num_records} records and saved to {output_file}")
        
        # Print summary statistics
        print("\nSummary Statistics:")
        print(f"  Total records: {num_records}")
        records_with_sqft = sum(1 for r in records if r.get('Square Footage') is not None)
        print(f"  Records with Square Footage: {records_with_sqft} ({records_with_sqft/num_records*100:.1f}%)")
        
        # Employee size bucket distribution (for reference, not in CSV)
        employee_counts = [int(r.get('Employee Size', 0)) for r in records if r.get('Employee Size')]
        if employee_counts:
            micro = sum(1 for c in employee_counts if 1 <= c <= 20)
            small_medium = sum(1 for c in employee_counts if 21 <= c <= 200)
            enterprise = sum(1 for c in employee_counts if c >= 201)
            print(f"\nEmployee Size Bucket Distribution (for reference):")
            print(f"  Micro (1-20): {micro} ({micro/num_records*100:.1f}%)")
            print(f"  Small-Medium (21-200): {small_medium} ({small_medium/num_records*100:.1f}%)")
            print(f"  Enterprise (200+): {enterprise} ({enterprise/num_records*100:.1f}%)")
        
        # Square footage statistics (numeric values)
        sqft_values = [int(r.get('Square Footage', 0)) for r in records if r.get('Square Footage')]
        if sqft_values:
            print(f"\nSquare Footage Statistics:")
            print(f"  Min: {min(sqft_values):,} sq ft")
            print(f"  Max: {max(sqft_values):,} sq ft")
            print(f"  Average: {sum(sqft_values)/len(sqft_values):,.0f} sq ft")
            
            # Show distribution by bucket ranges (for filtering reference)
            small = sum(1 for v in sqft_values if v < 5000)
            medium = sum(1 for v in sqft_values if 5000 <= v < 20000)
            large = sum(1 for v in sqft_values if v >= 20000)
            print(f"\nSquare Footage Bucket Distribution (for filtering):")
            print(f"  Small (<5,000): {small} ({small/len(sqft_values)*100:.1f}%)")
            print(f"  Medium (5,000-20,000): {medium} ({medium/len(sqft_values)*100:.1f}%)")
            print(f"  Large (20,000+): {large} ({large/len(sqft_values)*100:.1f}%)")
        
        # Sales volume statistics (numeric values)
        sales_values = [int(r.get('Sales Volume', 0)) for r in records if r.get('Sales Volume')]
        if sales_values:
            print(f"\nSales Volume Statistics:")
            print(f"  Min: ${min(sales_values):,}")
            print(f"  Max: ${max(sales_values):,}")
            print(f"  Average: ${sum(sales_values)/len(sales_values):,.0f}")
            
            # Show distribution by bucket ranges (for filtering reference)
            low = sum(1 for v in sales_values if v < 5000000)
            medium = sum(1 for v in sales_values if 5000000 <= v < 50000000)
            high = sum(1 for v in sales_values if v >= 50000000)
            print(f"\nSales Volume Bucket Distribution (for filtering):")
            print(f"  Low (<$5M): {low} ({low/len(sales_values)*100:.1f}%)")
            print(f"  Medium ($5M-$50M): {medium} ({medium/len(sales_values)*100:.1f}%)")
            print(f"  High ($50M+): {high} ({high/len(sales_values)*100:.1f}%)")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate synthetic ICP data')
    parser.add_argument('--num-records', type=int, default=50000,
                        help='Number of records to generate (default: 50000)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output CSV file path (default: data/synthetic_icp_data.csv)')
    parser.add_argument('--config', type=str, default=None,
                        help='Config JSON file path (default: data/config.json)')
    
    args = parser.parse_args()
    
    generator = DataGenerator(config_path=args.config)
    generator.generate_synthetic_data(num_records=args.num_records, output_file=args.output)
