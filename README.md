# RetailSense AI

RetailSense AI is an end-to-end retail data enrichment platform that turns messy product catalog data into structured, standardized, and quality-scored records using AI.

The project follows a medallion-style architecture:

- Bronze: ingest and clean raw product data
- Silver: enrich records with AI-generated descriptions, categories, and attributes
- Gold: evaluate output quality and publish metrics for monitoring and analysis

RetailSense is designed to solve a very real retail problem: product catalogs often contain inconsistent categories, incomplete descriptions, and conflicting attributes across suppliers. This pipeline helps normalize that data and track how well the AI is performing over time.

---

## Why this project exists

Large retailers deal with product catalogs that are noisy, inconsistent, and constantly changing. Without standardization, search, recommendations, analytics, and merchandising all break down.

RetailSense AI addresses this by building a practical data pipeline that:

- ingests raw product records
- sends them through an AI enrichment step
- evaluates the quality of the output
- stores the results for downstream analysis and dashboarding

---

## Project architecture

```text
Raw Product Data
    ↓
Bronze Layer (ingestion)
    ↓
Silver Layer (AI enrichment)
    ↓
Gold Layer (evaluation + metrics)
    ↓
Dashboard / Monitoring
```

### Layers

- Bronze layer
  - Reads raw product and category data
  - Performs basic cleaning and validation
  - Stores structured records in SQLite

- Silver layer
  - Reads Bronze data
  - Sends records to the Anthropic Claude API
  - Produces standardized categories, descriptions, and attributes
  - Stores enriched outputs in SQLite

- Gold layer
  - Evaluates each enriched record
  - Calculates quality metrics and flags
  - Writes evaluation results to PostgreSQL for analytics and reporting

---

## Repository structure

```text
.
├── ingestion.py          # Bronze ingestion pipeline
├── enrichment.py         # Silver enrichment pipeline
├── evaluation.py         # Gold evaluation framework
├── dashboard.py          # Streamlit dashboard
├── docker-compose.yml    # Local Postgres + dashboard setup
├── requirements.txt      # Python dependencies
├── data/                 # Raw product and category datasets
├── docs/                 # Project documentation
├── airflow/              # Airflow orchestration assets
├── tests/                # Unit and integration tests
└── retailsense.db        # Local SQLite database for Bronze/Silver data
```

---

## Tech stack

- Python 3.9+
- SQLite for Bronze/Silver storage
- PostgreSQL for Gold evaluation outputs
- Anthropic Claude API for AI enrichment
- Streamlit for the dashboard
- Airflow for orchestration
- Pytest for automated testing
- Docker for containerized local execution

---

## Getting started

### 1. Clone the repository

```bash
git clone <repo-url>
cd RetailSense
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your API key

The Silver layer uses the Anthropic API for enrichment. Set your API key before running enrichment:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

---

## Running the pipeline

### Ingest raw data

```bash
python ingestion.py
```

### Enrich records with AI

```bash
python enrichment.py
```

### Run evaluation and publish Gold metrics

```bash
python evaluation.py
```

These steps populate the Bronze and Silver SQLite tables and generate Gold evaluation results in PostgreSQL.

---

## Running the dashboard

The Streamlit dashboard can be launched locally with:

```bash
streamlit run dashboard.py
```

The dashboard is intended to show pipeline health, enrichment quality trends, and category-level performance.

---

## Running with Docker

A Docker Compose setup is included for the PostgreSQL-backed dashboard environment:

```bash
docker compose up --build
```

This starts the dashboard service and PostgreSQL container for the Gold layer.

---

## Testing

Run the test suite with:

```bash
pytest
```

The repository includes tests for ingestion, enrichment, and evaluation logic.

---

## Documentation

Project documentation lives in the docs directory and covers:

- product requirements
- high-level design
- sequence flow
- lessons learned and future improvements

---

## Current status

This repository currently includes:

- Bronze ingestion pipeline
- Silver enrichment pipeline
- Gold evaluation framework
- PostgreSQL integration for Gold metrics
- Streamlit dashboard scaffolding
- Docker-based local deployment support

The project is structured as a practical, interview-ready data pipeline rather than a toy demo.

---

## License

This project is intended for educational and portfolio purposes.
