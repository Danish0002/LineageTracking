import snowflake.connector
from config.settings import settings
from core.logger import get_logger
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

logger = get_logger("SnowflakeConnectionService")


def check_snowflake_connection_liveness(conn):
    """
    Executes a lightweight query to ensure the Snowflake connection is active.
    """
    try:
        logger.info("Performing Snowflake connection liveness check (SELECT 1)...")
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()

        if result:
            logger.info("Snowflake liveness check passed.")
            return True
    except Exception as e:
        logger.error(f"Snowflake liveness check failed: {e}")
        return False
    return False


MOCK_CUSTOMER_RECORDS = [
    ("CUST_001", "PROJ_001"),
    ("CUST_002", "PROJ_001"),
    ("CUST_003", "PROJ_002"),
]


class MockCursor:
    def __init__(self):
        self.results = []
        self.index = 0

    def execute(self, query):
        query_lower = query.lower()
        self.results = []
        self.index = 0
        
        if "data_set_element_and_data_product_element_lineage" in query_lower:
            if "select" in query_lower:
                import re
                domain_match = re.search(r"source_data_domain_instance_name\s*=\s*'([^']+)'", query)
                element_match = re.search(r"source_data_set_element_name\s*=\s*'([^']+)'", query)
                
                domain_val = domain_match.group(1) if domain_match else None
                element_val = element_match.group(1) if element_match else None
                
                if domain_val == "snowflake":
                    if element_val == "customer_id":
                        self.results = [("adls", "staging", "customer_id", "customer_metadata")]
                elif domain_val == "adls":
                    if element_val == "customer_id":
                        self.results = [("databricks", "customer_gold", "customer_id", "staging")]
                elif domain_val == "databricks":
                    self.results = []
            else:
                # DDL or Insert for lineage table
                pass
                
        elif "customer_metadata" in query_lower:
            if "insert into" in query_lower:
                import re
                # Extract values from insert query
                match = re.search(r"\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", query)
                if match:
                    cust_id, proj_id = match.groups()
                    if (cust_id, proj_id) not in MOCK_CUSTOMER_RECORDS:
                        MOCK_CUSTOMER_RECORDS.append((cust_id, proj_id))
                    logger.info(f"Mock Snowflake Ingested customer record: {(cust_id, proj_id)}. Total: {len(MOCK_CUSTOMER_RECORDS)}")
            elif "select" in query_lower:
                import re
                cust_filter_match = re.search(r"[\"']?customer_id[\"']?\s*=\s*['\"]([^'\"]+)['\"]", query)
                proj_filter_match = re.search(r"project_id\s*=\s*['\"]([^'\"]+)['\"]", query)
                
                cust_filter = cust_filter_match.group(1) if cust_filter_match else None
                proj_filter = proj_filter_match.group(1) if proj_filter_match else None
                
                matched = []
                for cust_id, proj_id in MOCK_CUSTOMER_RECORDS:
                    if cust_filter and cust_id != cust_filter:
                        continue
                    if proj_filter and proj_id != proj_filter:
                        continue
                    matched.append(cust_id)
                    
                if "count(*)" in query_lower:
                    self.results = [(len(matched),)]
                else:
                    # Apply limit if any
                    limit_match = re.search(r"limit\s+(\d+)", query_lower)
                    limit = int(limit_match.group(1)) if limit_match else len(matched)
                    self.results = [(c,) for c in matched[:limit]]
            else:
                # Truncate or other query
                pass
        elif "select 1" in query_lower:
            self.results = [(1,)]
        else:
            self.results = []

    def fetchall(self):
        return self.results

    def fetchone(self):
        if self.index < len(self.results):
            val = self.results[self.index]
            self.index += 1
            return val
        return None

    def close(self):
        pass


class MockConnection:
    def cursor(self):
        return MockCursor()
    def close(self):
        pass


def get_snowflake_connection():
    """
    Establishes and returns a validated connection to Snowflake.
    Falls back to a MockConnection if MOCK_MODE is enabled or configuration is missing.
    """
    if settings.MOCK_MODE:
        logger.info("Mock Mode is enabled. Falling back to Mock Snowflake Connection.")
        return MockConnection()
        
    try:
        account = settings.SNOWFLAKE_ACCOUNT
        if account and account.endswith(".snowflakecomputing.com"):
            account = account.replace(".snowflakecomputing.com", "")
            
        logger.info(f"Connecting to Snowflake account: {account}")
        
        # Uppercase the username as Snowflake key-pair authentication is case-sensitive
        user_upper = settings.SNOWFLAKE_USER.upper() if settings.SNOWFLAKE_USER else settings.SNOWFLAKE_USER
        
        conn_opts = {
            "account": account,
            "user": user_upper,
            "warehouse": settings.SNOWFLAKE_WAREHOUSE or "COMPUTE_WH",
            "database": settings.SNOWFLAKE_DATABASE,
            "schema": settings.SNOWFLAKE_SCHEMA
        }
        
        if settings.SNOWFLAKE_AUTHENTICATOR == "externalbrowser":
            logger.info("Using Snowflake browser authentication (MFA/SSO)")
            conn_opts["authenticator"] = "externalbrowser"
        elif settings.SNOWFLAKE_PRIVATE_KEY_PATH:
            import os
            import base64
            key_path = settings.SNOWFLAKE_PRIVATE_KEY_PATH
            if not os.path.isabs(key_path):
                from config.settings import Config
                key_path = os.path.join(Config.BASE_DIR, key_path)
                
            logger.info(f"Loading Snowflake private key from: {key_path}")
            with open(key_path, "rb") as key_file:
                raw_content = key_file.read()
                
            passphrase = settings.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
            password_bytes = passphrase.encode() if passphrase else None
            
            cleaned_content = raw_content.strip()
            # If the file lacks standard PEM headers, attempt decoding base64 DER
            if b"BEGIN" not in cleaned_content:
                logger.info("No PEM headers found. Attempting base64 decoding to DER...")
                try:
                    b64_data = b"".join(cleaned_content.split())
                    der_data = base64.b64decode(b64_data)
                    private_key = serialization.load_der_private_key(
                        der_data,
                        password=password_bytes,
                        backend=default_backend()
                    )
                    logger.info("Successfully loaded private key via base64 decode -> DER.")
                except Exception as der_err:
                    logger.warning(f"Failed to load as DER ({der_err}). Falling back to PEM wrapping...")
                    pem_data = b"-----BEGIN PRIVATE KEY-----\n" + cleaned_content + b"\n-----END PRIVATE KEY-----"
                    private_key = serialization.load_pem_private_key(
                        pem_data,
                        password=password_bytes,
                        backend=default_backend()
                    )
            else:
                private_key = serialization.load_pem_private_key(
                    raw_content,
                    password=password_bytes,
                    backend=default_backend()
                )
                
            private_key_der = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            conn_opts["private_key"] = private_key_der
        else:
            conn_opts["password"] = settings.SNOWFLAKE_PASSWORD

        if settings.SNOWFLAKE_ROLE:
            conn_opts["role"] = settings.SNOWFLAKE_ROLE
            
        conn = snowflake.connector.connect(**conn_opts)

        if not check_snowflake_connection_liveness(conn):
            conn.close()
            raise ConnectionError("Snowflake connection succeeded, but liveness check failed.")

        logger.info("Successfully connected to Snowflake.")
        return conn

    except Exception as e:
        if not settings.MOCK_MODE:
            logger.error(f"Failed to connect to real Snowflake: {e}")
            raise e
        logger.warning(f"Failed to connect to real Snowflake ({e}). Falling back to Mock Snowflake Connection.")
        return MockConnection()
