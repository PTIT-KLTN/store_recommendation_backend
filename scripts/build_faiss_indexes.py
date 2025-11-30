import sys
sys.path.append('..')

import os
# Disable multiprocessing to avoid segfault on macOS
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

from database.mongodb import MongoDBConnection
from services.embedding_service import EmbeddingService
from tqdm import tqdm
import gc
import torch

COLLECTIONS = [
    'alcoholic_beverages', 'beverages', 'cakes', 'candies',
    'cereals_&_grains', 'cold_cuts:_sausages_&_ham', 'dried_fruits',
    'fresh_fruits', 'fresh_meat', 'fruit_jam', 'grains_&_staples',
    'ice_cream_&_cheese', 'instant_foods', 'milk', 
    'seafood_&_fish_balls',
    'seasonings', 'snacks', 'vegetables', 'yogurt'
]

def build_all_indexes():
    """Build FAISS indexes for all collections"""

    print("🚀 Starting FAISS index building process...")
    print(f"{'='*70}\n")

    # Initialize database connection
    metadata_db = MongoDBConnection.get_metadata_db()

    total_products = 0
    successful_collections = 0

    for collection_name in tqdm(COLLECTIONS, desc="Processing collections"):
        print(f"\n📦 Collection: {collection_name}")
        print(f"{'-'*70}")

        try:
            # Get all products from collection
            collection = metadata_db[collection_name]

            # Fetch all necessary fields
            products = list(collection.find({}, {
                '_id': 1,
                'name': 1,
                'store_id': 1,
                'price': 1,
                'category': 1,
                'image': 1,
                'unit': 1,
                'chain': 1
            }))

            if not products:
                print(f"⚠️  No products found")
                continue

            # Initialize embedding service for each collection to avoid memory buildup
            embedding_service = EmbeddingService(
                model_name='keepitreal/vietnamese-sbert',
                index_dir='scripts/faiss_indexes'
            )

            # Build index
            embedding_service.build_index_for_collection(collection_name, products)

            # Save to disk
            embedding_service.save_index(collection_name)

            total_products += len(products)
            successful_collections += 1

            # Clean up memory after each collection
            del embedding_service
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n{'='*70}")
    print(f"🎉 Index building completed!")
    print(f"{'='*70}")
    print(f"✅ Successful collections: {successful_collections}/{len(COLLECTIONS)}")
    print(f"📊 Total products indexed: {total_products:,}")
    print(f"💾 Indexes saved to: ./faiss_indexes/")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    build_all_indexes()