"""
BigQuery service for the Hospital Queue AI system.

Handles analytics data ingestion and querying via BigQuery.
Creates dataset and tables on first use.

Environment variables:
    GOOGLE_CLOUD_PROJECT: GCP project ID
    BIGQUERY_DATASET: Dataset name (default: hospital_analytics)
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_client = None
_dataset_ready = False

DATASET_ID = os.environ.get("BIGQUERY_DATASET", "hospital_analytics")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")


def _get_client():
    """Get or create BigQuery client."""
    global _client
    if _client is None:
        try:
            from google.cloud import bigquery
            _client = bigquery.Client(project=PROJECT_ID)
            logger.info(f"BigQuery client initialized for project {PROJECT_ID}")
        except Exception as e:
            logger.warning(f"BigQuery client initialization failed: {e}")
            return None
    return _client


def ensure_dataset():
    """Create BigQuery dataset and tables if they don't exist."""
    global _dataset_ready
    if _dataset_ready:
        return True

    client = _get_client()
    if not client:
        return False

    try:
        from google.cloud import bigquery

        dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"

        # Create dataset
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        try:
            client.create_dataset(dataset, exists_ok=True)
            logger.info(f"BigQuery dataset '{dataset_ref}' ready.")
        except Exception as e:
            logger.warning(f"Could not create dataset: {e}")
            return False

        # Create tables
        tables = {
            "patient_events": [
                bigquery.SchemaField("event_id", "STRING"),
                bigquery.SchemaField("event_type", "STRING"),
                bigquery.SchemaField("patient_name", "STRING"),
                bigquery.SchemaField("department", "STRING"),
                bigquery.SchemaField("severity_score", "INTEGER"),
                bigquery.SchemaField("queue_number", "INTEGER"),
                bigquery.SchemaField("event_data", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP"),
            ],
            "queue_metrics": [
                bigquery.SchemaField("department", "STRING"),
                bigquery.SchemaField("patients_waiting", "INTEGER"),
                bigquery.SchemaField("current_load", "INTEGER"),
                bigquery.SchemaField("capacity", "INTEGER"),
                bigquery.SchemaField("load_percentage", "FLOAT"),
                bigquery.SchemaField("congestion_level", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP"),
            ],
            "agent_activity": [
                bigquery.SchemaField("agent_name", "STRING"),
                bigquery.SchemaField("action", "STRING"),
                bigquery.SchemaField("patient_name", "STRING"),
                bigquery.SchemaField("details", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP"),
            ],
        }

        for table_name, schema in tables.items():
            table_ref = f"{dataset_ref}.{table_name}"
            table = bigquery.Table(table_ref, schema=schema)
            try:
                client.create_table(table, exists_ok=True)
                logger.info(f"BigQuery table '{table_ref}' ready.")
            except Exception as e:
                logger.warning(f"Could not create table {table_name}: {e}")

        _dataset_ready = True
        return True

    except Exception as e:
        logger.warning(f"BigQuery setup failed: {e}")
        return False


def insert_event(event_type: str, event_data: str):
    """Insert an analytics event into BigQuery."""
    client = _get_client()
    if not client:
        return

    if not ensure_dataset():
        return

    try:
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.patient_events"
        row = {
            "event_id": f"evt-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "event_type": event_type,
            "patient_name": "",
            "department": "",
            "severity_score": 0,
            "queue_number": 0,
            "event_data": event_data if isinstance(event_data, str) else json.dumps(event_data),
            "timestamp": datetime.utcnow().isoformat(),
        }
        errors = client.insert_rows_json(table_ref, [row])
        if errors:
            logger.warning(f"BigQuery insert errors: {errors}")
        else:
            logger.info(f"Event '{event_type}' logged to BigQuery.")
    except Exception as e:
        logger.warning(f"BigQuery insert failed: {e}")


def insert_queue_metrics(department: str, patients_waiting: int,
                          current_load: int, capacity: int,
                          load_percentage: float, congestion_level: str):
    """Insert queue metrics snapshot into BigQuery."""
    client = _get_client()
    if not client:
        return

    if not ensure_dataset():
        return

    try:
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.queue_metrics"
        row = {
            "department": department,
            "patients_waiting": patients_waiting,
            "current_load": current_load,
            "capacity": capacity,
            "load_percentage": load_percentage,
            "congestion_level": congestion_level,
            "timestamp": datetime.utcnow().isoformat(),
        }
        client.insert_rows_json(table_ref, [row])
    except Exception as e:
        logger.warning(f"BigQuery queue metrics insert failed: {e}")


def query_analytics(query: str) -> list:
    """Run a SQL query on the BigQuery analytics dataset.

    Args:
        query: SQL query string.

    Returns:
        List of result rows as dictionaries.
    """
    client = _get_client()
    if not client:
        return []

    try:
        query_job = client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]
    except Exception as e:
        logger.warning(f"BigQuery query failed: {e}")
        return []
