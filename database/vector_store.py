"""
Vector store for storing and searching historical lineage traces using FAISS
"""
import faiss
import numpy as np
import pickle
import os
from datetime import datetime
from typing import List, Dict, Optional
from core.logger import get_logger
from config.settings import settings
from services.llm_client import get_databricks_client

logger = get_logger("VectorStore")


class LineageVectorStore:
    def __init__(self, index_path=None, embedding_model=None):
        """
        Initialize FAISS vector store for lineage traces using Databricks GTE-Large.

        Args:
            index_path: Directory to store FAISS index and metadata (uses settings if None)
            embedding_model: Databricks embedding model name (uses settings if None)
        """
        self.index_path = index_path or settings.FAISS_INDEX_PATH
        self.index_file = settings.FAISS_INDEX_FILE
        self.metadata_file = settings.FAISS_METADATA_FILE

        # Create directory if not exists
        os.makedirs(self.index_path, exist_ok=True)

        # Configure shared Databricks OpenAI endpoint
        self.client = get_databricks_client()

        # Load embedding model
        self.embedding_model = embedding_model or settings.DATABRICKS_EMBEDDING_MODEL
        self.dimension = settings.DATABRICKS_EMBEDDING_DIMENSION

        logger.info(f"Using Databricks embedding model: {self.embedding_model}")

        # Load or create FAISS index
        self.index = self._load_or_create_index()
        self.metadata = self._load_metadata()

        logger.info(f"Vector store initialized with {self.index.ntotal} traces")

    def find_existing_trace(self, root_node: str, filter_value: str = None) -> Optional[Dict]:
        """
        Find if a trace with same root node and filter already exists.

        Args:
            root_node: Root node identifier
            filter_value: Filter value used in trace

        Returns:
            Existing trace metadata or None
        """
        for trace in reversed(self.metadata):  # Check most recent first
            if trace.get('deleted', False):
                continue

            if trace['root_node'] == root_node:
                # If both have same filter (including both None)
                if trace.get('filter_value') == filter_value:
                    return trace

        return None

    def update_trace(self, trace_id: int, edges: List[Dict], samples: Dict) -> int:
        """
        Update an existing trace with new data.

        Args:
            trace_id: ID of trace to update
            edges: New edges list
            samples: New samples dict

        Returns:
            trace_id
        """
        if trace_id >= len(self.metadata):
            logger.warning(f"Trace ID {trace_id} not found")
            return None

        # Update metadata
        self.metadata[trace_id]['edges'] = edges
        self.metadata[trace_id]['samples'] = samples
        self.metadata[trace_id]['timestamp'] = datetime.now().isoformat()
        self.metadata[trace_id]['total_edges'] = len(edges)
        self.metadata[trace_id]['max_level'] = max(e['level'] for e in edges) if edges else 0
        self.metadata[trace_id]['trace_count'] = self.metadata[trace_id].get('trace_count', 1) + 1

        # Regenerate embedding and update FAISS
        trace_text = self._create_trace_text(edges, samples, self.metadata[trace_id].get('filter_value'))
        self.metadata[trace_id]['trace_text'] = trace_text

        embedding = self._get_embedding(trace_text)
        embedding = np.array([embedding], dtype='float32')

        # Update in FAISS (overwrite at same index position)
        # Note: FAISS doesn't have direct update, so we mark and handle in search

        self._save_metadata()

        logger.info(f"Updated trace {trace_id} (traced {self.metadata[trace_id]['trace_count']} times)")
        return trace_id

    def _load_or_create_index(self):
        """Load existing FAISS index or create new one"""
        if os.path.exists(self.index_file):
            logger.info("Loading existing FAISS index")
            return faiss.read_index(self.index_file)
        else:
            logger.info("Creating new FAISS index")
            # Using L2 distance (can change to Inner Product if needed)
            return faiss.IndexFlatL2(self.dimension)

    def _load_metadata(self):
        if not os.path.exists(self.metadata_file):
            return []

        try:
            with open(self.metadata_file, "rb") as f:
                return pickle.load(f)
        except EOFError:
            logger.warning("Metadata file corrupted or empty. Reinitializing metadata.")
            return []

    def _save_index(self):
        """Save FAISS index to disk"""
        faiss.write_index(self.index, self.index_file)
        logger.info(f"FAISS index saved to {self.index_file}")

    def _save_metadata(self):
        """Save metadata to disk"""
        with open(self.metadata_file, 'wb') as f:
            pickle.dump(self.metadata, f)
        logger.info(f"Metadata saved to {self.metadata_file}")

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using Databricks GTE-Large"""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                encoding_format="float"
            )

            embedding = np.array(response.data[0].embedding, dtype='float32')
            logger.debug(f"Generated embedding of dimension {len(embedding)}")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return np.zeros(self.dimension, dtype='float32')
    def add_trace(self, edges: List[Dict], samples: Dict, filter_value: str = None,
                  session_id: str = None, user_notes: str = None):
        """
        Add a lineage trace to the vector store.

        Args:
            edges: List of edge dictionaries
            samples: Sample data dictionary
            filter_value: Optional filter value used in trace
            session_id: Session identifier
            user_notes: Optional user notes about this trace

        Returns:
            int: Index of added trace
        """
        if not edges:
            logger.warning("Cannot add empty trace")
            return None

        # Create text representation for embedding
        trace_text = self._create_trace_text(edges, samples, filter_value)

        # Generate embedding using Google API
        embedding = self._get_embedding(trace_text)
        embedding = np.array([embedding], dtype='float32')

        # Add to FAISS index
        self.index.add(embedding)

        # Store metadata
        trace_metadata = {
            'id': len(self.metadata),
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'edges': edges,
            'samples': samples,
            'filter_value': filter_value,
            'user_notes': user_notes,
            'trace_text': trace_text,
            'root_node': edges[0]['source'] if edges else None,
            'total_edges': len(edges),
            'max_level': max(e['level'] for e in edges) if edges else 0,
            'unique_nodes': len(set([e['source'] for e in edges] + [e['target'] for e in edges])),
            'trace_count': 1
        }

        self.metadata.append(trace_metadata)

        # Save to disk
        self._save_index()
        self._save_metadata()

        logger.info(f"Added trace {trace_metadata['id']} with {len(edges)} edges")
        return trace_metadata['id']

    def _create_trace_text(self, edges: List[Dict], samples: Dict, filter_value: str = None) -> str:
        """
        Create searchable text representation of a trace.
        """
        text_parts = []

        # Add filter if present
        if filter_value:
            text_parts.append(f"Filter: {filter_value}")

        # Add all node names
        all_nodes = set()
        for e in edges:
            all_nodes.add(e['source'])
            all_nodes.add(e['target'])
        text_parts.append("Nodes: " + ", ".join(sorted(all_nodes)))

        # Add lineage flow
        flow = " -> ".join([f"{e['source']} to {e['target']}" for e in edges[:5]])  # First 5 edges
        text_parts.append(f"Flow: {flow}")

        # Add sample values from all sources
        sample_values = []
        for node, data in samples.items():
            if data.get('adls'):
                sample_values.extend([f"ADLS:{v}" for v in data['adls'][:3]])
            if data.get('snowflake'):
                sample_values.extend([f"Snowflake:{v}" for v in data['snowflake'][:3]])
            if data.get('databricks'):
                sample_values.extend([f"Databricks:{v}" for v in data['databricks'][:3]])

        if sample_values:
            text_parts.append("Samples: " + ", ".join(sample_values[:20]))

        return " | ".join(text_parts)

    def search_traces(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search for similar traces using semantic search.

        Args:
            query: Search query (natural language or keywords)
            k: Number of results to return

        Returns:
            List of trace metadata dictionaries with similarity scores
        """
        if self.index.ntotal == 0:
            logger.warning("No traces in index")
            return []

        # Generate query embedding using Google API
        query_embedding = self._get_embedding(query)
        query_embedding = np.array([query_embedding], dtype='float32')

        # Search FAISS index
        k = min(k, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, k)

        # Retrieve metadata
        results = []
        for idx, (distance, trace_idx) in enumerate(zip(distances[0], indices[0])):
            if trace_idx < len(self.metadata):
                result = self.metadata[trace_idx].copy()
                result['similarity_score'] = float(1 / (1 + distance))  # Convert distance to similarity
                result['rank'] = idx + 1
                results.append(result)

        logger.info(f"Found {len(results)} traces for query: {query}")
        return results

    def search_by_node(self, node_name: str, k: int = 5) -> List[Dict]:
        """
        Find all traces containing a specific node.

        Args:
            node_name: Node identifier (e.g., "gmpmsd_dev.project_metadata.strategy_id")
            k: Max number of results

        Returns:
            List of matching traces
        """
        matching_traces = []

        for trace in self.metadata:
            edges = trace['edges']
            all_nodes = set([e['source'] for e in edges] + [e['target'] for e in edges])

            if node_name in all_nodes:
                matching_traces.append(trace)

        # Sort by timestamp (most recent first)
        matching_traces.sort(key=lambda x: x['timestamp'], reverse=True)

        return matching_traces[:k]

    def search_by_filter(self, filter_value: str, k: int = 10) -> List[Dict]:
        """
        Find traces that used a specific filter value.
        """
        matching_traces = []

        for trace in self.metadata:
            if trace.get('filter_value') == filter_value:
                matching_traces.append(trace)

        matching_traces.sort(key=lambda x: x['timestamp'], reverse=True)
        return matching_traces[:k]

    def get_trace_by_id(self, trace_id: int) -> Optional[Dict]:
        """Retrieve a specific trace by ID"""
        if 0 <= trace_id < len(self.metadata):
            return self.metadata[trace_id]
        return None

    def compare_traces(self, trace_id1: int, trace_id2: int) -> Dict:
        """
        Compare two traces and return differences.

        Returns:
            Dictionary with comparison results
        """
        trace1 = self.get_trace_by_id(trace_id1)
        trace2 = self.get_trace_by_id(trace_id2)

        if not trace1 or not trace2:
            return {"error": "One or both traces not found"}

        # Extract node sets
        nodes1 = set([e['source'] for e in trace1['edges']] + [e['target'] for e in trace1['edges']])
        nodes2 = set([e['source'] for e in trace2['edges']] + [e['target'] for e in trace2['edges']])

        comparison = {
            'trace1_id': trace_id1,
            'trace2_id': trace_id2,
            'common_nodes': list(nodes1.intersection(nodes2)),
            'only_in_trace1': list(nodes1 - nodes2),
            'only_in_trace2': list(nodes2 - nodes1),
            'trace1_depth': trace1['max_level'],
            'trace2_depth': trace2['max_level'],
            'trace1_edges': trace1['total_edges'],
            'trace2_edges': trace2['total_edges'],
            'timestamp1': trace1['timestamp'],
            'timestamp2': trace2['timestamp']
        }

        return comparison

    def get_all_traces_summary(self) -> List[Dict]:
        """Get summary of all stored traces"""
        summaries = []
        for trace in self.metadata:
            if not trace.get('deleted', False):
                summaries.append({
                    'id': trace['id'],
                    'timestamp': trace['timestamp'],
                    'root_node': trace['root_node'],
                    'total_edges': trace['total_edges'],
                    'filter_value': trace.get('filter_value', 'None'),
                    'user_notes': trace.get('user_notes', '')
                })
        return summaries

    def delete_trace(self, trace_id: int):
        """Delete a trace (marks as deleted, doesn't rebuild index)"""
        if 0 <= trace_id < len(self.metadata):
            self.metadata[trace_id]['deleted'] = True
            self._save_metadata()
            logger.info(f"Marked trace {trace_id} as deleted")
        else:
            logger.warning(f"Trace {trace_id} not found")