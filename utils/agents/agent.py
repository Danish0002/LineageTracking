"""
Main agent interface using supervisor pattern
"""

import logging
from typing import List, Dict

from database.vector_store import LineageVectorStore
from utils.agents.supervisor import route_question, execute_agent
from utils.agents.prompts import REFUSAL_MESSAGE

logger = logging.getLogger("AgentService")

# Initialize Vector Store
try:
    vector_store = LineageVectorStore()
    logger.info("Vector store initialized")
except Exception as e:
    logger.error(f"Failed to initialize vector store: {e}")
    vector_store = None


def build_lineage_paths(edges: List[Dict]) -> List[List[str]]:
    """Build complete lineage paths from edges"""
    if not edges:
        return []

    adj_map = {}
    all_targets = set()

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        all_targets.add(tgt)
        if src not in adj_map:
            adj_map[src] = []
        adj_map[src].append(tgt)

    all_sources = set(adj_map.keys())
    roots = all_sources - all_targets

    if not roots:
        min_level = min(e["level"] for e in edges)
        roots = set(e["source"] for e in edges if e["level"] == min_level)

    paths = []

    def dfs(node, current_path):
        if node in adj_map:
            for child in adj_map[node]:
                dfs(child, current_path + [child])
        else:
            paths.append(current_path)

    for root in roots:
        dfs(root, [root])

    return paths if paths else [[e["source"], e["target"]] for e in edges[:1]]


def format_current_trace_context(
    edges: List[Dict], samples: Dict, filter_value: str = None, trace_id: int = None
) -> str:
    """Format context for current trace agent"""
    if not edges:
        return "No active lineage trace."

    paths = build_lineage_paths(edges)

    text = "=== CURRENT TRACE METADATA ===\n"
    text += f"Trace ID: {trace_id if trace_id is not None else 'Unknown'}\n"
    text += f"Filter Applied: {filter_value or 'None'}\n"
    text += f"Total Nodes: {len(samples)} | Total Edges: {len(edges)}\n"
    text += f"Max Depth: {max(e['level'] for e in edges)}\n\n"

    text += "=== LINEAGE PATHS ===\n"
    for idx, path in enumerate(paths, 1):
        text += f"Path {idx}: {' -> '.join(path)}\n"
    text += "\n"

    text += "=== NODE DATA ANALYSIS ===\n"
    for node, data in samples.items():
        text += f"\n--- Node: {node} ---\n"

        sources = [k for k in ["adls", "snowflake", "databricks"] if data.get(k)]
        text += f"Sources: {', '.join(sources) if sources else 'NONE'}\n"

        adls_count = data.get("adls_count", 0)
        snowflake_count = data.get("snowflake_count", 0)
        databricks_count = data.get("databricks_count", 0)

        text += f"Total Rows - ADLS: {adls_count} | Snowflake: {snowflake_count} | Databricks: {databricks_count}\n"

        if data.get("adls"):
            text += f"ADLS Samples: {data['adls'][:5]}\n"
        if data.get("snowflake"):
            text += f"Snowflake Samples: {data['snowflake'][:5]}\n"
        if data.get("databricks"):
            text += f"Databricks Samples: {data['databricks'][:5]}\n"

        # Comparisons
        if data.get("adls") and data.get("snowflake"):
            match = "MATCH" if set(data["adls"]) == set(data["snowflake"]) else "MISMATCH"
            text += f"Snowflake vs ADLS: {match}\n"

        if filter_value:
            found_in = [
                s
                for s in ["adls", "snowflake", "databricks"]
                if filter_value in data.get(s, [])
            ]
            text += f"Filter '{filter_value}' found in: {found_in if found_in else 'NOWHERE'}\n"

    return text


