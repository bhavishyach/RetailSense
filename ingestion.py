"""
RetailSense Bronze Layer Ingestion Pipeline

Reads amazon_products.csv and amazon_categories.csv, performs minimal cleaning,
datatype standardization, duplicate removal, and category enrichment.
Writes cleaned data to the raw_products table in retailsense.db.
"""

import csv
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_categories(csv_path: str) -> Dict[int, str]:
    """
    Load categories CSV and build a lookup dictionary.
    
    Args:
        csv_path: Path to amazon_categories.csv
        
    Returns:
        Dictionary mapping category_id (int) to category_name (str)
    """
    categories = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cat_id = int(row['id'].strip())
                    cat_name = row['category_name'].strip()
                    if cat_id and cat_name:
                        categories[cat_id] = cat_name
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping category row due to parse error: {e}")
        logger.info(f"Loaded {len(categories)} categories from {csv_path}")
    except FileNotFoundError:
        logger.error(f"Categories file not found: {csv_path}")
        raise
    return categories


def parse_float(value: str, field_name: str) -> Optional[float]:
    """Parse a string to float, log errors, return None on failure."""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        logger.debug(f"Failed to parse {field_name} as float: '{value}'")
        return None


def parse_int(value: str, field_name: str) -> Optional[int]:
    """Parse a string to integer, log errors, return None on failure."""
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        logger.debug(f"Failed to parse {field_name} as integer: '{value}'")
        return None


def parse_boolean(value: str, field_name: str) -> Optional[int]:
    """Parse a string to boolean (0/1), log errors, return None on failure."""
    if not value or not value.strip():
        return None
    normalized = value.strip()
    if normalized in ('True', 'true', '1'):
        return 1
    elif normalized in ('False', 'false', '0'):
        return 0
    else:
        logger.debug(f"Failed to parse {field_name} as boolean: '{value}'")
        return None


def process_products(
    csv_path: str,
    categories: Dict[int, str]
) -> Tuple[List[Dict], int, int, int]:
    """
    Read and process products CSV, perform validation and cleaning.
    
    Args:
        csv_path: Path to amazon_products.csv
        categories: Dictionary of category_id -> category_name
        
    Returns:
        Tuple of (valid_records, total_read, skipped_count, duplicate_count)
    """
    valid_records = []
    total_read = 0
    skipped = 0
    duplicates = 0
    seen_asins = set()
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=1):
                total_read += 1
                
                # Validate ASIN (required, primary key)
                asin = row.get('asin', '').strip()
                if not asin:
                    logger.debug(f"Row {row_idx}: Skipping record with missing ASIN")
                    skipped += 1
                    continue
                
                # Check for duplicates (keep first, skip rest)
                if asin in seen_asins:
                    duplicates += 1
                    logger.debug(f"Row {row_idx}: Duplicate ASIN '{asin}' encountered, skipping")
                    continue
                seen_asins.add(asin)
                
                # Extract and validate fields
                try:
                    title = row.get('title', '').strip()
                    
                    # Parse numeric category_id
                    category_id = parse_int(row.get('category_id', ''), 'category_id')
                    if category_id is None:
                        logger.debug(f"Row {row_idx} ({asin}): Invalid category_id, skipping")
                        skipped += 1
                        continue
                    
                    # Get category name from lookup
                    category_name = categories.get(category_id, 'Unknown')
                    
                    # Parse price fields
                    price = parse_float(row.get('price', ''), 'price')
                    list_price = parse_float(row.get('listPrice', ''), 'listPrice')
                    
                    # Parse star_rating
                    star_rating = parse_float(row.get('stars', ''), 'stars')
                    if star_rating is not None and (star_rating < 0 or star_rating > 5):
                        logger.debug(f"Row {row_idx} ({asin}): star_rating out of range [0-5], setting to NULL")
                        star_rating = None
                    
                    # Parse review counts
                    review_count = parse_int(row.get('reviews', ''), 'reviews')
                    monthly_purchases = parse_int(row.get('boughtInLastMonth', ''), 'boughtInLastMonth')
                    
                    # Parse bestseller flag
                    bestseller_flag = parse_boolean(row.get('isBestSeller', ''), 'isBestSeller')
                    
                    # Build record
                    record = {
                        'asin': asin,
                        'title': title,
                        'category_id': category_id,
                        'category_name': category_name,
                        'price': price,
                        'list_price': list_price,
                        'star_rating': star_rating,
                        'review_count': review_count,
                        'bestseller_flag': bestseller_flag,
                        'monthly_purchases': monthly_purchases,
                        'ingested_at': datetime.utcnow().isoformat(),
                        'source_file': csv_path
                    }
                    valid_records.append(record)
                    
                except Exception as e:
                    logger.debug(f"Row {row_idx}: Unexpected error during parsing: {e}")
                    skipped += 1
                    continue
        
        logger.info(f"Processed {total_read} product records from {csv_path}")
        logger.info(f"Valid records: {len(valid_records)}, Skipped: {skipped}, Duplicates: {duplicates}")
        
    except FileNotFoundError:
        logger.error(f"Products file not found: {csv_path}")
        raise
    
    return valid_records, total_read, skipped, duplicates


