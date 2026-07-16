"""
RetailSense Gold Layer Evaluation Framework

This module evaluates the outputs stored in the Silver layer and writes
per-record evaluation results into the PostgreSQL Gold layer.

Current scope (Step 1): per-record evaluation and insertion into
gold_record_outcomes.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import Json

DB_PATH = 'retailsense.db'
RAW_TABLE = 'raw_products'
ENRICHED_TABLE = 'enriched_products'

LOW_CONFIDENCE_THRESHOLD = 0.6

def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _is_empty_json_object(value: Optional[str]) -> bool:
    if value is None:
        return True
    text = value.strip()
    if not text:
        return True
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return False
    return parsed == {}


def evaluate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a single enriched record and return evaluation details."""
    description = _normalize_text(record.get('generated_description'))
    standardized_category = _normalize_text(record.get('standardized_category'))
    attributes = record.get('attributes')
    confidence_score = record.get('confidence_score')
    enrichment_status = (record.get('enrichment_status') or '').strip().lower()

    flags: List[str] = []

    if confidence_score is None:
        flags.append('LOW_CONFIDENCE')
    elif float(confidence_score) < LOW_CONFIDENCE_THRESHOLD:
        flags.append('LOW_CONFIDENCE')

    if description is None:
        flags.append('MISSING_DESCRIPTION')

    if _is_empty_json_object(attributes):
        flags.append('EMPTY_ATTRIBUTES')

    if standardized_category is None:
        flags.append('MISSING_STANDARDIZED_CATEGORY')

    if enrichment_status == 'failed':
        flags.append('FAILED_ENRICHMENT')

    if enrichment_status == 'failed':
        final_status = 'FAILED'
    elif flags:
        final_status = 'REVIEW'
    else:
        final_status = 'SUCCESS'

    description_present = 1 if description is not None else 0
    attributes_present = 0 if _is_empty_json_object(attributes) else 1
    category_present = 1 if standardized_category is not None else 0

    completeness_score = round((description_present + attributes_present + category_present) / 3.0, 3)

    return {
        'asin': record.get('asin'),
        'completeness_score': completeness_score,
        'quality_flags': flags,
        'final_status': final_status,
    }


def fetch_enriched_records(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Load all enriched records from the Silver SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT asin, title, category_name, standardized_category, generated_description, "
            f"attributes, confidence_score, latency_ms, enrichment_status, failure_reason, "
            f"enriched_at, model_version FROM {ENRICHED_TABLE}"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_postgres_connection() -> psycopg2.extensions.connection:
    """Create a PostgreSQL connection using environment variables or local defaults."""
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE', 'retailsense_gold'),
        user=os.getenv('PGUSER', 'bhavishyachallagolla'),
        password=os.getenv('PGPASSWORD', ''),
        host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'),
    )


def ensure_pipeline_run(
    run_id: str,
    record_count: int,
    conn: psycopg2.extensions.connection,
) -> None:
    """Create a parent pipeline run row so gold_record_outcomes can reference it."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM gold_pipeline_runs WHERE run_id = %s",
            (run_id,),
        )
        exists = cur.fetchone()
        if exists:
            return

        cur.execute(
            """
            INSERT INTO gold_pipeline_runs (
                run_id,
                run_timestamp,
                total_records_processed,
                total_enriched,
                total_failed,
                total_skipped,
                avg_confidence_score,
                avg_latency_ms,
                p50_latency_ms,
                p95_latency_ms,
                failure_rate,
                cost_estimate_usd
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                datetime.utcnow(),
                record_count,
                None,
                None,
                0,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
        )
    conn.commit()


