from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="retailsense_pipeline",
    start_date=datetime(2026, 7, 17),
    schedule="@daily",
    catchup=False,
    tags=["retailsense"],
) as dag:

    bronze_task = BashOperator(
        task_id="populate_bronze_layer",
        bash_command="cd /Users/bhavishyachallagolla/Desktop/RetailSense && python ingestion.py",
    )

    silver_task = BashOperator(
        task_id="populate_silver_layer",
        bash_command="cd /Users/bhavishyachallagolla/Desktop/RetailSense && python enrichment.py",
    )

    gold_task = BashOperator(
        task_id="populate_gold_layer",
        bash_command="cd /Users/bhavishyachallagolla/Desktop/RetailSense && python evaluation.py",
    )

    bronze_task >> silver_task >> gold_task
