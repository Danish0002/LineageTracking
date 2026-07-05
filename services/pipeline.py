"""
Data Pipeline Service for ingesting new records and updating lineage traces.
"""
import os
import pandas as pd
import io
from config.settings import settings
from core.logger import get_logger
from database.snowflake import get_snowflake_connection
from database.adls import get_adls_connection, read_csv_from_adls, write_csv_to_adls
from database.databricks import get_databricks_connection

logger = get_logger("DataPipelineService")


def ingest_customer_record(customer_id: str, project_id: str):
    """
    Ingests a new customer record into Snowflake, propagates it to ADLS (CSV),
    and synchronizes it to Databricks for lineage consistency.

    Args:
        customer_id: The Customer ID to ingest (e.g. 'CUST_004')
        project_id: The Project ID associated with the customer (e.g. 'PROJ_003')

    Returns:
        dict: Ingestion status and summary of operations
    """
    customer_id = customer_id.strip()
    project_id = project_id.strip()

    if not customer_id or not project_id:
        raise ValueError("Customer ID and Project ID cannot be empty.")

    logger.info(f"Starting ingestion pipeline for Customer: {customer_id}, Project: {project_id}")
    status = {
        "snowflake": "Pending",
        "adls": "Pending",
        "databricks": "Pending",
        "logs": []
    }

    # Define the rows to sync across all levels of the pipeline
    new_rows = [
        {"domain": "snowflake", "dataset": "customer_metadata", "element": "customer_id", "sample_value": customer_id, "project_id": project_id},
        {"domain": "adls", "dataset": "staging", "element": "customer_id", "sample_value": customer_id, "project_id": project_id},
        {"domain": "databricks", "dataset": "customer_gold", "element": "customer_id", "sample_value": customer_id, "project_id": project_id}
    ]

    # -------------------------------------------------------------------------
    # 1. SNOWFLAKE INGESTION
    # -------------------------------------------------------------------------
    try:
        status["logs"].append("Connecting to Snowflake...")
        snowflake_conn = get_snowflake_connection()
        cursor = snowflake_conn.cursor()

        db = settings.SNOWFLAKE_DATABASE or "lineageDatabase"
        
        status["logs"].append(f"Ensuring Snowflake schema 'snowflake' and table 'customer_metadata' exist in database '{db}'...")
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {db}.snowflake")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {db}.snowflake.customer_metadata (
                "customer_id" VARCHAR,
                project_id VARCHAR
            )
        """)

        # Check if record already exists in Snowflake
        check_query = f"SELECT COUNT(*) FROM {db}.snowflake.customer_metadata WHERE \"customer_id\" = '{customer_id}' AND project_id = '{project_id}'"
        cursor.execute(check_query)
        count = cursor.fetchone()[0]

        if count == 0:
            insert_query = f"INSERT INTO {db}.snowflake.customer_metadata (\"customer_id\", project_id) VALUES ('{customer_id}', '{project_id}')"
            status["logs"].append("Inserting record into Snowflake...")
            cursor.execute(insert_query)
            try:
                snowflake_conn.commit()
            except:
                pass
            status["logs"].append(f"Successfully inserted '{customer_id}' into Snowflake table 'customer_metadata'.")
        else:
            status["logs"].append(f"Record '{customer_id}' already exists in Snowflake, skipping insert.")

        cursor.close()
        status["snowflake"] = "Success"
    except Exception as e:
        err_msg = f"Snowflake ingestion failed: {e}"
        logger.error(err_msg)
        status["logs"].append(err_msg)
        status["snowflake"] = f"Failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 2. ADLS UPLOAD
    # -------------------------------------------------------------------------
    try:
        sas_url = os.getenv("AZURE_SAS_URL")
        if not sas_url or "youraccount" in sas_url:
            if settings.MOCK_MODE:
                sas_url = "https://mock.blob.core.windows.net/mock?sas"
            else:
                raise ValueError("AZURE_SAS_URL is missing or placeholder.")

        status["logs"].append("Connecting to Azure Data Lake Storage (ADLS)...")
        adls_client = get_adls_connection(sas_url)
        csv_path = os.getenv("CSV_FILE_PATH") or "node_samples.csv"

        status["logs"].append(f"Reading current samples CSV '{csv_path}' from ADLS...")
        try:
            df = read_csv_from_adls(adls_client, csv_path)
            # Standardize string fields
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.strip()
        except Exception as csv_err:
            status["logs"].append(f"Warning: Could not read CSV from ADLS ({csv_err}). Starting new CSV.")
            df = pd.DataFrame(columns=["domain", "dataset", "element", "sample_value", "project_id"])

        appended_any = False
        for row in new_rows:
            # Check if this node sample already exists in the CSV
            exists = False
            if len(df) > 0:
                exists = ((df['domain'] == row['domain']) & 
                          (df['dataset'] == row['dataset']) & 
                          (df['element'] == row['element']) & 
                          (df['sample_value'] == row['sample_value']) & 
                          (df['project_id'] == row['project_id'])).any()
            
            if not exists:
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                appended_any = True
                status["logs"].append(f"Appending row to CSV: {row['domain']}.{row['dataset']}.{row['element']} = {row['sample_value']}")

        if appended_any:
            status["logs"].append("Uploading updated CSV back to ADLS...")
            write_csv_to_adls(adls_client, df, csv_path)
            status["logs"].append("ADLS CSV uploaded successfully.")
        else:
            status["logs"].append("All records already present in ADLS CSV, upload skipped.")

        status["adls"] = "Success"
    except Exception as e:
        err_msg = f"ADLS upload failed: {e}"
        logger.error(err_msg)
        status["logs"].append(err_msg)
        status["adls"] = f"Failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 3. DATABRICKS SYNCHRONIZATION
    # -------------------------------------------------------------------------
    try:
        status["logs"].append("Connecting to Databricks SQL Warehouse...")
        databricks_conn = get_databricks_connection()
        cursor = databricks_conn.cursor()

        catalog = settings.DATABRICKS_CATALOG or "lineagecatalog"
        schema = settings.DATABRICKS_SCHEMA or "lineageschema"
        table = settings.DATABRICKS_TABLE or "node_samples"

        status["logs"].append(f"Ensuring Databricks catalog '{catalog}', schema '{schema}' and table '{table}' exist...")
        
        # 3.1 Try to create Catalog (may require high privileges, fail gracefully)
        try:
            cursor.execute(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")
        except Exception as cat_err:
            status["logs"].append(f"Note: Catalog creation skipped/unauthorized ({cat_err})")

        # 3.2 Try to use Catalog
        try:
            cursor.execute(f"USE CATALOG `{catalog}`")
        except Exception as cat_err:
            status["logs"].append(f"Note: USE CATALOG skipped/unauthorized ({cat_err})")

        # 3.3 Create Schema
        try:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS `{schema}`")
        except Exception as sch_err:
            status["logs"].append(f"Note: Schema creation skipped/unauthorized ({sch_err})")

        # 3.4 Create Table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{catalog}`.`{schema}`.`{table}` (
                domain STRING,
                dataset STRING,
                element STRING,
                sample_value STRING,
                project_id STRING
            )
        """)

        # 3.5 Insert rows
        for row in new_rows:
            # Check if this record already exists in Databricks
            check_query = f"""
                SELECT COUNT(*) FROM `{catalog}`.`{schema}`.`{table}`
                WHERE `domain` = '{row['domain']}' 
                AND `dataset` = '{row['dataset']}' 
                AND `element` = '{row['element']}' 
                AND `sample_value` = '{row['sample_value']}' 
                AND `project_id` = '{row['project_id']}'
            """
            cursor.execute(check_query)
            res = cursor.fetchone()
            count = res[0] if res else 0

            if count == 0:
                insert_query = f"""
                    INSERT INTO `{catalog}`.`{schema}`.`{table}` (domain, dataset, element, sample_value, project_id)
                    VALUES ('{row['domain']}', '{row['dataset']}', '{row['element']}', '{row['sample_value']}', '{row['project_id']}')
                """
                status["logs"].append(f"Synchronizing record to Databricks for: {row['domain']}.{row['dataset']}.{row['element']}...")
                cursor.execute(insert_query)
            else:
                status["logs"].append(f"Record for {row['domain']}.{row['dataset']} already exists in Databricks, skipping insert.")

        cursor.close()
        status["databricks"] = "Success"
        status["logs"].append("Databricks synchronization completed successfully.")
    except Exception as e:
        err_msg = f"Databricks synchronization failed: {e}"
        logger.error(err_msg)
        status["logs"].append(err_msg)
        status["databricks"] = f"Failed: {str(e)}"

    logger.info(f"Ingestion pipeline completed: Snowflake={status['snowflake']}, ADLS={status['adls']}, Databricks={status['databricks']}")
    return status
