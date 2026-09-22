"""
RetailSense Silver Layer Enrichment Pipeline

Reads raw_products from retailsense.db, sends batches to a local Ollama model,
receives structured AI outputs, and writes results to enriched_products.
"""

import argparse
import csv
import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = 'retailsense.db'
RAW_TABLE = 'raw_products'
ENRICHED_TABLE = 'enriched_products'
DEFAULT_BATCH_SIZE = 5
DEFAULT_RATE_LIMIT = 1.0
DEFAULT_MAX_TOKENS = 300
DEFAULT_MODEL = 'qwen3.5:9b'
DEFAULT_API_URL = 'http://localhost:11434/v1'


def ensure_enriched_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {ENRICHED_TABLE} (
            asin TEXT PRIMARY KEY,
            title TEXT,
            category_name TEXT,
            standardized_category TEXT,
            generated_description TEXT,
            attributes TEXT,
            confidence_score REAL,
            latency_ms REAL,
            enrichment_status TEXT,
            failure_reason TEXT,
            enriched_at TIMESTAMP,
            model_version TEXT,
            FOREIGN KEY (asin) REFERENCES {RAW_TABLE}(asin)
        );
    """)
    conn.commit()


def fetch_pending_records(
    conn: sqlite3.Connection,
    limit: int
) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = f"""
        SELECT rp.asin,
               rp.title,
               rp.category_name,
               rp.price,
               rp.list_price,
               rp.star_rating,
               rp.review_count,
               rp.bestseller_flag,
               rp.monthly_purchases
        FROM {RAW_TABLE} AS rp
        LEFT JOIN {ENRICHED_TABLE} AS ep
          ON rp.asin = ep.asin
        WHERE ep.asin IS NULL
        ORDER BY rp.asin
        LIMIT ?
    """
    cursor.execute(query, (limit,))
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def build_prompt(records: List[Dict[str, Any]]) -> str:
    template = (
        "You are a retail product enrichment assistant. For each product, return a JSON array of objects with exact structure.\n\n"
        "**Output Requirements:**\n"
        "- Return ONLY a valid JSON array. No markdown, explanations, or text outside the array.\n"
        "- Each object must have these exact keys: asin, standardized_category, generated_description, attributes, confidence_score\n\n"
        "**Field Definitions:**\n\n"
        "asin: Product identifier (must match input)\n\n"
        "standardized_category: A clean, normalized product category. Rules:\n"
        "  - Remove redundant qualifiers (e.g., 'Supplies', 'Products', 'Accessories')\n"
        "  - Fix obvious typos or category mismatches\n"
        "  - Use common retail category names\n"
        "  - If original category seems incorrect, infer from title and price signals\n"
        "  - Be concise (2-4 words max)\n\n"
        "generated_description: A one-sentence product description (40-80 words). Rules:\n"
        "  - Summarize what the product is\n"
        "  - Mention key characteristics evident from title, price, or category\n"
        "  - Be factual and avoid marketing language\n"
        "  - Do NOT copy the title verbatim\n\n"
        "attributes: A JSON object with extracted product attributes. Rules:\n"
        "  - Extract 3-5 most relevant attributes for this category\n"
        "  - Only extract attributes you can infer from the data\n"
        "  - Use lowercase key names\n"
        "  - For unknown attributes, omit the key entirely (do NOT use 'Unknown')\n"
        "  - Return empty object {} if no attributes can be extracted\n\n"
        "confidence_score: A number 0.0-1.0 indicating enrichment confidence. Rules:\n"
        "  - 0.8-1.0: High confidence. Clear category, complete data, easily inferred attributes\n"
        "  - 0.5-0.7: Medium confidence. Some data missing, slightly unclear category\n"
        "  - 0.0-0.4: Low confidence. Sparse data, contradictory signals, or impossible category\n"
        "  - Calculate based on: data completeness, category clarity, attribute extractability\n"
        "  - If title is empty or <10 characters: set confidence ≤ 0.3\n"
        "  - If category is obviously wrong: infer correct one, set confidence 0.6-0.7\n\n"
        "**Edge Cases:**\n"
        "- If any field is missing or unclear, do NOT invent data; use best judgment or lower confidence_score\n\n"
        "Return ONLY the JSON array. No other text."
    )
    payload = {
        'products': [
            {
                'asin': record['asin'],
                'title': record['title'],
                'category_name': record['category_name'],
                'price': record['price'],
                'list_price': record['list_price'],
                'star_rating': record['star_rating'],
                'review_count': record['review_count'],
                'bestseller_flag': bool(record['bestseller_flag']),
                'monthly_purchases': record['monthly_purchases'],
            }
            for record in records
        ]
    }
    prompt = (
        f"{template}\n\n"
        f"Products JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Return only valid JSON."
    )
    return prompt


def call_local_api(
    prompt: str,
    api_url: str,
    model: str,
    max_tokens: int,
    temperature: float = 0.0,
    max_retries: int = 3
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError('The OpenAI Python SDK is required for local Ollama mode') from exc

    client = OpenAI(base_url=api_url, api_key='ollama')

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort='none',
                extra_body={'think': False, 'format': 'json'},
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError('Ollama response contained no message content')
            return content
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)


def parse_claude_output(raw_output: str) -> List[Dict[str, Any]]:
    cleaned = raw_output.strip()
    if cleaned.startswith('['):
        parsed, _ = json.JSONDecoder().raw_decode(cleaned)
        return parsed
    if cleaned.startswith('{'):
        parsed, _ = json.JSONDecoder().raw_decode(cleaned)
        if isinstance(parsed, dict) and 'products' in parsed:
            return parsed['products']
        raise ValueError('Expected a JSON array or object with products')
    # Find JSON array inside text
    start = cleaned.find('[')
    end = cleaned.rfind(']')
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start:end + 1])
    raise ValueError('Unable to parse JSON from Claude output')


def prepare_enrichment_rows(
    records: List[Dict[str, Any]],
    response_items: List[Dict[str, Any]],
    latency_ms: float,
    model_version: str,
    failure_reason: Optional[str] = None
) -> List[Dict[str, Any]]:
    mapped = []
    record_map = {record['asin']: record for record in records}

    if failure_reason is not None:
        for record in records:
            mapped.append(
                {
                    'asin': record['asin'],
                    'title': record.get('title'),
                    'category_name': record.get('category_name'),
                    'standardized_category': None,
                    'generated_description': None,
                    'attributes': None,
                    'confidence_score': None,
                    'latency_ms': latency_ms,
                    'enrichment_status': 'failed',
                    'failure_reason': failure_reason,
                    'enriched_at': datetime.utcnow().isoformat(),
                    'model_version': model_version,
                }
            )
        return mapped

    for item in response_items:
        asin = item.get('asin')
        if asin not in record_map:
            raise ValueError(f"Local model response contains unknown ASIN: {asin}")
        record = record_map[asin]
        mapped.append(
            {
                'asin': asin,
                'title': record.get('title'),
                'category_name': record.get('category_name'),
                'standardized_category': item.get('standardized_category'),
                'generated_description': item.get('generated_description'),
                'attributes': json.dumps(item.get('attributes', {}), ensure_ascii=False) if item.get('attributes') is not None else None,
                'confidence_score': float(item['confidence_score']) if item.get('confidence_score') is not None else None,
                'latency_ms': latency_ms,
                'enrichment_status': 'success',
                'failure_reason': None,
                'enriched_at': datetime.utcnow().isoformat(),
                'model_version': model_version,
            }
        )
    return mapped


def insert_enriched_records(conn: sqlite3.Connection, records: List[Dict[str, Any]]) -> int:
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')
    insert_sql = f"""
        INSERT OR IGNORE INTO {ENRICHED_TABLE} (
            asin,
            title,
            category_name,
            standardized_category,
            generated_description,
            attributes,
            confidence_score,
            latency_ms,
            enrichment_status,
            failure_reason,
            enriched_at,
            model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows = [
        (
            rec['asin'],
            rec['title'],
            rec['category_name'],
            rec['standardized_category'],
            rec['generated_description'],
            rec['attributes'],
            rec['confidence_score'],
            rec['latency_ms'],
            rec['enrichment_status'],
            rec['failure_reason'],
            rec['enriched_at'],
            rec['model_version'],
        )
        for rec in records
    ]
    cursor.executemany(insert_sql, rows)
    conn.commit()
    return cursor.rowcount


def mock_claude_response(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate mock enrichment responses that follow the improved prompt guidelines.
    This simulates what Claude would return with the enhanced prompt.
    """
    output = []
    
    for record in records:
        asin = record['asin']
        title = record.get('title', '').strip()
        category = record.get('category_name', '').strip()
        price = record.get('price')
        star_rating = record.get('star_rating')
        review_count = record.get('review_count')
        
        # Calculate confidence based on data completeness
        confidence = 0.85
        if not title or len(title) < 10:
            confidence = 0.3
        elif review_count == 0:
            confidence = 0.65
        elif price and star_rating and review_count > 10:
            confidence = 0.88
        
        # Standardize category (remove redundant qualifiers)
        std_category = category
        for suffix in [' Supplies', ' Products', ' Accessories', ' & Accessories']:
            if std_category.endswith(suffix):
                std_category = std_category[:-len(suffix)]
        
        # Generate realistic description based on title and category
        desc_parts = []
        if title:
            desc_parts.append(title[:50])
        if price:
            desc_parts.append(f"priced at ${price:.2f}")
        if star_rating:
            desc_parts.append(f"rated {star_rating}/5 stars")
        description = ". ".join(desc_parts[:2]) + "."
        
        # Extract category-specific attributes
        attributes = {}
        title_lower = title.lower()
        
        if 'luggage' in category.lower() or 'suitcase' in title_lower:
            attributes = {
                'type': 'rolling luggage',
                'material': 'polycarbonate',
                'size_inches': '28-29'
            }
        elif 'clothing' in category.lower() or 'apparel' in category.lower():
            attributes = {
                'material': 'cotton blend',
                'size_range': 'XS-XL',
                'color': 'assorted'
            }
        elif 'book' in category.lower() or any(word in title_lower for word in ['guide', 'manual', 'novel']):
            attributes = {
                'format': 'hardcover',
                'genre': 'non-fiction',
                'pages': '200-400'
            }
        elif 'electronics' in category.lower() or 'gadget' in title_lower:
            attributes = {
                'brand': 'premium',
                'connectivity': 'wireless',
                'battery_life': '8-12 hours'
            }
        else:
            attributes = {}
        
        output.append({
            'asin': asin,
            'standardized_category': std_category,
            'generated_description': description,
            'attributes': attributes,
            'confidence_score': round(confidence, 2)
        })
    
    return output


def enrich_batch(
    conn: sqlite3.Connection,
    batch: List[Dict[str, Any]],
    api_url: str,
    api_key: Optional[str],
    model: str,
    max_tokens: int,
    rate_limit: float,
    use_mock: bool
) -> Tuple[int, float]:
    prompt = build_prompt(batch)
    start_time = time.perf_counter()
    model_version = model
    try:
        if use_mock:
            response_items = mock_claude_response(batch)
        else:
            raw_output = call_local_api(prompt, api_url, model, max_tokens)
            response_items = parse_claude_output(raw_output)
            if len(response_items) != len(batch):
                raise ValueError(
                    f'Local model returned {len(response_items)} results for {len(batch)} products'
                )
        latency_ms = round((time.perf_counter() - start_time) * 1000, 3)
        enriched_rows = prepare_enrichment_rows(batch, response_items, latency_ms, model_version)
        inserted = insert_enriched_records(conn, enriched_rows)
        successful = sum(1 for row in enriched_rows if row['enrichment_status'] == 'success')
        logger = get_logger()
        logger.info(f"Enriched batch of {len(batch)} ASINs in {latency_ms}ms (inserted {inserted})")
        time.sleep(rate_limit)
        return inserted, latency_ms
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 3)
        failure_reason = str(exc)
        failed_rows = prepare_enrichment_rows(batch, [], latency_ms, model_version, failure_reason=failure_reason)
        inserted = insert_enriched_records(conn, failed_rows)
        logger = get_logger()
        logger.error(f"Batch enrichment failed: {failure_reason}")
        time.sleep(rate_limit)
        return inserted, latency_ms


def get_logger():
    import logging
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def run_enrichment(
    db_path: str,
    batch_size: int,
    max_tokens: int,
    rate_limit: float,
    model: str,
    api_url: str,
    api_key: Optional[str],
    use_mock: bool,
    total_limit: Optional[int]
) -> Dict[str, Any]:
    logger = get_logger()
    logger.info('Starting RetailSense Silver Layer Enrichment')
    logger.info(f'Database: {db_path}')
    logger.info(f'Batch size: {batch_size}, rate limit: {rate_limit}s, max tokens: {max_tokens}')
    logger.info(f'Model: {model}, API URL: {api_url}')
    logger.info(f'Using mock mode: {use_mock}')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_enriched_table(conn)

    total_pending = 0
    total_inserted = 0
    total_batches = 0
    overall_start = time.perf_counter()

    remaining = total_limit if total_limit is not None and total_limit > 0 else None
    while True:
        current_limit = batch_size if remaining is None else min(batch_size, remaining)
        batch = fetch_pending_records(conn, current_limit)
        if not batch:
            break
        total_pending += len(batch)
        total_batches += 1
        inserted, latency_ms = enrich_batch(
            conn=conn,
            batch=batch,
            api_url=api_url,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            rate_limit=rate_limit,
            use_mock=use_mock,
        )
        total_inserted += inserted
        if remaining is not None:
            remaining -= len(batch)
            if remaining <= 0:
                break

    elapsed = time.perf_counter() - overall_start
    logger.info('Enrichment complete')
    logger.info(f'Total batches processed: {total_batches}')
    logger.info(f'Total records attempted: {total_pending}')
    logger.info(f'Total records inserted: {total_inserted}')
    logger.info(f'Total elapsed time: {elapsed:.2f}s')
    conn.close()
    return {
        'total_batches': total_batches,
        'total_attempted': total_pending,
        'total_inserted': total_inserted,
        'elapsed_seconds': elapsed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='RetailSense Silver Layer Enrichment')
    parser.add_argument('--db-path', default=DB_PATH, help='Path to retailsense.db')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help='Number of products per local model request')
    parser.add_argument('--rate-limit', type=float, default=DEFAULT_RATE_LIMIT, help='Seconds between enrichment batches')
    parser.add_argument('--max-tokens', type=int, default=DEFAULT_MAX_TOKENS, help='Maximum output tokens for the local model')
    parser.add_argument('--model', default=os.getenv('OLLAMA_MODEL', DEFAULT_MODEL), help='Ollama model identifier')
    parser.add_argument('--api-url', default=os.getenv('OLLAMA_API_URL', DEFAULT_API_URL), help='OpenAI-compatible Ollama base URL')
    parser.add_argument('--limit', type=int, default=5, help='Total number of records to enrich for validation; set 0 for all pending records')
    parser.add_argument('--local', action='store_true', help='Use the local Ollama model (the default unless --mock is set)')
    parser.add_argument('--mock', action='store_true', help='Use mock responses instead of calling Ollama')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    use_mock = args.mock
    if args.mock and args.local:
        raise ValueError('--mock and --local cannot be used together')

    total_limit = None if args.limit == 0 else args.limit
    run_enrichment(
        db_path=args.db_path,
        batch_size=args.batch_size,
        max_tokens=args.max_tokens,
        rate_limit=args.rate_limit,
        model=args.model,
        api_url=args.api_url,
        api_key='ollama',
        use_mock=use_mock,
        total_limit=total_limit,
    )


if __name__ == '__main__':
    main()
