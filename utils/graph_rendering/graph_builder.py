"""
Graph building utilities for lineage visualization
"""

def get_graph_statistics(edges):
    """
    Calculate statistics about the lineage graph.

    Args:
        edges: List of edge dictionaries with 'source', 'target', 'level'

    Returns:
        Dictionary with statistics including:
        - total_edges: Total number of relationships
        - max_level: Maximum depth in the lineage
        - unique_nodes: Number of unique nodes
        - nodes_per_level: Dictionary mapping level to node count
    """
    if not edges:
        return {
            "total_edges": 0,
            "max_level": 0,
            "unique_nodes": 0,
            "nodes_per_level": {}
        }

    # Collect unique nodes
    unique_sources = set(e['source'] for e in edges)
    unique_targets = set(e['target'] for e in edges)
    all_nodes = unique_sources.union(unique_targets)

    # Find maximum level
    max_level = max(e['level'] for e in edges)

    # Count nodes per level
    level_map = {}
    for edge in edges:
        level = edge['level']

        # Add target to current level
        if level not in level_map:
            level_map[level] = set()
        level_map[level].add(edge['target'])

        # Add source to previous level
        if level > 0:
            prev_level = level - 1
            if prev_level not in level_map:
                level_map[prev_level] = set()
            level_map[prev_level].add(edge['source'])

    # Convert sets to counts
    nodes_per_level = {level: len(nodes) for level, nodes in level_map.items()}

    return {
        "total_edges": len(edges),
        "max_level": max_level,
        "unique_nodes": len(all_nodes),
        "nodes_per_level": nodes_per_level
    }


def get_flattened_paths(edges):
    """
    Converts a list of edges into distinct lineage paths.
    Strictly enforces level continuity (1->2->3) to avoid jumping paths.

    Args:
        edges: List of edge dictionaries with 'source', 'target', 'level'

    Returns:
        List of edge dictionaries with separator rows between paths
    """
    if not edges:
        return []

    # Build Adjacency Map
    adj_map = {}
    min_level = float('inf')

    for edge in edges:
        src = edge['source']
        if src not in adj_map:
            adj_map[src] = []
        adj_map[src].append(edge)

        if edge['level'] < min_level:
            min_level = edge['level']

    # Find Roots (edges at minimum level)
    roots = [e for e in edges if e['level'] == min_level]

    # Recursive DFS with STRICT LEVEL CHECK
    all_paths = []

    def find_paths(current_edge, current_path):
        target = current_edge['target']
        current_level_val = current_edge['level']

        if target in adj_map:
            children = adj_map[target]
            found_child = False

            for child in children:
                # ONLY follow children that are exactly one level deeper
                if child['level'] != current_level_val + 1:
                    continue

                # Avoid cycles
                if child in current_path:
                    continue

                found_child = True
                new_path = current_path + [child]
                find_paths(child, new_path)

            if not found_child:
                all_paths.append(current_path)
        else:
            all_paths.append(current_path)

    if not roots:
        return edges

    # Start DFS from each root
    for r in roots:
        find_paths(r, [r])

    # Format for Display with separators
    display_rows = []
    seen_paths_hashes = set()

    for path in all_paths:
        # Create unique hash for this path
        path_hash = tuple((e['source'], e['target'], e['level']) for e in path)

        if path_hash in seen_paths_hashes:
            continue

        seen_paths_hashes.add(path_hash)

        # Add all edges in this path
        for edge in path:
            display_rows.append(edge)

        # Add separator
        display_rows.append({"source": "---", "target": "---", "level": "---"})

    # Remove trailing separator
    if display_rows and display_rows[-1]['source'] == "---":
        display_rows.pop()

    return display_rows