def format_historical_context(question: str) -> str:
    """Format context for historical search agent"""
    if not vector_store:
        return "Historical search unavailable (vector store not initialized)"

    # Check if user wants to COMPARE two specific traces
    import re

    compare_match = re.search(
        r"trace[s]?\s*(\d+)\s*(?:and|vs|with|versus|,)\s*(?:trace\s*)?(\d+)",
        question.lower(),
    )

    if compare_match:
        # User wants COMPARISON with current trace
        historical_trace_id = int(compare_match.group(1))

        logger.info(
            f"Detected comparison request: Historical Trace {historical_trace_id} vs Current Trace"
        )

        historical_trace = vector_store.get_trace_by_id(historical_trace_id)

        if not historical_trace:
            return f"Error: Trace {historical_trace_id} not found."

        # Build comparison context - historical trace data + placeholder for current
        text = f"=== COMPARISON CONTEXT ===\n\n"

        # Historical trace metadata
        text += f"HISTORICAL TRACE (ID: {historical_trace_id}):\n"
        text += f"Date: {historical_trace['timestamp'][:19]}\n"
        text += f"Root: {historical_trace['root_node']}\n"
        text += f"Filter: {historical_trace.get('filter_value', 'None')}\n"
        text += f"Total Edges: {historical_trace['total_edges']}\n"
        text += f"Max Depth: {historical_trace['max_level']}\n\n"

        # Historical trace sample data
        text += f"HISTORICAL TRACE (ID: {historical_trace_id}) NODE SAMPLES:\n"
        historical_samples = historical_trace.get("samples", {})

        for node, data in historical_samples.items():
            text += f"\nNode: {node}\n"
            if data.get("adls"):
                text += f"  ADLS: {data['adls'][:10]} (Count: {data.get('adls_count', 0)})\n"
            if data.get("snowflake"):
                text += f"  Snowflake: {data['snowflake'][:10]} (Count: {data.get('snowflake_count', 0)})\n"
            if data.get("databricks"):
                text += f"  Databricks: {data['databricks'][:10]} (Count: {data.get('databricks_count', 0)})\n"

        text += "\n\nNOTE: Current trace data will be provided separately in the execution context.\n"

        return text

    # Check if user is asking about a specific trace ID
    import re

    trace_id_match = re.search(r"trace\s*(\d+)", question.lower())

    if trace_id_match:
        trace_id = int(trace_id_match.group(1))
        logger.info(f"Detected specific trace query: Trace {trace_id}")

        trace = vector_store.get_trace_by_id(trace_id)

        if not trace:
            return f"Error: Trace {trace_id} not found."

        text = f"=== TRACE {trace_id} DETAILS ===\n\n"
        text += f"Date: {trace['timestamp'][:19]}\n"
        text += f"Root Node: {trace['root_node']}\n"
        text += f"Filter Value: {trace.get('filter_value', 'None')}\n"
        text += f"Total Edges: {trace['total_edges']}\n"
        text += f"Max Depth: {trace['max_level']}\n\n"

        text += "=== NODE SAMPLE DATA ===\n\n"
        samples = trace.get("samples", {})

        for node, data in samples.items():
            text += f"Node: {node}\n"
            if data.get("adls"):
                text += f"  ADLS Samples: {data['adls'][:10]} (Total: {data.get('adls_count', 0)})\n"
            if data.get("snowflake"):
                text += f"  Snowflake Samples: {data['snowflake'][:10]} (Total: {data.get('snowflake_count', 0)})\n"
            if data.get("databricks"):
                text += f"  Databricks Samples: {data['databricks'][:10]} (Total: {data.get('databricks_count', 0)})\n"
            text += "\n"

        return text

    # Not a comparison - check if user wants full list
    list_keywords = ["list", "show all", "all traces", "history", "what did i"]
    wants_list = any(kw in question.lower() for kw in list_keywords)

    # Not a comparison - check if user wants full list
    list_keywords = ["list", "show all", "all traces", "history", "what did i"]
    wants_list = any(kw in question.lower() for kw in list_keywords)

    if wants_list:
        summaries = vector_store.get_all_traces_summary()
        if summaries:
            text = "=== ALL HISTORICAL TRACES ===\n\n"
            seen_ids = set()
            for s in summaries:
                if s["id"] not in seen_ids:
                    seen_ids.add(s["id"])
                    text += f"Trace ID {s['id']} | Date: {s['timestamp'][:19]}\n"
                    text += f"  Root: {s['root_node']}\n"
                    text += f"  Filter: {s.get('filter_value', 'None')}\n"
                    text += f"  Edges: {s['total_edges']}\n\n"
            return text
        else:
            return "No historical traces found."

    # Normal semantic search using embeddings
    results = vector_store.search_traces(question, k=20)  # Or any number you want

    if not results:
        return "No matching historical traces found."

    text = f"=== SEARCH RESULTS FOR: '{question}' ===\n\n"
    seen_ids = set()
    for r in results:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            text += f"Trace ID {r['id']} (Score: {r['similarity_score']:.2f})\n"
            text += f"  Date: {r['timestamp'][:19]}\n"
            text += f"  Root: {r['root_node']}\n"
            text += f"  Filter: {r.get('filter_value', 'None')}\n"
            text += f"  Edges: {r['total_edges']} | Depth: {r['max_level']}\n\n"

    return text


