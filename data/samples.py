"""
Utility to fetch sample values from Denodo tables and Databricks
"""

from core.logger import get_logger
# from config.settings import settings  # Uncomment when re-enabling Databricks

logger = get_logger("SampleFetcher")


def fetch_snowflake_samples(
    cursor, domain, dataset, element, sample_size=5, filter_value=None, project_id=None
):
    if not dataset or not element:
        return [], 0

    try:
        # Build WHERE clause
        where_parts = [f'"{element}" IS NOT NULL']
        if filter_value:
            where_parts.append(f"\"{element}\" = '{filter_value}'")
        if project_id:
            where_parts.append(f"project_id = '{project_id}'")
        where_clause = " AND ".join(where_parts)

        # Count query
        count_query = f"SELECT COUNT(*) FROM {domain}.{dataset} WHERE {where_clause}"
        cursor.execute(count_query)
        total_count = cursor.fetchone()[0]

        # Sample query
        sample_query = f'SELECT "{element}" FROM {domain}.{dataset} WHERE {where_clause} LIMIT {sample_size}'
        cursor.execute(sample_query)
        results = cursor.fetchall()

        sample_values = [str(row[0]) for row in results if row[0] is not None]
        return sample_values, total_count

    except Exception as e:
        logger.warning(f"Snowflake fetch failed for {domain}.{dataset}.{element}: {e}")
        return [], 0


# ============================================================================
def fetch_databricks_samples(
    databricks_cursor, domain, dataset, element, sample_size=5, filter_value=None, project_id=None
):
    """
    Fetches sample values from Databricks sample table.

    Returns:
        Tuple[List[str], int]: (sample_values, total_count)
    """
    if not domain or not dataset or not element or databricks_cursor is None:
        logger.debug("Databricks sample fetch skipped")
        return [], 0

    from config.settings import settings
    if not all([settings.DATABRICKS_CATALOG, settings.DATABRICKS_SCHEMA, settings.DATABRICKS_TABLE]):
        logger.warning("Databricks table configuration not set")
        return [], 0

    catalog = settings.DATABRICKS_CATALOG
    schema = settings.DATABRICKS_SCHEMA
    table = settings.DATABRICKS_TABLE

    logger.info(f"Fetching Databricks samples for: {domain}.{dataset}.{element}")

    # Build WHERE clause
    where_parts = [
        f"`domain` = '{domain}'",
        f"`dataset` = '{dataset}'",
        f"`element` = '{element}'",
        "`sample_value` IS NOT NULL"
    ]
    if filter_value:
        where_parts.append(f"`sample_value` = '{filter_value}'")
    if project_id:
        where_parts.append(f"`project_id` = '{project_id}'")
        
    where_clause = " AND ".join(where_parts)

    try:
        # First, try to get total count
        count_query = f"SELECT COUNT(DISTINCT `sample_value`) FROM `{catalog}`.`{schema}`.`{table}` WHERE {where_clause}"
        databricks_cursor.execute(count_query)
        total_count = databricks_cursor.fetchone()[0]
    except Exception as e:
        logger.debug(f"Could not get Databricks count: {e}")
        total_count = 0

    try:
        # Select sample values
        sample_query = f"SELECT DISTINCT `sample_value` FROM `{catalog}`.`{schema}`.`{table}` WHERE {where_clause} LIMIT {sample_size}"
        databricks_cursor.execute(sample_query)
        results = databricks_cursor.fetchall()
        
        sample_values = [str(row[0]) for row in results if row[0] is not None]
        logger.info(f"Found {len(sample_values)} Databricks samples (total: {total_count})")
        return sample_values, total_count
    except Exception as e:
        logger.warning(f"Failed to fetch Databricks samples for {domain}.{dataset}.{element}: {e}")
        return [], total_count


def fetch_adls_samples(
    samples_df,
    domain,
    dataset,
    element,
    sample_size=5,
    filter_value=None,
    project_id=None,
):
    """
    Fetches sample values from ADLS CSV DataFrame.
    If project_id is provided, only rows matching that project_id are returned.
    """
    if samples_df is None:
        logger.debug(f"ADLS samples_df is None")
        return []

    adls_samples = []
    matches_found = 0

    try:
        for idx, row in samples_df.iterrows():
            row_domain = str(row.get("domain", "")).strip()
            row_dataset = str(row.get("dataset", "")).strip()
            row_element = str(row.get("element", "")).strip()
            sample_value = str(row.get("sample_value", "")).strip()
            row_project_id = str(row.get("project_id", "")).strip()

            # Match logic
            matched = False
            if dataset:  # 3-part node: domain.dataset.element
                if (
                    row_domain == domain
                    and row_dataset == dataset
                    and row_element == element
                ):
                    matched = True
                    matches_found += 1
            else:  # 2-part node: domain.element
                if row_domain == domain and row_element == element:
                    matched = True
                    matches_found += 1

            # Apply project_id filter if provided
            if matched and project_id and row_project_id != project_id:
                matched = False

            # Apply filter value if provided
            if matched and filter_value and sample_value != filter_value:
                matched = False

            if matched and sample_value:
                adls_samples.append(sample_value)
                if len(adls_samples) >= sample_size:
                    break

        if matches_found > 0:
            logger.info(
                f"Found {len(adls_samples)} ADLS samples for {domain}.{dataset}.{element} (total matches: {matches_found})"
            )
        else:
            logger.debug(f"No ADLS samples found for {domain}.{dataset}.{element}")

        return adls_samples[:sample_size]

    except Exception as e:
        logger.warning(
            f"Error fetching ADLS samples for {domain}.{dataset}.{element}: {e}"
        )
        return []


