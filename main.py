import streamlit as st
import pandas as pd
import time
import uuid
import json
import os

from database.snowflake import get_snowflake_connection
from services.tracer import trace_lineage_recursive
from core.logger import get_log_contents, clear_logs, get_logger

from utils.graph_rendering import (
    render_interactive_graph,
    get_graph_statistics,
    get_flattened_paths,
)

from database.adls import get_adls_connection, load_samples_csv_cached
from database.databricks import (
    get_databricks_connection,
    check_databricks_connection_liveness,
)
from data.samples import aggregate_samples_from_all_sources
from utils.agents.agent import save_trace_to_history
from utils.agents.chatbot import render_chatbot

logger = get_logger("ConnectionService")

# -----------------------------------------------------------------------------
# Page Config
#
st.set_page_config(page_title="Snowflake Lineage Explorer", layout="wide")

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "lineage_history" not in st.session_state:
    st.session_state.lineage_history = []
if "current_edges" not in st.session_state:
    st.session_state.current_edges = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "has_run_trace" not in st.session_state:
    st.session_state.has_run_trace = False
if "graph_displayed" not in st.session_state:
    st.session_state.graph_displayed = False
if "ui_chat_history" not in st.session_state:
    st.session_state.ui_chat_history = []

# If the app is in a clean state (no history, no edges, no graph),
# ensure we don't show "No lineage found" due to stale session state.
if (
    not st.session_state.get("lineage_history")
    and not st.session_state.get("current_edges")
    and not st.session_state.get("graph_displayed", False)
):
    st.session_state.has_run_trace = False

# DEV/TEST: Set default trace values
if 'domain_input' not in st.session_state:
    st.session_state.domain_input = "snowflake"
if 'dataset_input' not in st.session_state:
    st.session_state.dataset_input = "customer_metadata"
if 'element_input' not in st.session_state:
    st.session_state.element_input = "customer_id"
if 'filter_value_input' not in st.session_state:
    st.session_state.filter_value_input = "CUST_001"

# -----------------------------------------------------------------------------
# Check for exploration query params
# -----------------------------------------------------------------------------
query_params = st.query_params
exploration_triggered = False

if "explore_domain" in query_params and not st.session_state.graph_displayed:
    exploration_triggered = True
    domain_val = query_params.get("explore_domain", "")
    dataset_val = query_params.get("explore_dataset", "")
    element_val = query_params.get("explore_element", "")
    filter_value = query_params.get("explore_filter", "")
    project_id_val = query_params.get("explore_project_id", "")

    st.session_state.domain_input = domain_val
    st.session_state.dataset_input = dataset_val
    st.session_state.element_input = element_val
    st.session_state.filter_value_input = filter_value
    st.session_state.project_id_input = project_id_val
    st.session_state.trigger_trace = True
    st.query_params.clear()