def ask_lineage_agent(
    session_id: str,
    question: str,
    edges: List[Dict],
    samples: Dict,
    filter_value: str = None,
    include_historical: bool = False,
    current_trace_id: int = None,
) -> str:
    """Main entry point for lineage questions."""
    try:
        has_active_trace = len(edges) > 0

        logger.info(f"Session: {session_id}")
        logger.info(f"Question: {question}")
        logger.info(f"Active Trace: {has_active_trace} ({len(edges)} edges)")
        logger.info(f"Filter Value: {filter_value}")
        logger.info(f"Force Historical: {include_historical}")

        # Route question
        if include_historical:
            agent_name = "historical_search_agent"
            logger.info("Forced routing to: historical_search_agent")
        else:
            agent_name = route_question(question, has_active_trace)

            logger.info(f"Supervisor routed to: {agent_name}")

        # Prepare contexts
        current_context = format_current_trace_context(
            edges, samples, filter_value, current_trace_id
        )
        historical_context = (
            format_historical_context(question)
            if agent_name == "historical_search_agent"
            else ""
        )

        logger.info(f"Current Context Length: {len(current_context)} chars")
        logger.info(f"Historical Context Length: {len(historical_context)} chars")

        # Execute agent
        response = execute_agent(
            agent_name=agent_name,
            current_context=current_context,
            historical_context=historical_context,
            question=question,
        )

        logger.info(f"Final Response Length: {len(response)} chars")

        # Log the Q&A for traceability
        logger.info(f"CHATBOT Q&A | Question: {question}")
        logger.info(f"CHATBOT Q&A | Answer: {response}")

        return response

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        return f"Error processing question: {str(e)}"


def save_trace_to_history(
    edges: List[Dict],
    samples: Dict,
    filter_value: str = None,
    project_id: str = None,
    session_id: str = None,
    user_notes: str = None,
) -> int:
    """Save or update trace in vector store"""
    if not vector_store:
        logger.warning("Vector store not initialized, cannot save trace")
        return None

    try:
        # Determine root node
        if not edges:
            logger.warning("Cannot save empty trace")
            return None

        root_node = edges[0]["source"]

        logger.info(
            f"Saving trace: root={root_node}, filter={filter_value}, project_id={project_id}"
        )
        logger.info(f"Trace has {len(edges)} edges, {len(samples)} nodes")

        # Sanitize samples
        sanitized_samples = {}
        for node, data in samples.items():
            sanitized_samples[node] = {
                "adls": [str(v) for v in data.get("adls", [])],
                "snowflake": [str(v) for v in data.get("snowflake", [])],
                "databricks": [str(v) for v in data.get("databricks", [])],
                "adls_count": int(data.get("adls_count", 0)),
                "snowflake_count": int(data.get("snowflake_count", 0)),
                "databricks_count": int(data.get("databricks_count", 0)),
            }

        sanitized_edges = [
            {
                "source": str(e["source"]),
                "target": str(e["target"]),
                "level": int(e["level"]),
            }
            for e in edges
        ]

        # Check if trace already exists
        existing_trace = vector_store.find_existing_trace(root_node, filter_value)

        if existing_trace:
            # UPDATE existing trace
            trace_id = vector_store.update_trace(
                existing_trace["id"], sanitized_edges, sanitized_samples
            )
            logger.info(f"Updated existing trace ID: {trace_id}")
        else:
            # CREATE new trace
            trace_id = vector_store.add_trace(
                sanitized_edges,
                sanitized_samples,
                str(filter_value) if filter_value else None,
                str(session_id) if session_id else None,
                str(user_notes) if user_notes else None,
            )
            logger.info(f"Created new trace ID: {trace_id}")

        return trace_id

    except Exception as e:
        logger.error(f"Failed to save trace: {e}", exc_info=True)
        return None
