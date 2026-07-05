import os
from dotenv import load_dotenv
from core.logger import get_logger


# Load .env file
load_dotenv()

# Set JAVA_HOME dynamically if not already in system environment
if not os.environ.get("JAVA_HOME"):
    java_home_val = os.getenv("JAVA_HOME")
    if java_home_val:
        os.environ["JAVA_HOME"] = java_home_val
    else:
        # Fallback to the detected local JDK path
        detected_jdk = r"C:\Program Files\Java\jdk-26.0.1"
        if os.path.exists(detected_jdk):
            os.environ["JAVA_HOME"] = detected_jdk

logger = get_logger("Config")

class Config:
    # Define the Project Root based on this file's location
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Mock Mode configuration
    MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes")

    # Snowflake Configuration
    SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
    SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
    SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
    SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
    SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
    SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")
    SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE")
    SNOWFLAKE_PRIVATE_KEY_PATH = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    SNOWFLAKE_PRIVATE_KEY_PASSPHRASE = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    SNOWFLAKE_AUTHENTICATOR = os.getenv("SNOWFLAKE_AUTHENTICATOR")

    # Databricks Configuration
    DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
    DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_ACCESS_TOKEN")
    DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG")
    DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA")
    DATABRICKS_TABLE = os.getenv("DATABRICKS_TABLE")

    # Vector Store Configuration
    _index_path_env = os.getenv("FAISS_INDEX_PATH")
    FAISS_INDEX_PATH = _index_path_env if _index_path_env else os.path.join(BASE_DIR, "data", "lineage_index")

    _index_file_env = os.getenv("FAISS_INDEX_FILE")
    FAISS_INDEX_FILE = _index_file_env if _index_file_env else os.path.join(FAISS_INDEX_PATH, "faiss.index")

    _metadata_file_env = os.getenv("FAISS_METADATA_FILE")
    FAISS_METADATA_FILE = _metadata_file_env if _metadata_file_env else os.path.join(FAISS_INDEX_PATH, "metadata.pkl")

    DATABRICKS_EMBEDDING_MODEL = os.getenv("DATABRICKS_EMBEDDING_MODEL")
    DATABRICKS_LLM_MODEL=os.getenv("DATABRICKS_LLM_MODEL")
    _embedding_dim = os.getenv("DATABRICKS_EMBEDDING_DIMENSION")
    DATABRICKS_EMBEDDING_DIMENSION = int(_embedding_dim) if _embedding_dim else 1024
    DATABRICKS_BASE_URL = os.getenv("DATABRICKS_BASE_URL")

    @classmethod
    def validate(cls):
        if cls.MOCK_MODE:
            logger.info("Mock Mode is enabled. Skipping credentials validation.")
            return
        if not cls.SNOWFLAKE_ACCOUNT or not cls.SNOWFLAKE_USER:
            logger.error("CRITICAL: Missing Snowflake account or user in .env file.")
        if cls.SNOWFLAKE_AUTHENTICATOR != "externalbrowser":
            if not cls.SNOWFLAKE_PASSWORD and not cls.SNOWFLAKE_PRIVATE_KEY_PATH:
                logger.error("CRITICAL: Missing Snowflake password or private key in .env file.")
        if not cls.DATABRICKS_ACCESS_TOKEN:
            logger.error("CRITICAL: DATABRICKS_ACCESS_TOKEN is missing.")

settings = Config()