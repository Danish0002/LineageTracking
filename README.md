# Record Level Lineage Explorer & Data Pipeline

A Python-based Streamlit dashboard and data pipeline for tracing, matching, and exploring record-level data lineage across **Snowflake**, **Azure Data Lake Storage (ADLS)**, and **Databricks**. 

The application resolves the structural column lineage paths, fetches sample values at each node from all three platforms, checks for value consistency, and includes an AI-driven Chatbot Assistant powered by LangChain and FAISS vector search to analyze lineage history.

---

##  Key Features

* **Recursive Lineage Graph Rendering**: Traces column-level mapping dynamically (e.g., Snowflake ➔ ADLS ➔ Databricks) and visualizes the dependency graph interactively using VisJS.
* **Record-Level Value Consistency Check**: Compares data samples (like specific `Customer ID`s and `Project ID`s) across all stages of the pipeline to verify data integrity.
* **Auto-Sync Ingestion Pipeline**: Contains a CLI script and a Streamlit sidebar form to ingest a new record into Snowflake, append the lineage nodes to ADLS (`node_samples.csv`), and synchronize it to Databricks.
* **Self-Healing Database Cache**: Automatically detects closed database sessions or timeouts for Databricks and Snowflake, refreshes the cached connections, and retries seamlessly.
* **AI Lineage Assistant**: Features an embedded chatbot agent (supervisor pattern) that retrieves relevant context from a FAISS vector store of historical lineage traces to answer complex engineering questions.

---

##  Project Structure

```text
Record-level-lineage/
│
├── database/               # Database connectivity & operations
│   ├── snowflake.py        # Snowflake connection with self-healing caching
│   ├── adls.py             # ADLS container connection and CSV file operations
│   ├── databricks.py       # Databricks SQL connection and tables setup
│   └── vector_store.py     # FAISS vector store database for trace archiving
│
├── services/               # Core business services
│   ├── pipeline.py         # snowflake-ADLS-Databricks ingestion pipeline
│   ├── tracer.py           # Recursive lineage tree tracer
│   └── llm_client.py       # Databricks OpenAI endpoint client
│
├── utils/                  # Helper modules
│   ├── agents/             # LangChain chatbot, supervisor, guardrails, & prompts
│   └── graph_rendering/    # vis.js graph builders, javascript, & HTML renderers
│
├── data/                   # Data samples and index directory
│   ├── lineage_index/      # FAISS vector store binary index and metadata
│   └── node_samples.csv    # Local CSV backups
│
├── main.py                 # Streamlit UI dashboard entry point
├── ingest_record.py        # Command line data ingestion pipeline trigger
├── packages.txt            # Streamlit Cloud system dependencies (Java JRE, Graphviz)
├── requirements.txt        # Python package dependencies
└── .env                    # Environment variables (connection string, tokens)
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have the following installed:
* Python 3.10+
* Java (JDK/JRE 11 or 17) - Required for JDBC drivers. Verify with:
  ```bash
  java -version
  ```

### 2. Install Python Dependencies
Create a virtual environment and install requirements:
```bash
pip install -r requirements.txt
```

### 3. Configure Connection Credentials (`.env`)
Create a `.env` file in the root directory. Paste your credentials using this format:
```ini
MOCK_MODE=false

# SNOWFLAKE
SNOWFLAKE_ACCOUNT=your-snowflake-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PASSWORD="your-password"
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=lineageDatabase
SNOWFLAKE_SCHEMA=lineageSchema

# AZURE STORAGE (ADLS)
AZURE_STORAGE_ACCOUNT_NAME=yourstorageaccount
AZURE_CONTAINER_NAME=lineage
AZURE_SAS_TOKEN="your-sas-token"
AZURE_SAS_URL="your-sas-url"
CSV_FILE_PATH=node_samples.csv

# DATABRICKS
DATABRICKS_BASE_URL=https://your-databricks-instance.cloud.databricks.com/serving-endpoints
DATABRICKS_ACCESS_TOKEN=your-token
DATABRICKS_SERVER_HOSTNAME=your-databricks-instance.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/yourwarehouseid
DATABRICKS_CATALOG=lineagecatalog
DATABRICKS_SCHEMA=lineageschema
DATABRICKS_TABLE=node_samples
```

---

##  Running the Application

### Launch Streamlit App
Run the following command to start the local dashboard:
```bash
streamlit run main.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Ingest Data via CLI
To sync a new record into Snowflake, ADLS, and Databricks directly from the terminal, execute:
```bash
python ingest_record.py --customer-id CUST_999 --project-id PROJ_999
```

---

##  Deployment on Streamlit Cloud

1. Push the contents of the `LineageDemo` folder to a public or private GitHub repository.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/) and click **"New App"**.
3. Select your repository and branch, and point the main file path to `main.py`.
4. Go to **Advanced settings... -> Secrets** and paste your TOML-formatted `.env` credentials.
5. Click **Deploy**. (The system will automatically install Java and Graphviz using `packages.txt`).
