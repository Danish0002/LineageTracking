from core.logger import get_logger

logger = get_logger("LineageService")


def trace_lineage_recursive(
    cursor,
    source_domain,
    source_dataset,
    source_element,
    current_level,
    max_levels,
    edges_collector=None,
    filter_value=None,
    project_id=None,
):
    """
    Traces lineage recursively and returns node data list.
    If project_id is provided, the query is filtered by project_id.
    """
    if edges_collector is None:
        edges_collector = []

    node_data_list = []

    # Construct Source Display Name
    if source_dataset:
        source_display = f"{source_domain}.{source_dataset}.{source_element}"
    else:
        source_display = f"{source_domain}.{source_element}"

    # Check Max Depth
    if current_level >= max_levels:
        logger.warning(f"Max Depth reached. Stopping trace at: {source_display}")
        return node_data_list

    # Build Query
    sql_query = f"""
    SELECT 
        data_domain_instance_name, 
        data_set_name, 
        data_set_element_name,
        source_data_set_name
    FROM data_set_element_and_data_product_element_lineage
    WHERE source_data_domain_instance_name = '{source_domain}'
    AND source_data_set_element_name = '{source_element}'
    """
    if source_dataset:
        sql_query += f" AND source_data_set_name = '{source_dataset}'"

    try:
        cursor.execute(sql_query)
        results = cursor.fetchall()

        if not results and current_level == 0:
            logger.warning(f"No lineage found for root: {source_display}")

        for row in results:
            tgt_domain, tgt_dataset, tgt_element, actual_src_dataset = row
            real_source_display = (
                f"{source_domain}.{actual_src_dataset}.{source_element}"
            )
            tgt_display = f"{tgt_domain}.{tgt_dataset}.{tgt_element}"

            logger.info(f"{real_source_display} -> {tgt_display}")

            edges_collector.append(
                {
                    "source": real_source_display,
                    "target": tgt_display,
                    "level": current_level + 1,
                }
            )

            # Collect node data
            node_data_list.append(
                {
                    "domain": tgt_domain,
                    "dataset": tgt_dataset,
                    "element": tgt_element,
                    "filter_value": filter_value,
                    "project_id": project_id,
                }
            )

            # Recurse
            child_nodes = trace_lineage_recursive(
                cursor,
                tgt_domain,
                tgt_dataset,
                tgt_element,
                current_level + 1,
                max_levels,
                edges_collector,
                filter_value,
                project_id,
            )

            node_data_list.extend(child_nodes)

    except Exception as e:
        logger.error(f"Error processing {source_display}: {e}")

    return node_data_list