# -----------------------------------------------------------------------------
# Styling
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 2rem;}
div.stButton > button {
    width: 100%;
    background-color: #0078D4; 
    color: white; 
    border-radius: 6px;
    height: 3em;
    font-weight: bold;
}
div.stButton > button:hover {
    background-color: #005a9e;
    color: white;
    border-color: #005a9e;
}
.status-box {
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 20px;
    font-weight: bold;
    font-family: sans-serif;
}
.connected { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.disconnected { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.partial { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
.checking { background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Cached Connections
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_cached_connection():
    with st.spinner("Connecting to Snowflake..."):
        return get_snowflake_connection()


@st.cache_resource(show_spinner=False)
def get_adls_client():
    with st.spinner("Connecting to Azure Data Lake..."):
        sas_url = os.getenv("AZURE_SAS_URL")
        from config.settings import settings
        if not sas_url or "youraccount" in sas_url:
            if settings.MOCK_MODE:
                sas_url = "https://mock.blob.core.windows.net/mock?sas"
            else:
                raise ValueError("AZURE_SAS_URL not found or is placeholder in environment variables")
        return get_adls_connection(sas_url)


@st.cache_resource(show_spinner=False)
def get_databricks_client():
    with st.spinner("Connecting to Databricks..."):
        return get_databricks_connection()


# -----------------------------------------------------------------------------
# Connection Status Display
# -----------------------------------------------------------------------------
status_placeholder = st.empty()
status_placeholder.markdown(
    '<div class="status-box checking"> Status: Checking Connections...</div>',
    unsafe_allow_html=True,
)

connection_status = []
snowflake_success = False
adls_success = False
databricks_success = False
snowflake_error_msg = None

# 1. Snowflake
try:
    conn = get_cached_connection()
    connection_status.append(" Snowflake")
    snowflake_success = True
except Exception as e:
    connection_status.append(" Snowflake")
    snowflake_error_msg = str(e)

# 2. ADLS
try:
    adls_client = get_adls_client()
    csv_path = os.getenv("CSV_FILE_PATH")

    if not csv_path:
        st.session_state.samples_df = None
        connection_status.append(" Azure Data Lake (No CSV path)")
    else:
        try:
            samples_df = load_samples_csv_cached(adls_client, csv_path)
            st.session_state.samples_df = samples_df
            connection_status.append(f" Azure Data Lake")
            adls_success = True
        except Exception as csv_error:
            st.session_state.samples_df = None
            connection_status.append(" Azure Data Lake (Error)")
except Exception as e:
    connection_status.append(" Azure Data Lake")
    st.session_state.samples_df = None

# 3. Databricks
databricks_conn = None
try:
    databricks_conn = get_databricks_client()
    connection_status.append(" Databricks")
    databricks_success = True
    st.session_state.databricks_conn = databricks_conn
except Exception as e:
    connection_status.append(" Databricks")
    st.session_state.databricks_conn = None

# Update Status Box
success_count = sum([snowflake_success, adls_success, databricks_success])
box_class = (
    "connected"
    if success_count == 3
    else "partial"
    if success_count >= 1
    else "disconnected"
)
status_text = " | ".join(connection_status)
status_placeholder.markdown(
    f'<div class="status-box {box_class}">Status: {status_text}</div>',
    unsafe_allow_html=True,
)

if not snowflake_success:
    st.error(f" Snowflake connection failed: {snowflake_error_msg}")
    st.stop()


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def deduplicate_lineages(edges):
    """Remove subset lineages and recalculate levels."""
    if not edges:
        return edges

    from collections import defaultdict

    # Build path signatures
    paths = defaultdict(list)
    for edge in edges:
        path_key = f"{edge['source']}->{edge['target']}"
        paths[path_key].append(edge)

    # Keep unique paths
    unique_edges = []
    seen_paths = set()

    for edge in edges:
        path_sig = f"{edge['source']}->{edge['target']}->{edge['level']}"
        if path_sig not in seen_paths:
            seen_paths.add(path_sig)
            unique_edges.append(edge)

    return unique_edges


def trace_lineage(
    domain, dataset, element, max_depth, filter_value=None, project_id=None
):
    """Execute lineage trace"""
    try:
        cursor = conn.cursor()
    except Exception:
        st.cache_resource.clear()
        conn_new = get_snowflake_connection()
        cursor = conn_new.cursor()

    edges = []
    start = time.time()

    node_data_list = trace_lineage_recursive(
        cursor,
        domain.strip(),
        dataset.strip() if dataset and dataset.strip() else None,
        element.strip(),
        0,
        max_depth,
        edges,
        filter_value,
        project_id,
    )

    elapsed = round(time.time() - start, 2)
    st.session_state.current_edges = edges

    # Ensure Session ID exists
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    st.session_state.last_trace_domain = domain
    st.session_state.last_trace_dataset = dataset if dataset else ""
    st.session_state.last_trace_element = element

    history_item = {
        "domain": domain,
        "dataset": dataset if dataset else "",
        "element": element,
        "filter": filter_value if filter_value else "None",
        "timestamp": time.strftime("%H:%M:%S"),
        "edges_count": len(edges),
    }
    st.session_state.lineage_history.append(history_item)

    return edges, elapsed


# -----------------------------------------------------------------------------
# Pipeline Ingestion Control Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header(" Ingest & Sync Record")
    st.markdown(
        "Add a new record to Snowflake. The pipeline will automatically sync it to ADLS and Databricks to enable record-level lineage tracing."
    )
    
    ingest_cust_id = st.text_input("New Customer ID", placeholder="e.g. CUST_004", key="ingest_cust_id_input")
    ingest_proj_id = st.text_input("New Project ID", placeholder="e.g. PROJ_003", key="ingest_proj_id_input")
    
    ingest_btn = st.button("Run Ingestion Pipeline", use_container_width=True)
    
    if ingest_btn:
        if not ingest_cust_id.strip() or not ingest_proj_id.strip():
            st.sidebar.error("⚠️ Customer ID and Project ID are required.")
        else:
            with st.sidebar.status("Executing pipeline...", expanded=True) as p_status:
                try:
                    from services.pipeline import ingest_customer_record
                    res = ingest_customer_record(ingest_cust_id, ingest_proj_id)
                    
                    # Log the results
                    for log in res["logs"]:
                        st.write(f"• {log}")
                    
                    # Check status
                    failures = [k for k, v in res.items() if k in ["snowflake", "adls", "databricks"] and "Fail" in str(v)]
                    if failures:
                        p_status.update(label="Pipeline failed!", state="error")
                        st.sidebar.error(f"Failed in: {', '.join(failures)}")
                    else:
                        p_status.update(label="Ingestion successful!", state="complete")
                        st.sidebar.success(f"Successfully ingested and synced record {ingest_cust_id}!")
                        
                        # Clear sample loader cache to reflect updates in the tracer immediately
                        load_samples_csv_cached.clear()
                        
                        # Set fields to the newly ingested record so user can trace it easily!
                        st.session_state.domain_input = "snowflake"
                        st.session_state.dataset_input = "customer_metadata"
                        st.session_state.element_input = "customer_id"
                        st.session_state.filter_value_input = ingest_cust_id.strip()
                        st.session_state.project_id_input = ingest_proj_id.strip()
                        
                        st.rerun()
                        
                except Exception as ex:
                    p_status.update(label="Pipeline crashed!", state="error")
                    st.sidebar.error(f"Error: {ex}")


# -----------------------------------------------------------------------------
# UI Inputs
# -----------------------------------------------------------------------------
st.title(" Record Level Lineage Explorer")

with st.container():
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.subheader("Trace Configuration")

col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1])
with col1:
    domain = st.text_input(
        "Domain / Database", placeholder="Domain Name", key="domain_input"
    )
with col2:
    dataset = st.text_input("Dataset", placeholder="Table name", key="dataset_input")
with col3:
    element = st.text_input("Element", placeholder="Column Name", key="element_input")
with col4:
    filter_value = st.text_input(
        "Data Filter", placeholder="Filter Value", key="filter_value_input"
    )
with col5:
    project_id = st.text_input(
        "Project ID", placeholder="Project ID", key="project_id_input"
    )
with col6:
    max_depth = st.number_input(
        "Max Depth", min_value=1, max_value=20, value=5, key="depth_input"
    )

st.write("")
run = st.button(" Start Trace", width="stretch", type="primary")

# -----------------------------------------------------------------------------
# Execution
# -----------------------------------------------------------------------------
if st.session_state.get("trigger_trace", False):
    st.session_state.trigger_trace = False
    st.session_state.current_edges = []
    st.session_state.lineage_history = []
    run = True

if run:
    if not domain.strip() or not element.strip():
        st.warning(" Please provide Domain and Element name.")
        st.stop()

    # ? SET FLAG TO PREVENT GRAPH RENDERING
    st.session_state.tracing_in_progress = True
    st.session_state.graph_displayed = False
    st.session_state.current_edges = []
    st.session_state.samples_with_source = {}
    st.session_state.last_saved_trace_id = None
    clear_logs()

    with st.status(" Tracing lineage...", expanded=True) as status:
        st.write(" Initializing recursive trace...")
        edges, elapsed = trace_lineage(
            domain, dataset, element, max_depth, filter_value, project_id
        )

        st.write(" Fetching sample data...")
        try:
            cursor = conn.cursor()
            databricks_cursor = None
            if st.session_state.get("databricks_conn"):
                try:
                    databricks_cursor = st.session_state.databricks_conn.cursor()
                except Exception:
                    pass

            samples_with_source = aggregate_samples_from_all_sources(
                cursor,
                edges,
                st.session_state.samples_df,
                sample_size=5,
                databricks_cursor=databricks_cursor,
                filter_value=filter_value,
                project_id=project_id,
            )

            st.session_state.samples_with_source = samples_with_source

            try:
                cursor.close()
                if databricks_cursor:
                    databricks_cursor.close()
            except:
                pass

        except Exception as e:
            logger.error(f"Error fetching samples: {e}")
            st.session_state.samples_with_source = {}

        status.update(label=" Trace Completed", state="complete", expanded=False)
        st.session_state.graph_displayed = True
        st.session_state.has_run_trace = True
        # ? CLEAR FLAG AFTER TRACE COMPLETES
        st.session_state.tracing_in_progress = False

    # Auto-save trace to vector store
    if st.session_state.get("current_edges"):
        try:
            trace_id = save_trace_to_history(
                edges=st.session_state.current_edges,
                samples=st.session_state.get("samples_with_source", {}),
                filter_value=filter_value if filter_value else None,
                project_id=project_id if project_id else None,
                session_id=st.session_state.session_id,
                user_notes=f"Traced {domain}.{element} [Project: {project_id}]",
            )

            if trace_id is not None:
                st.session_state.last_saved_trace_id = trace_id
                logger.info(f"Auto-saved trace with ID: {trace_id}")

        except Exception as e:
            logger.warning(f"Could not auto-save trace: {e}")

    # Only show save status if trace was just executed
    if run and st.session_state.get("last_saved_trace_id") is not None:
        logger.info(f"Trace saved with ID: {st.session_state.last_saved_trace_id}")
    elif run and "last_saved_trace_id" in st.session_state:
        st.warning("Trace was not saved to history")

render_chatbot()


# -----------------------------------------------------------------------------
# GRAPH DISPLAY
# -----------------------------------------------------------------------------
if st.session_state.current_edges and not st.session_state.get(
    "tracing_in_progress", False
):
    edges = st.session_state.current_edges

    trace_domain = st.session_state.get("last_trace_domain", "")
    trace_dataset = st.session_state.get("last_trace_dataset", "")
    trace_element = st.session_state.get("last_trace_element", "")

    if trace_domain and trace_element:
        if trace_dataset and trace_dataset.strip():
            root = f"{trace_domain}.{trace_dataset}.{trace_element}"
        else:
            root = f"{trace_domain}.{trace_element}"
    else:
        min_level = min(e["level"] for e in edges)
        roots = [e["source"] for e in edges if e["level"] == min_level]
        root = roots[0] if roots else edges[0]["source"]

    st.markdown("---")
    tab1, tab2 = st.tabs(["Graph View", "Tabular View"])

    with tab1:
        deduplicated_edges = deduplicate_lineages(edges)
        render_interactive_graph(
            deduplicated_edges,
            root,
            st.session_state.get("samples_with_source", {}),
        )
        st.session_state.graph_displayed = True

    with tab2:
        stats = get_graph_statistics(edges)
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        with stat_col1:
            st.metric("Total Connections", stats["total_edges"])
        with stat_col2:
            st.metric("Unique Nodes", stats["unique_nodes"])
        with stat_col3:
            st.metric("Max Depth", stats["max_level"])
        with stat_col4:
            st.metric("Total Levels", len(stats["nodes_per_level"]))

        st.markdown("---")

        flattened = get_flattened_paths(edges)
        df_display = pd.DataFrame(flattened)
        df_display["level"] = df_display["level"].astype(str)

        def highlight_separator(row):
            if row["source"] == "---":
                return ["background-color: #f0f0f0; font-weight: bold"] * len(row)
            return [""] * len(row)

        styled_df = df_display.style.apply(highlight_separator, axis=1).hide(
            axis="index"
        )
        st.dataframe(styled_df, width="stretch", height=600)

elif st.session_state.get("has_run_trace", False):
    st.info("No lineage found for the given inputs.")
