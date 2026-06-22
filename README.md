# Data Ingestion Sub-System

Configuration-driven ETL pipeline for ingesting structured data into PostgreSQL.

The system implements modular ingestion with validation, transformation, reject handling, and structured loading into staging (bronze) tables.

---

## Features

- YAML-driven ingestion workflows  
- CSV and JSON source support  
- PostgreSQL staging table creation  
- Schema-based type casting  
- Primary key enforcement  
- Rule-based validation  
- Reject capture via `stg_rejects`  
- Upsert-based loading strategy  
- Structured logging  
- Unit tests with pytest and coverage reporting  

---

## Architecture

### Pipeline Flow

```text
CSV / JSON / API Sources
        ↓
Reader (extract raw data)
        ↓
Validator (schema + rule checks)
        ↓
Cleaner (type casting + normalization)
        ↓
Loader (insert into PostgreSQL staging tables)
        ↓
stg_* tables (clean dataset)
```

---

### Reject Flow

```text
Invalid Records
        ↓
Validation Failure Reason Attached
        ↓
stg_rejects (audit table for debugging and replay)
```

---

## Repository Structure

```text
src/
├── cleaners/        # Data normalization and type casting
├── database/        # PostgreSQL connection + query execution
├── loaders/         # Insert and upsert logic
├── loggers/         # Structured logging utilities
├── readers/         # CSV, JSON, API ingestion
├── tests/           # Unit and integration tests
├── utils/           # Shared helpers
├── validators/      # Schema + rule validation engine
└── main.py          # Pipeline entry point
```

---

## Configuration Example

```yaml
sources:
  - name: weather_data
    type: json
    target_table: stg_weather

    pk:
      - time

    schema:
      time: datetime
      temperature: float

    rules:
      - temperature >= -100
```

---

## Requirements

- Python 3.11+
- PostgreSQL

---

## Setup

```bash
python -m venv .venv
pip install -r requirements.txt
```

Environment variables:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/database
```

---

## Running

```bash
python src/main.py
```

---

## Testing

```bash
pytest
pytest --cov --cov-report=term-missing
```

---

## Future Enhancements

- Open-Meteo API ingestion  
- NOAA GSOM ingestion  
- Integration testing  
- Docker support  
- CI/CD pipeline  
- Incremental loading  
- Audit tracking  

---

## Design Principles

- Modular pipeline stages (extract → validate → transform → load)  
- Configuration-driven design  
- Explicit reject handling (no silent failures)  
- Reproducibility and idempotency  
- Testable components  