def compute_pipeline_metrics(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute run-level metrics from the evaluated Silver records."""
    total_records = len(records)
    if total_records == 0:
        return {
            'total_records_processed': 0,
            'total_enriched': 0,
            'total_failed': 0,
            'total_skipped': 0,
            'avg_confidence_score': None,
            'avg_latency_ms': None,
            'p50_latency_ms': None,
            'p95_latency_ms': None,
            'failure_rate': None,
            'cost_estimate_usd': 0.0,
        }

    confidences = [float(record.get('confidence_score')) for record in records if record.get('confidence_score') is not None]
    latencies = [float(record.get('latency_ms')) for record in records if record.get('latency_ms') is not None]
    total_enriched = sum(1 for record in records if str(record.get('enrichment_status') or '').strip().lower() == 'success')
    total_failed = sum(1 for record in records if str(record.get('enrichment_status') or '').strip().lower() == 'failed')
    total_skipped = 0

    avg_confidence = sum(confidences) / len(confidences) if confidences else None
    avg_latency = sum(latencies) / len(latencies) if latencies else None

    sorted_latencies = sorted(latencies)
    p50_latency = median(sorted_latencies) if sorted_latencies else None
    p95_latency = None
    if sorted_latencies:
        index = max(0, int(round(0.95 * len(sorted_latencies))) - 1)
        p95_latency = sorted_latencies[min(index, len(sorted_latencies) - 1)]

    failure_rate = total_failed / total_records if total_records else None
    cost_estimate = 0.0

    return {
        'total_records_processed': total_records,
        'total_enriched': total_enriched,
        'total_failed': total_failed,
        'total_skipped': total_skipped,
        'avg_confidence_score': avg_confidence,
        'avg_latency_ms': avg_latency,
        'p50_latency_ms': p50_latency,
        'p95_latency_ms': p95_latency,
        'failure_rate': failure_rate,
        'cost_estimate_usd': cost_estimate,
    }


def update_pipeline_run_metrics(
    run_id: str,
    metrics: Dict[str, Any],
    conn: psycopg2.extensions.connection,
) -> None:
    """Update the existing gold_pipeline_runs row for the provided run_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE gold_pipeline_runs
            SET total_records_processed = %s,
                total_enriched = %s,
                total_failed = %s,
                total_skipped = %s,
                avg_confidence_score = %s,
                avg_latency_ms = %s,
                p50_latency_ms = %s,
                p95_latency_ms = %s,
                failure_rate = %s,
                cost_estimate_usd = %s
            WHERE run_id = %s
            """,
            (
                metrics['total_records_processed'],
                metrics['total_enriched'],
                metrics['total_failed'],
                metrics['total_skipped'],
                metrics['avg_confidence_score'],
                metrics['avg_latency_ms'],
                metrics['p50_latency_ms'],
                metrics['p95_latency_ms'],
                metrics['failure_rate'],
                metrics['cost_estimate_usd'],
                run_id,
            ),
        )
    conn.commit()


def compute_category_metrics(
    records: Sequence[Dict[str, Any]],
    evaluations: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compute category-level metrics directly from the evaluated Silver records."""
    grouped: Dict[str, List[Tuple[Dict[str, Any], Dict[str, Any]]]] = {}
    for record, evaluation_result in zip(records, evaluations):
        category = (record.get('standardized_category') or '').strip() or 'UNCLASSIFIED'
        grouped.setdefault(category, []).append((record, evaluation_result))

    metrics = []
    for category, items in sorted(grouped.items()):
        confidence_values = [float(item[0].get('confidence_score')) for item in items if item[0].get('confidence_score') is not None]
        failures = sum(1 for _, ev in items if str(ev.get('final_status') or '').upper() == 'FAILED')
        completeness_values = [float(ev.get('completeness_score', 0.0)) for _, ev in items]

        metrics.append({
            'category': category,
            'record_count': len(items),
            'avg_confidence': (sum(confidence_values) / len(confidence_values)) if confidence_values else None,
            'failure_rate': (failures / len(items)) if items else None,
            'completeness_score': (sum(completeness_values) / len(completeness_values)) if completeness_values else None,
        })
    return metrics


def insert_category_metrics(
    run_id: str,
    category_metrics: Sequence[Dict[str, Any]],
    conn: psycopg2.extensions.connection,
) -> int:
    """Insert one row per category into gold_category_metrics."""
    with conn.cursor() as cur:
        inserted = 0
        for metric in category_metrics:
            cur.execute(
                """
                INSERT INTO gold_category_metrics (
                    id,
                    run_id,
                    category,
                    record_count,
                    avg_confidence,
                    failure_rate,
                    completeness_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    metric['category'],
                    metric['record_count'],
                    metric['avg_confidence'],
                    metric['failure_rate'],
                    metric['completeness_score'],
                ),
            )
            inserted += 1
        conn.commit()
    return inserted


def insert_record_outcomes(
    records: Sequence[Dict[str, Any]],
    run_id: Optional[str] = None,
    conn: Optional[psycopg2.extensions.connection] = None,
) -> int:
    """Insert one evaluation row per record into gold_record_outcomes."""
    if conn is None:
        conn = get_postgres_connection()
        close_conn = True
    else:
        close_conn = False

    resolved_run_id = run_id or str(uuid.uuid4())

    try:
        ensure_pipeline_run(resolved_run_id, len(records), conn)
        with conn.cursor() as cur:
            inserted = 0
            for record in records:
                evaluation_result = evaluate_record(record)
                payload = {
                    'id': str(uuid.uuid4()),
                    'asin': record.get('asin'),
                    'run_id': resolved_run_id,
                    'final_status': evaluation_result['final_status'],
                    'quality_flags': evaluation_result['quality_flags'],
                    'evaluated_at': datetime.utcnow().isoformat(),
                }
                cur.execute(
                    """
                    INSERT INTO gold_record_outcomes (
                        id, asin, run_id, final_status, quality_flags, evaluated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload['id'],
                        payload['asin'],
                        payload['run_id'],
                        payload['final_status'],
                        Json(payload['quality_flags']),
                        payload['evaluated_at'],
                    ),
                )
                inserted += 1
            conn.commit()
            return inserted
    finally:
        if close_conn:
            conn.close()


def run_record_evaluation(
    db_path: str = DB_PATH,
    run_id: Optional[str] = None,
    conn: Optional[psycopg2.extensions.connection] = None,
) -> Tuple[int, Dict[str, Any], int]:
    """Evaluate all enriched records, insert outcomes, update pipeline metrics, and insert category metrics."""
    records = fetch_enriched_records(db_path=db_path)
    if conn is None:
        conn = get_postgres_connection()
        close_conn = True
    else:
        close_conn = False

    resolved_run_id = run_id or str(uuid.uuid4())
    try:
        ensure_pipeline_run(resolved_run_id, len(records), conn)
        inserted = insert_record_outcomes(records, run_id=resolved_run_id, conn=conn)

        evaluations = [evaluate_record(record) for record in records]
        pipeline_metrics = compute_pipeline_metrics(records)
        update_pipeline_run_metrics(resolved_run_id, pipeline_metrics, conn)

        category_metrics = compute_category_metrics(records, evaluations)
        category_inserted = insert_category_metrics(resolved_run_id, category_metrics, conn)
        return inserted, pipeline_metrics, category_inserted
    finally:
        if close_conn:
            conn.close()
