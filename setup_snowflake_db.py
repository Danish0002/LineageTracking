import os
from dotenv import load_dotenv
import snowflake.connector

# Load environment variables from .env
load_dotenv()

def run_setup():
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE") or "COMPUTE_WH"
    role = os.getenv("SNOWFLAKE_ROLE")

    if not account or not user:
        print("Error: SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER must be set in .env")
        return

    # Handle enclosing quotes in password if any
    if password:
        if (password.startswith('"') and password.endswith('"')) or (password.startswith("'") and password.endswith("'")):
            password = password[1:-1]

    # Connection options to establish initial session
    conn_opts = {
        "account": account,
        "user": user.upper(),
        "warehouse": warehouse,
        "password": password
    }
    if role:
        conn_opts["role"] = role

    print(f"Connecting to Snowflake account {account} as user {user}...")
    conn = snowflake.connector.connect(**conn_opts)
    cursor = conn.cursor()

    target_db = 'lineageDatabase'
    try:
        # 1. Attempt to create database
        print('Attempting to create database lineageDatabase...')
        cursor.execute('CREATE DATABASE IF NOT EXISTS lineageDatabase')
        print('Database lineageDatabase created or already exists.')
    except Exception as e:
        if "privileges" in str(e).lower() or "42501" in str(e):
            print('\n[WARNING] Insufficient privileges to create database lineageDatabase.')
            fallback_db = "AGENTIC_AI_DE_TEMP"
            print(f'Falling back to temp database: {fallback_db}')
            target_db = fallback_db
        else:
            cursor.close()
            conn.close()
            raise e

    try:
        # 2. Create Schemas under target_db (without double quotes for case-insensitivity)
        print(f"Creating schemas lineageSchema and snowflake inside database {target_db}...")
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {target_db}.lineageSchema')
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {target_db}.snowflake')

        # 3. Create Tables (using CREATE OR REPLACE to ensure column name casing updates)
        print(f"Creating table data_set_element_and_data_product_element_lineage inside {target_db}.lineageSchema...")
        cursor.execute(f'''
            CREATE OR REPLACE TABLE {target_db}.lineageSchema.data_set_element_and_data_product_element_lineage (
                data_domain_instance_name VARCHAR,
                data_set_name VARCHAR,
                data_set_element_name VARCHAR,
                source_data_set_name VARCHAR,
                source_data_domain_instance_name VARCHAR,
                source_data_set_element_name VARCHAR
            )
        ''')

        # Note: "customer_id" column is double-quoted to keep it lowercase because the code executes queries with quoted element name: SELECT "customer_id" FROM ...
        # project_id is kept unquoted because the code queries it as: WHERE project_id = ...
        print(f"Creating table customer_metadata inside {target_db}.snowflake...")
        cursor.execute(f'''
            CREATE OR REPLACE TABLE {target_db}.snowflake.customer_metadata (
                "customer_id" VARCHAR,
                project_id VARCHAR
            )
        ''')

        # 4. Ingest sample data into lineage table
        print("Ingesting sample data into data_set_element_and_data_product_element_lineage...")
        cursor.execute(f'TRUNCATE TABLE {target_db}.lineageSchema.data_set_element_and_data_product_element_lineage')
        cursor.execute(f'''
            INSERT INTO {target_db}.lineageSchema.data_set_element_and_data_product_element_lineage (
                data_domain_instance_name,
                data_set_name,
                data_set_element_name,
                source_data_set_name,
                source_data_domain_instance_name,
                source_data_set_element_name
            ) VALUES
            ('adls', 'staging', 'customer_id', 'customer_metadata', 'snowflake', 'customer_id'),
            ('databricks', 'customer_gold', 'customer_id', 'staging', 'adls', 'customer_id')
        ''')

        # 5. Ingest sample data into customer_metadata table
        print("Ingesting sample data into customer_metadata...")
        cursor.execute(f'TRUNCATE TABLE {target_db}.snowflake.customer_metadata')
        cursor.execute(f'''
            INSERT INTO {target_db}.snowflake.customer_metadata (
                "customer_id",
                project_id
            ) VALUES
            ('CUST_001', 'PROJ_001'),
            ('CUST_002', 'PROJ_001'),
            ('CUST_003', 'PROJ_002')
        ''')

        print("Ingestion completed successfully!")

    except Exception as e:
        print(f"An error occurred during Snowflake table setup/ingestion: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

    # 6. Update .env file
    print(f"Updating .env file to set SNOWFLAKE_DATABASE={target_db} and SNOWFLAKE_SCHEMA=lineageSchema...")
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.startswith("SNOWFLAKE_DATABASE="):
                new_lines.append(f'SNOWFLAKE_DATABASE={target_db}\n')
            elif line.startswith("SNOWFLAKE_SCHEMA="):
                new_lines.append('SNOWFLAKE_SCHEMA=lineageSchema\n')
            else:
                new_lines.append(line)

        with open(env_path, "w") as f:
            f.writelines(new_lines)
        print(".env file updated successfully.")
    else:
        print(".env file not found!")

if __name__ == "__main__":
    run_setup()
