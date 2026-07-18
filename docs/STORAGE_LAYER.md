# Storage Layer

## Purpose
The Storage Layer is responsible for storing the outputs generated throughout the RetailSense pipeline in a structured and queryable format.

## Storage Architecture

### Bronze Layer (SQLite)
Stores raw product records after ingestion.

Table:
- raw_products

Primary Key:
- asin

---

### Silver Layer (SQLite)
Stores AI-enriched product records.

Table:
- enriched_products

Primary Key:
- asin

---

### Gold Layer (PostgreSQL)
Stores evaluation metrics.

Tables:
- gold_pipeline_runs
- gold_record_outcomes
- gold_category_metrics

---

## Relationships
The `asin` field links the raw product in Bronze to its enriched version in Silver and its evaluation results in Gold.

The `run_id` field links all Gold tables belonging to the same evaluation run.

---

## Duplicate Prevention
Before enrichment, the pipeline checks whether the product already exists in the Silver layer. If it does, the record is skipped, preventing duplicate enrichment.

---

## Example Queries

### Find low-confidence products

```sql
SELECT *
FROM gold_record_outcomes
WHERE quality_flags::text LIKE '%LOW_CONFIDENCE%';