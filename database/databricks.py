"""
Databricks connection utilities
"""
from databricks import sql
from config.settings import settings
from core.logger import get_logger
import streamlit as st

logger = get_logger("DatabricksConnection")


MOCK_DATABRICKS_RECORDS = [
    ("snowflake", "customer_metadata", "customer_id", "CUST_001", "PROJ_001"),
    ("snowflake", "customer_metadata", "customer_id", "CUST_002", "PROJ_001"),
    ("snowflake", "customer_metadata", "customer_id", "CUST_003", "PROJ_002"),
    ("adls", "staging", "customer_id", "CUST_001", "PROJ_001"),
    ("adls", "staging", "customer_id", "CUST_002", "PROJ_001"),
    ("adls", "staging", "customer_id", "CUST_003", "PROJ_002"),
    ("databricks", "customer_gold", "customer_id", "CUST_001", "PROJ_001"),
    ("databricks", "customer_gold", "customer_id", "CUST_002", "PROJ_001"),
    ("databricks", "customer_gold", "customer_id", "CUST_003", "PROJ_002"),
]


class MockCursor:
    def __init__(self):
        self.results = []
        self.index = 0

    def execute(self, query):
        query_lower = query.lower()
        self.results = []
        self.index = 0
        
        if "select 1" in query_lower:
            self.results = [(1,)]
        elif "insert into" in query_lower:
            import re
            # Extract tuples like ('domain', 'dataset', 'element', 'sample_val', 'proj_id')
            value_groups = re.findall(
                r"\(\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)",
                query
            )
            for val in value_groups:
                if val not in MOCK_DATABRICKS_RECORDS:
                    MOCK_DATABRICKS_RECORDS.append(val)
            logger.info(f"Mock Databricks Ingested records: {value_groups}. Total: {len(MOCK_DATABRICKS_RECORDS)}")
        elif "select" in query_lower:
            import re
            domain_match = re.search(r"[`\"]?domain[`\"]?\s*=\s*['\"]([^'\"]+)['\"]", query)
            dataset_match = re.search(r"[`\"]?dataset[`\"]?\s*=\s*['\"]([^'\"]+)['\"]", query)
            element_match = re.search(r"[`\"]?element[`\"]?\s*=\s*['\"]([^'\"]+)['\"]", query)
            sample_val_match = re.search(r"[`\"]?sample_value[`\"]?\s*=\s*['\"]([^'\"]+)['\"]", query)
            proj_id_match = re.search(r"[`\"]?project_id[`\"]?\s*=\s*['\"]([^'\"]+)['\"]", query)

            domain_val = domain_match.group(1) if domain_match else None
            dataset_val = dataset_match.group(1) if dataset_match else None
            element_val = element_match.group(1) if element_match else None
            sample_val = sample_val_match.group(1) if sample_val_match else None
            proj_id_val = proj_id_match.group(1) if proj_id_match else None

            matched_records = []
            for r in MOCK_DATABRICKS_RECORDS:
                if domain_val and r[0] != domain_val:
                    continue
                if dataset_val and r[1] != dataset_val:
                    continue
                if element_val and r[2] != element_val:
                    continue
                if sample_val and r[3] != sample_val:
                    continue
                if proj_id_val and r[4] != proj_id_val:
                    continue
                matched_records.append(r[3])

            matched_records = list(dict.fromkeys(matched_records))

            if "count" in query_lower:
                self.results = [(len(matched_records),)]
            else:
                self.results = [(v,) for v in matched_records]

    def fetchone(self):
        if self.index < len(self.results):
            val = self.results[self.index]
            self.index += 1
            return val
        return None

    def fetchall(self):
        return self.results

    def close(self):
        pass


class MockConnection:
    def cursor(self):
        return MockCursor()
    def close(self):
        pass


@st.cache_resource(show_spinner=False)
def get_databricks_connection():
    """
    Establishes connection to Databricks SQL warehouse.

    Returns:
        Connection object
    """
    if settings.MOCK_MODE:
        logger.info("Mock Mode is enabled. Falling back to Mock Databricks Connection.")
        return MockConnection()

    try:
        if not settings.DATABRICKS_SERVER_HOSTNAME or not settings.DATABRICKS_HTTP_PATH or not settings.DATABRICKS_ACCESS_TOKEN:
            raise ValueError("Databricks configuration is incomplete in .env file.")

        logger.info("Connecting to Databricks...")
        logger.info(f"Server: {settings.DATABRICKS_SERVER_HOSTNAME}")
        logger.info(f"HTTP Path: {settings.DATABRICKS_HTTP_PATH}")

        # Create connection using Databricks SQL Connector
        conn = sql.connect(
            server_hostname=settings.DATABRICKS_SERVER_HOSTNAME,
            http_path=settings.DATABRICKS_HTTP_PATH,
            access_token=settings.DATABRICKS_ACCESS_TOKEN,
        )

        # Test connection with a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()

        if result:
            logger.info("Databricks connection established successfully")
            return conn
        else:
            raise ConnectionError("Connection test query returned no result")

    except Exception as e:
        if settings.MOCK_MODE:
            logger.warning(f"Failed to connect to real Databricks ({e}). Falling back to Mock Databricks Connection.")
            return MockConnection()
        logger.error(f"Failed to connect to Databricks: {e}")
        raise


def check_databricks_connection_liveness(conn):
    """
    Executes a lightweight query to ensure the connection is truly active
    and the server is responsive.

    Args:
        conn: Databricks connection object

    Returns:
        bool: True if connection is alive, False otherwise
    """
    try:
        logger.info("Performing Databricks connection liveness check (SELECT 1)...")
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()

        if result:
            logger.info("Databricks liveness check passed.")
            return True
    except Exception as e:
        logger.error(f"Databricks liveness check failed: {e}")
        return False
    return False


def execute_databricks_query(conn, query):
    """
    Execute a SQL query on Databricks and return results.

    Args:
        conn: Databricks connection object
        query: SQL query string

    Returns:
        List of tuples containing query results
    """
    try:
        logger.info(f"Executing query on Databricks: {query[:100]}...")
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        logger.info(f"Query executed successfully. Returned {len(results)} rows")
        return results
    except Exception as e:
        logger.error(f"Error executing query on Databricks: {e}")
        raise