def create_database_and_table(db_path: str) -> sqlite3.Connection:
    """
    Create SQLite database and raw_products table with finalized schema.
    
    Args:
        db_path: Path to retailsense.db
        
    Returns:
        SQLite connection object
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create raw_products table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS raw_products (
        asin TEXT PRIMARY KEY NOT NULL,
        title TEXT,
        category_id INTEGER,
        category_name TEXT,
        price REAL,
        list_price REAL,
        star_rating REAL,
        review_count INTEGER,
        bestseller_flag INTEGER,
        monthly_purchases INTEGER,
        ingested_at TIMESTAMP NOT NULL,
        source_file TEXT
    );
    """
    cursor.execute(create_table_sql)
    
    # Create index on category_id for join performance
    create_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_raw_products_category_id 
    ON raw_products(category_id);
    """
    cursor.execute(create_index_sql)
    
    conn.commit()
    logger.info(f"Created/verified raw_products table in {db_path}")
    return conn


def insert_records(conn: sqlite3.Connection, records: List[Dict]) -> int:
    """
    Bulk insert valid records into raw_products table.
    
    Args:
        conn: SQLite connection
        records: List of validated record dictionaries
        
    Returns:
        Number of records inserted
    """
    cursor = conn.cursor()
    insert_sql = """
    INSERT OR IGNORE INTO raw_products (
        asin, title, category_id, category_name, price, list_price,
        star_rating, review_count, bestseller_flag, monthly_purchases,
        ingested_at, source_file
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    rows_to_insert = [
        (
            rec['asin'],
            rec['title'],
            rec['category_id'],
            rec['category_name'],
            rec['price'],
            rec['list_price'],
            rec['star_rating'],
            rec['review_count'],
            rec['bestseller_flag'],
            rec['monthly_purchases'],
            rec['ingested_at'],
            rec['source_file']
        )
        for rec in records
    ]
    
    try:
        cursor.executemany(insert_sql, rows_to_insert)
        conn.commit()
        inserted = cursor.rowcount
        logger.info(f"Inserted {inserted} records into raw_products")
        return inserted
    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error during insert: {e}")
        conn.rollback()
        return 0


def run_ingestion(
    products_csv: str = 'data/amazon_products.csv',
    categories_csv: str = 'data/amazon_categories.csv',
    db_path: str = 'retailsense.db'
) -> Dict[str, int]:
    """
    Execute the complete Bronze layer ingestion pipeline.
    
    Args:
        products_csv: Path to amazon_products.csv
        categories_csv: Path to amazon_categories.csv
        db_path: Path to retailsense.db
        
    Returns:
        Dictionary with ingestion summary statistics
    """
    logger.info("=" * 80)
    logger.info("Starting RetailSense Bronze Layer Ingestion")
    logger.info("=" * 80)
    
    try:
        # Load categories
        categories = load_categories(categories_csv)
        
        # Process products
        valid_records, total_read, skipped, duplicates = process_products(
            products_csv, categories
        )
        
        # Create database and table
        conn = create_database_and_table(db_path)
        
        # Insert records
        inserted = insert_records(conn, valid_records)
        conn.close()
        
        # Summary
        summary = {
            'total_read': total_read,
            'inserted': inserted,
            'skipped': skipped,
            'duplicates': duplicates,
            'categories_loaded': len(categories)
        }
        
        logger.info("=" * 80)
        logger.info("Ingestion Summary")
        logger.info("=" * 80)
        logger.info(f"Products read:       {summary['total_read']}")
        logger.info(f"Records inserted:    {summary['inserted']}")
        logger.info(f"Records skipped:     {summary['skipped']}")
        logger.info(f"Duplicate ASINs:     {summary['duplicates']}")
        logger.info(f"Categories loaded:   {summary['categories_loaded']}")
        logger.info(f"Database created:    {db_path}")
        logger.info("=" * 80)
        
        return summary
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    run_ingestion()