def aggregate_samples_from_all_sources(
    cursor,
    edges,
    samples_df,
    sample_size=5,
    databricks_cursor=None,
    filter_value=None,
    project_id=None,
):
    """
    Fetches sample values from ADLS, Snowflake, and Databricks, tracking the source.
    If project_id is provided, all queries are filtered by project_id.

    Args:
        project_id: Optional project ID to filter all data by

    Returns: Dictionary mapping node_id -> {
        'adls': [list of samples],
        'snowflake': [list of samples],
        'databricks': [list of samples]
    }
    """
    logger.info(f"Starting sample aggregation: {len(edges)} edges")
    logger.info(f"ADLS samples_df available: {samples_df is not None}")
    logger.info(f"Databricks cursor available: {databricks_cursor is not None}")
    logger.info(f"Filter value: {filter_value}")
    logger.info(f"Project ID: {project_id}")

    if samples_df is not None:
        logger.info(
            f"ADLS samples_df shape: {samples_df.shape}, columns: {list(samples_df.columns)}"
        )
        logger.info(f"First few rows: {samples_df.head(3).to_dict('records')}")

    samples_dict = {}
    processed_nodes = set()

    for edge in edges:
        for node_key in ["source", "target"]:
            node_id = edge[node_key]
            if node_id in processed_nodes:
                continue
            processed_nodes.add(node_id)

            samples_dict[node_id] = {
                "adls": [],
                "adls_count": 0,
                "snowflake": [],
                "snowflake_count": 0,
                "databricks": [],
                "databricks_count": 0,
            }
            parts = node_id.split(".")
            logger.debug(f"Processing node: {node_id}, parts: {parts}")

            # NEW CLEAN CODE:
            # Fetch from ADLS
            if len(parts) == 3:
                domain, dataset, element = parts
                adls_samples = fetch_adls_samples(
                    samples_df,
                    domain,
                    dataset,
                    element,
                    sample_size,
                    filter_value,
                    project_id,
                )
                samples_dict[node_id]["adls"] = adls_samples
                samples_dict[node_id]["adls_count"] = len(adls_samples)
            elif len(parts) == 2:
                domain, element = parts[0], parts[1]
                adls_samples = fetch_adls_samples(
                    samples_df,
                    domain,
                    None,
                    element,
                    sample_size,
                    filter_value,
                    project_id,
                )
                samples_dict[node_id]["adls"] = adls_samples
                samples_dict[node_id]["adls_count"] = len(adls_samples)
            else:
                samples_dict[node_id]["adls"] = []
                samples_dict[node_id]["adls_count"] = 0

            # NEW CLEAN CODE - REPLACE WITH THIS:
            # Fetch from Snowflake
            if len(parts) == 3:
                domain, dataset, element = parts
                try:
                    logger.debug(
                        f"Fetching Snowflake samples for: {domain}.{dataset}.{element}"
                    )

                    # CLEAN: All logic in one function call
                    snowflake_samples, snowflake_count = fetch_snowflake_samples(
                        cursor,
                        domain,
                        dataset,
                        element,
                        sample_size,
                        filter_value,
                        project_id,
                    )

                    samples_dict[node_id]["snowflake"] = snowflake_samples
                    samples_dict[node_id]["snowflake_count"] = snowflake_count

                    if snowflake_samples:
                        logger.info(
                            f"Found {len(snowflake_samples)} Snowflake samples for {node_id}"
                        )

                except Exception as e:
                    logger.warning(f"Error fetching Snowflake samples for {node_id}: {e}")
                    samples_dict[node_id]["snowflake"] = []
                    samples_dict[node_id]["snowflake_count"] = 0

                # Fetch from Databricks
                if databricks_cursor is not None:
                    try:
                        logger.debug(
                            f"Fetching Databricks samples for: {domain}.{dataset}.{element}"
                        )

                        # Fetch samples
                        databricks_samples, databricks_count = fetch_databricks_samples(
                            databricks_cursor,
                            domain,
                            dataset,
                            element,
                            sample_size,
                            filter_value,
                            project_id,
                        )

                        samples_dict[node_id]["databricks"] = databricks_samples
                        samples_dict[node_id]["databricks_count"] = databricks_count

                        if databricks_samples:
                            logger.info(
                                f"Found {len(databricks_samples)} Databricks samples for {node_id}"
                            )

                    except Exception as e:
                        logger.warning(
                            f"Error fetching Databricks samples for {node_id}: {e}"
                        )
                        samples_dict[node_id]["databricks"] = []
                        samples_dict[node_id]["databricks_count"] = 0
                else:
                    logger.debug(f"Databricks cursor is None for {node_id}")

            elif len(parts) == 2:
                logger.debug(
                    f"Node {node_id} has only 2 parts, skipping Snowflake/Databricks fetch"
                )
                samples_dict[node_id]["snowflake"] = []
                samples_dict[node_id]["snowflake_count"] = 0
                samples_dict[node_id]["databricks"] = []
                samples_dict[node_id]["databricks_count"] = 0
            else:
                logger.debug(
                    f"Node {node_id} has {len(parts)} parts, unexpected format"
                )

    # Count samples found
    total_adls = sum(len(s["adls"]) for s in samples_dict.values())
    total_snowflake = sum(len(s["snowflake"]) for s in samples_dict.values())
    total_databricks = sum(len(s["databricks"]) for s in samples_dict.values())

    logger.info(
        f"Fetched samples for {len(samples_dict)} nodes: ADLS={total_adls}, Snowflake={total_snowflake}, Databricks={total_databricks}"
    )
    return samples_dict
