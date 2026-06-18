# data-ingestion

A configuration-driven ETL pipeline for ingesting structured data into PostgreSQL.

The project demonstrates modular ingestion, schema validation, reject handling, dynamic table creation, UPSERT loading, logging, and automated testing.

## Features

* YAML-driven ingestion workflows
* CSV and JSON source support
* Automatic PostgreSQL table creation
* Schema-based type casting
* Primary key enforcement
* Rule-based validation
* Reject auditing via `stg_rejects`
* UPSERT loading strategy
* Pytest unit testing and coverage reporting
* Structured logging

## Architecture

```text
Reader
  ↓
Validator
  ↓
Cleaner
  ↓
Loader
  ↓
PostgreSQL

Rejected Records
        ↓
   stg_rejects
```

## Repository Structure

```text
src/
├── cleaners/
├── database/
├── loaders/
├── loggers/
├── readers/
├── tests/
├── utils/
├── validators/
└── main.py
```

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

## Requirements

* Python 3.11+
* PostgreSQL

## Setup

```bash
python -m venv .venv
pip install -r requirements.txt
```

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/database
```

## Running

```bash
python src/main.py
```

## Testing

```bash
pytest
pytest --cov --cov-report=term-missing
```

## Future Enhancements

* Open-Meteo API ingestion
* NOAA GSOM remote CSV ingestion
* Integration testing
* Docker support
* GitHub Actions CI/CD
* Incremental loading
* ETL audit tracking

## Design Principles

* Thin orchestration layer
* Configuration over hardcoding
* Modular processing stages
* Testable components
* Fail-fast validation
* Explicit reject handling

