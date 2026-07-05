"""
Main graph renderer - orchestrates HTML generation and Streamlit rendering
"""

import json
import streamlit.components.v1 as components
from .html_template import build_graph_html


def get_database_color(node_name):
    """
    Extract database name and assign a consistent color based on hash.
    """
    parts = node_name.split(".")
    if len(parts) > 0:
        database = parts[0]
        hash_val = hash(database) % 360
        return f"hsl({hash_val}, 70%, 85%)"
    return "#E3F2FD"


def render_interactive_graph(edges, root_node, samples_with_source=None):
    """
    Renders an interactive graph using D3.js with scroll and click functionality.
    Node exploration now properly communicates with Streamlit using query params.

    Args:
        edges: List of edge dictionaries with 'source', 'target', 'level'
        root_node: String name of the root node to highlight
        samples_with_source: Dict mapping node_id -> {'adls': [], 'snowflake': [], 'databricks': []}
    """
    # Use pre-fetched samples with source information
    node_samples = samples_with_source if samples_with_source else {}

    # Build nodes and links data structure
    nodes_dict = {}
    links = []

    # Collect all unique nodes with their levels
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        level = edge["level"]

        # Add source node
        if source not in nodes_dict:
            source_level = level - 1 if level > 0 else 0
            nodes_dict[source] = {
                "id": source,
                "label": source,
                "level": source_level,
                "is_root": source == root_node,
                "database": source.split(".")[0] if "." in source else source,
            }

        # Add target node
        if target not in nodes_dict:
            nodes_dict[target] = {
                "id": target,
                "label": target,
                "level": level,
                "is_root": target == root_node,
                "database": target.split(".")[0] if "." in target else target,
            }

        # Add link
        links.append({"source": source, "target": target, "level": level})

    nodes = list(nodes_dict.values())

    # Convert to JSON
    graph_data = {
        "nodes": nodes,
        "links": links,
        "samples": node_samples,
    }
    graph_json = json.dumps(graph_data)

    # Build HTML from template
    html_code = build_graph_html(graph_json)

    # Render component
    components.html(html_code, height=800, scrolling=False)
