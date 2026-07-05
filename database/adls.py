"""
Azure Data Lake Storage (ADLS) connection utilities
"""
from azure.storage.blob import BlobServiceClient, ContainerClient
from core.logger import get_logger
import streamlit as st
import io
import pandas as pd

logger = get_logger("ADLSConnection")


@st.cache_resource(show_spinner=False)
class MockBlob:
    def __init__(self, name):
        self.name = name


class MockBlobData:
    def __init__(self, csv_data):
        self.csv_data = csv_data

    def readall(self):
        return self.csv_data.encode('utf-8')


class MockBlobClient:
    def __init__(self, container):
        self.container = container

    def download_blob(self):
        return MockBlobData(self.container.csv_content)

    def upload_blob(self, data, overwrite=True):
        if hasattr(data, 'read'):
            content_bytes = data.read()
        elif isinstance(data, str):
            content_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            content_bytes = data
        else:
            content_bytes = str(data).encode('utf-8')
        self.container.csv_content = content_bytes.decode('utf-8')
        logger.info("MockBlobClient: uploaded CSV data successfully in-memory")


class MockContainerClient:
    def __init__(self):
        self.csv_content = """domain,dataset,element,sample_value,project_id
snowflake,customer_metadata,customer_id,CUST_001,PROJ_001
snowflake,customer_metadata,customer_id,CUST_002,PROJ_001
snowflake,customer_metadata,customer_id,CUST_003,PROJ_002
adls,staging,customer_id,CUST_001,PROJ_001
adls,staging,customer_id,CUST_002,PROJ_001
adls,staging,customer_id,CUST_003,PROJ_002
databricks,customer_gold,customer_id,CUST_001,PROJ_001
databricks,customer_gold,customer_id,CUST_002,PROJ_001
databricks,customer_gold,customer_id,CUST_003,PROJ_002
"""

    def list_blobs(self, name_starts_with=None, results_per_page=None):
        return [MockBlob("node_samples.csv")]

    def get_blob_client(self, blob_path):
        return MockBlobClient(self)


@st.cache_resource(show_spinner=False)
def get_adls_connection(sas_url):
    """
    Establishes connection to ADLS using SAS URL.

    Args:
        sas_url: SAS URL for container access

    Returns:
        ContainerClient
    """
    from config.settings import settings
    if settings.MOCK_MODE:
        logger.info("Mock Mode is enabled. Falling back to Mock ADLS container client.")
        return MockContainerClient()

    try:
        logger.info("Connecting to ADLS using SAS URL...")

        # Create container client from SAS URL
        container_client = ContainerClient.from_container_url(sas_url)

        # Test connection by listing blobs (limit 1)
        list(container_client.list_blobs(results_per_page=1))

        logger.info("ADLS connection established successfully")
        return container_client

    except Exception as e:
        from config.settings import settings
        if settings.MOCK_MODE:
            logger.warning(f"Failed to connect to real ADLS ({e}). Falling back to Mock ADLS container client.")
            return MockContainerClient()
        logger.error(f"Failed to connect to ADLS: {e}")
        raise


def read_csv_from_adls(container_client, blob_path):
    """
    Reads a CSV file from ADLS and returns as DataFrame.

    Args:
        container_client: Azure ContainerClient
        blob_path: Path to the CSV blob (e.g., "samples/node_samples.csv")

    Returns:
        pandas DataFrame
    """
    try:
        logger.info(f"Reading CSV from ADLS: {blob_path}")

        # Get blob client
        blob_client = container_client.get_blob_client(blob_path)

        # Download blob content
        blob_data = blob_client.download_blob()
        content = blob_data.readall()

        # Read CSV into DataFrame
        df = pd.read_csv(io.BytesIO(content))

        logger.info(f"Successfully read CSV: {blob_path} ({len(df)} rows)")
        return df

    except Exception as e:
        logger.error(f"Error reading CSV from ADLS {blob_path}: {e}")
        raise


def list_blobs_in_container(container_client, prefix=None):
    """
    Lists all blobs in a container (or with a prefix).

    Args:
        container_client: Azure ContainerClient
        prefix: Optional prefix to filter blobs (e.g., "samples/")

    Returns:
        List of blob names
    """
    try:
        logger.info(f"Listing blobs with prefix: {prefix or 'None'}")
        blobs = container_client.list_blobs(name_starts_with=prefix)
        blob_names = [blob.name for blob in blobs]
        logger.info(f"? Found {len(blob_names)} blobs")
        return blob_names

    except Exception as e:
        logger.error(f"Error listing blobs: {e}")
        raise


@st.cache_data(show_spinner=False, ttl=300)  # Cache for 5 minutes
def load_samples_csv_cached(_container_client, csv_path):
    """
    Cached version of CSV loading from ADLS.
    Note: _container_client has underscore prefix to prevent hashing by Streamlit

    Args:
        _container_client: Azure ContainerClient
        csv_path: Path to CSV file

    Returns:
        pandas DataFrame
    """
    return read_csv_from_adls(_container_client, csv_path)


def write_csv_to_adls(container_client, df, blob_path):
    """
    Writes a pandas DataFrame to ADLS as CSV.

    Args:
        container_client: Azure ContainerClient (or MockContainerClient)
        df: pandas DataFrame to upload
        blob_path: Target path of the CSV blob
    """
    try:
        logger.info(f"Writing CSV to ADLS at path: {blob_path}")
        
        # Convert DataFrame to CSV string/bytes
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        # Get blob client
        blob_client = container_client.get_blob_client(blob_path)
        
        # Upload blob
        blob_client.upload_blob(csv_data, overwrite=True)
        
        logger.info(f"Successfully uploaded CSV to ADLS at path: {blob_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing CSV to ADLS {blob_path}: {e}")
        raise