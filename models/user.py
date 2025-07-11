from datetime import datetime

class User:
    def __init__(self, email, password, fullname, role='USER'):
        self.email = email
        self.password = password
        self.fullname = fullname
        self.role = role
        self.location = None
        self.basket_id = None
        self.near_stores = []
        self.saved_baskets = []
        self.is_enabled = True
        self.created_at = datetime.utcnow()
    
    def to_dict(self):
        return {
            'email': self.email,
            'password': self.password,
            'fullname': self.fullname,
            'role': self.role,
            'location': self.location,
            'basket_id': self.basket_id,
            'near_stores': self.near_stores,
            'saved_baskets': self.saved_baskets,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        user = cls(
            email=data['email'],
            password=data['password'],
            fullname=data['fullname'],
            role=data.get('role', 'USER')
        )
        user.location = data.get('location')
        user.basket_id = data.get('basket_id')
        user.near_stores = data.get('near_stores', [])
        user.saved_baskets = data.get('saved_baskets', [])
        user.is_enabled = data.get('is_enabled', True)
        user.created_at = data.get('created_at', datetime.utcnow())
        return user
