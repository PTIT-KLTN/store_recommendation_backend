from mongodb import MongoDBConnection

primary_db = MongoDBConnection.get_primary_db()

def create_collections():
    try:
        # database collections
        primary_db.create_collection('ingredients')
        primary_db.create_collection('dishes') 
        primary_db.create_collection('users')
        primary_db.create_collection('baskets')
        
    except Exception as e:
        if "already exists" in str(e):
            print("Collections already exist")
        else:
            print(f"Error creating collections: {e}")

def create_indexes():
    try:
        # DB indexes
        primary_db.ingredients.create_index('name')
        primary_db.ingredients.create_index('vietnameseName')
        primary_db.dishes.create_index('name')
        primary_db.users.create_index('email', unique=True)
        
        print("Created indexes")
    except Exception as e:
        print(f"Error creating indexes: {e}")

if __name__ == "__main__":
    create_collections()
    create_indexes()