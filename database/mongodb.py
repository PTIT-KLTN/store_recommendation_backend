import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from config import Config

class MongoDBConnection:
    _primary_client = None
    _metadata_client = None
    
    @classmethod
    def get_primary_db(cls):
        if cls._primary_client is None:
            cls._primary_client = MongoClient(Config.MONGODB_PRIMARY_URI)
        return cls._primary_client.get_default_database()
    
    @classmethod
    def get_metadata_db(cls):
        if cls._metadata_client is None:
            cls._metadata_client = MongoClient(Config.MONGODB_METADATA_URI)
        return cls._metadata_client.get_default_database()
    
    @classmethod
    def get_shard_db(cls, uri, db_name):
        client = MongoClient(uri)
        return client[db_name]