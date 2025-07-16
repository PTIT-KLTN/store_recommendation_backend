import pymongo
import json
from bson import ObjectId
import random

class MongoRandomSampler:
    def __init__(self):
        self.connection_string = "mongodb+srv://n21dccn078:ABC12345678@storerecommender.w9auorn.mongodb.net/"
        self.db_name = "store_recommender"
        self.client = None
        self.db = None
        
        # Danh sách các collections
        self.collections = [
            "alcoholic_beverages",
            "beverages", 
            "cakes",
            "candies",
            "cereals_&_grains",
            "cold_cuts:_sausages_&_ham",
            "dried_fruits",
            "fresh_fruits",
            "fresh_meat",
            "fruit_jam",
            "grains_&_staples",
            "ice_cream_&_cheese",
            "instant_foods",
            "seafood_&_fish_balls",
            "seasonings",
            "snacks",
            "vegetables",
            "yogurt"
        ]
    
    def connect(self):
        """Kết nối với MongoDB"""
        try:
            self.client = pymongo.MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
            
            # Test connection
            self.client.admin.command('ping')
            print(f"✅ Kết nối thành công với database: {self.db_name}")
            return True
            
        except Exception as e:
            print(f"❌ Lỗi kết nối: {e}")
            return False
    
    def get_random_documents(self, collection_name, limit=50):
        """Lấy random documents từ một collection"""
        try:
            collection = self.db[collection_name]
            
            # Đếm tổng số documents
            total_count = collection.count_documents({})
            
            if total_count == 0:
                print(f"⚠️  Collection {collection_name} không có dữ liệu")
                return []
            
            # Sử dụng $sample để lấy random documents
            # Nếu tổng số ít hơn limit thì lấy tất cả
            sample_size = min(limit, total_count)
            
            pipeline = [
                {"$sample": {"size": sample_size}},
                {"$project": {
                    "_id": 1,
                    "name": 1,
                    "name_en": 1, 
                    "category": 1,
                    "unit": 1,
                    "image": 1
                }}
            ]
            
            documents = list(collection.aggregate(pipeline))
            
            # Convert ObjectId to string
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            print(f"✅ Lấy được {len(documents)}/{total_count} documents từ {collection_name}")
            return documents
            
        except Exception as e:
            print(f"❌ Lỗi khi lấy dữ liệu từ {collection_name}: {e}")
            return []
    
    def sample_all_collections(self, limit_per_collection=50):
        """Lấy random data từ tất cả collections"""
        if not self.connect():
            return None
        
        all_data = {}
        
        print(f"\n📊 Bắt đầu lấy {limit_per_collection} documents từ mỗi collection...")
        print("=" * 70)
        
        for collection_name in self.collections:
            print(f"\n🔄 Đang xử lý collection: {collection_name}")
            
            documents = self.get_random_documents(collection_name, limit_per_collection)
            all_data[collection_name] = {
                "collection_name": collection_name,
                "total_documents": len(documents),
                "data": documents
            }
        
        return all_data
    
    def save_to_json(self, data, filename="random_data_sample.json"):
        """Lưu dữ liệu ra file JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Đã lưu dữ liệu vào file: {filename}")
            return True
        except Exception as e:
            print(f"❌ Lỗi khi lưu file: {e}")
            return False
    
    def print_summary(self, data):
        """In tóm tắt dữ liệu"""
        print("\n" + "=" * 70)
        print("📋 TÓM TẮT DỮ LIỆU")
        print("=" * 70)
        
        total_documents = 0
        for collection_name, collection_data in data.items():
            count = collection_data['total_documents']
            total_documents += count
            print(f"📁 {collection_name:25} : {count:3} documents")
        
        print("-" * 70)
        print(f"📊 Tổng cộng: {total_documents} documents từ {len(data)} collections")
        
        # Hiển thị sample data từ collection đầu tiên
        if data:
            first_collection = list(data.keys())[0]
            first_data = data[first_collection]['data']
            if first_data:
                print(f"\n🔍 Sample data từ collection '{first_collection}':")
                print("-" * 50)
                sample_doc = first_data[0]
                for key, value in sample_doc.items():
                    print(f"  {key}: {value}")
    
    def close_connection(self):
        """Đóng kết nối"""
        if self.client:
            self.client.close()
            print("\n🔒 Đã đóng kết nối database")


def main():
    """Hàm main để chạy chương trình"""
    sampler = MongoRandomSampler()
    
    try:
        # Lấy dữ liệu random
        data = sampler.sample_all_collections(limit_per_collection=50)
        
        if data:
            # In tóm tắt
            sampler.print_summary(data)
            
            # Lưu ra file JSON
            sampler.save_to_json(data)
                    
        else:
            print("❌ Không thể lấy dữ liệu")
    
    except KeyboardInterrupt:
        print("\n⚠️  Chương trình bị ngắt bởi người dùng")
    except Exception as e:
        print(f"❌ Lỗi không mong muốn: {e}")
    finally:
        sampler.close_connection()

if __name__ == "__main__":
    main()


# Hàm utility để test connection đơn giản
def test_connection():
    """Test kết nối đơn giản"""
    sampler = MongoRandomSampler()
    if sampler.connect():
        print("🎉 Test connection thành công!")
        
        # List all collections
        collections = sampler.db.list_collection_names()
        print(f"📁 Các collections có sẵn: {collections}")
        
        sampler.close_connection()
        return True
    return False


# Hàm để lấy data từ một collection cụ thể
def get_single_collection_data(collection_name, limit=50):
    """Lấy data từ một collection cụ thể"""
    sampler = MongoRandomSampler()
    
    if sampler.connect():
        data = sampler.get_random_documents(collection_name, limit)
        sampler.close_connection()
        return data
    return []


# Example usage:
"""
# Chạy toàn bộ
python mongodb_sampler.py

# Hoặc sử dụng các hàm riêng lẻ:
if __name__ == "__main__":
    # Test connection
    test_connection()
    
    # Lấy data từ một collection
    fresh_fruits_data = get_single_collection_data("fresh_fruits", 10)
    print(fresh_fruits_data)
"""