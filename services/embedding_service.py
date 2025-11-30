from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle
import os
from typing import List, Dict, Tuple
from bson import ObjectId
from fuzzywuzzy import fuzz
import re

class EmbeddingService:
    def __init__(self, model_name='keepitreal/vietnamese-sbert', index_dir='scripts/faiss_indexes'):
        """
        Initialize embedding service with FAISS

        Args:
            model_name: Sentence transformer model
            index_dir: Directory to store FAISS indexes
        """
        # Disable multiprocessing to prevent crashes on macOS
        import torch
        torch.set_num_threads(1)

        self.model = SentenceTransformer(model_name, device='cpu')
        self.model.eval()  # Set to evaluation mode
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.index_dir = index_dir
        self.indexes = {}  # {collection_name: faiss.Index}
        self.id_mappings = {}  # {collection_name: {faiss_idx: product_id}}
        self.product_data = {}  # {collection_name: {product_id: full_product_data}}

        # Create index directory if not exists
        os.makedirs(index_dir, exist_ok=True)
    
    def create_embeddings(self, texts: List[str]) -> np.ndarray:
        embeddings = self.model.encode(
            texts, 
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        # Normalize for cosine similarity (important!)
        embeddings = embeddings.astype('float32')
        faiss.normalize_L2(embeddings)
        
        return embeddings
    
    def build_index_for_collection(self, collection_name: str, products: List[Dict]) -> None:
        if not products:
            print(f"⚠️  No products to index for {collection_name}")
            return
        
        print(f"📊 Building index for {collection_name}: {len(products)} products")
        
        # Extract product names
        product_names = [p['name'] for p in products]
        
        # Create embeddings
        embeddings = self.create_embeddings(product_names)
        
        # Create FAISS index (Inner Product for normalized vectors = Cosine Similarity)
        index = faiss.IndexFlatIP(self.dimension)
        index.add(embeddings)
        
        # Create mappings
        id_mapping = {}
        product_data = {}
        
        for i, product in enumerate(products):
            product_id = str(product['_id'])
            id_mapping[i] = product_id
            product_data[product_id] = product
        
        # Store in memory
        self.indexes[collection_name] = index
        self.id_mappings[collection_name] = id_mapping
        self.product_data[collection_name] = product_data
        
        print(f"✅ Built index: {index.ntotal} vectors")
    
    def save_index(self, collection_name: str) -> None:
        """
        Save FAISS index and mappings to disk
        
        Args:
            collection_name: Name of the collection
        """
        if collection_name not in self.indexes:
            raise ValueError(f"Index for {collection_name} not found in memory")
        
        # Save FAISS index
        index_path = os.path.join(self.index_dir, f'{collection_name}.index')
        faiss.write_index(self.indexes[collection_name], index_path)
        
        # Save ID mapping
        mapping_path = os.path.join(self.index_dir, f'{collection_name}_mapping.pkl')
        with open(mapping_path, 'wb') as f:
            pickle.dump(self.id_mappings[collection_name], f)
        
        # Save product data
        data_path = os.path.join(self.index_dir, f'{collection_name}_data.pkl')
        with open(data_path, 'wb') as f:
            pickle.dump(self.product_data[collection_name], f)
        
        print(f"💾 Saved index for {collection_name}")
    
    def load_index(self, collection_name: str) -> None:
        """
        Load FAISS index and mappings from disk
        
        Args:
            collection_name: Name of the collection
        """
        index_path = os.path.join(self.index_dir, f'{collection_name}.index')
        mapping_path = os.path.join(self.index_dir, f'{collection_name}_mapping.pkl')
        data_path = os.path.join(self.index_dir, f'{collection_name}_data.pkl')

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Index file not found: {index_path}")
        
        # Load FAISS index
        self.indexes[collection_name] = faiss.read_index(index_path)
        
        # Load ID mapping
        with open(mapping_path, 'rb') as f:
            self.id_mappings[collection_name] = pickle.load(f)
        
        # Load product data
        with open(data_path, 'rb') as f:
            self.product_data[collection_name] = pickle.load(f)
        
        print(f"📂 Loaded index for {collection_name}: {self.indexes[collection_name].ntotal} vectors")
    
    def load_all_indexes(self, collection_names: List[str]) -> None:
        """
        Load multiple indexes at once
        
        Args:
            collection_names: List of collection names
        """
        print("🔄 Loading FAISS indexes...")
        
        for collection_name in collection_names:
            try:
                self.load_index(collection_name)
            except FileNotFoundError:
                print(f"⚠️  Index not found for {collection_name}, skipping...")
        
        print(f"✅ Loaded {len(self.indexes)} indexes")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text for fuzzy matching"""
        # Remove extra spaces and convert to lowercase
        text = re.sub(r'\s+', ' ', text.strip().lower())
        return text

    def _fuzzy_search(self, collection_name: str, query: str, store_id: int = None,
                      top_k: int = 10) -> List[Dict]:
        """
        Fuzzy string matching for short queries

        Args:
            collection_name: Collection to search in
            query: Search query text (normalized)
            store_id: Filter by store_id (optional)
            top_k: Number of results to return

        Returns:
            List of matched products with fuzzy scores
        """
        if collection_name not in self.product_data:
            return []

        normalized_query = self._normalize_text(query)
        fuzzy_results = []

        for product_id, product in self.product_data[collection_name].items():
            # Filter by store_id if provided
            if store_id is not None and product.get('store_id') != store_id:
                continue

            product_name = self._normalize_text(product.get('name', ''))

            # Calculate fuzzy scores
            partial_ratio = fuzz.partial_ratio(normalized_query, product_name)
            token_sort_ratio = fuzz.token_sort_ratio(normalized_query, product_name)

            # Boost score if query is a substring of product name
            if normalized_query in product_name:
                partial_ratio = min(100, partial_ratio + 20)

            # Use the higher score
            fuzzy_score = max(partial_ratio, token_sort_ratio) / 100.0

            if fuzzy_score >= 0.6:  # Minimum 60% fuzzy match
                product_copy = product.copy()
                product_copy['similarity_score'] = fuzzy_score
                product_copy['match_type'] = 'fuzzy'
                fuzzy_results.append(product_copy)

        # Sort by score descending
        fuzzy_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        return fuzzy_results[:top_k]

    def search(self, collection_name: str, query: str, store_id: int = None,
               top_k: int = 10, threshold: float = 0.5, category: str = '') -> List[Dict]:
        if collection_name not in self.indexes:
            print(f"⚠️  Index for {collection_name} not loaded")
            return []

        # Determine if query is short (use fuzzy matching)
        query_length = len(query.strip())
        is_short_query = query_length <= 6

        # For very short queries, prioritize fuzzy matching
        if is_short_query:
            print(f"Short query detected ('{query}'), using semantic search")

            # Get fuzzy results first
            fuzzy_results = self._fuzzy_search(collection_name, query, store_id, top_k * 2)

            # Also get semantic results with lower threshold
            enhanced_query = f"{query} {category}" if category else query
            query_embedding = self.create_embeddings([enhanced_query])

            # More aggressive search for short queries
            search_k = min(top_k * 20, self.indexes[collection_name].ntotal)
            scores, indices = self.indexes[collection_name].search(query_embedding, search_k)

            semantic_results = []
            # Use dynamic threshold for short queries
            dynamic_threshold = max(0.25, threshold - 0.15)

            for score, idx in zip(scores[0], indices[0]):
                if score < dynamic_threshold:
                    continue

                product_id = self.id_mappings[collection_name][idx]
                product = self.product_data[collection_name][product_id].copy()

                if store_id is not None and product.get('store_id') != store_id:
                    continue

                product['similarity_score'] = float(score)
                product['match_type'] = 'semantic'
                semantic_results.append(product)

            # Merge results: prioritize fuzzy, then add unique semantic results
            merged_results = fuzzy_results.copy()
            seen_ids = {str(p['_id']) for p in fuzzy_results}

            for sem_product in semantic_results:
                if str(sem_product['_id']) not in seen_ids:
                    merged_results.append(sem_product)
                    seen_ids.add(str(sem_product['_id']))

            # Re-sort by similarity score
            merged_results.sort(key=lambda x: x['similarity_score'], reverse=True)

            return merged_results[:top_k]

        else:
            # For longer queries, use standard semantic search with context enhancement
            enhanced_query = f"{query} {category}" if category else query
            query_embedding = self.create_embeddings([enhanced_query])

            # Search in FAISS (get more candidates for filtering)
            search_k = min(top_k * 10, self.indexes[collection_name].ntotal)
            scores, indices = self.indexes[collection_name].search(query_embedding, search_k)

            # Collect results
            results = []
            for score, idx in zip(scores[0], indices[0]):
                # Check threshold
                if score < threshold:
                    continue

                # Get product data
                product_id = self.id_mappings[collection_name][idx]
                product = self.product_data[collection_name][product_id].copy()

                # Filter by store_id if provided
                if store_id is not None and product.get('store_id') != store_id:
                    continue

                # Add similarity score
                product['similarity_score'] = float(score)
                product['match_type'] = 'semantic'
                results.append(product)

                # Stop if we have enough results
                if len(results) >= top_k:
                    break

            return results
    