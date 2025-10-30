from datetime import datetime

class UserValidationError(Exception):
    pass

class User:
    def __init__(self, email, password, fullname, role='USER'):
        if not email:
            raise UserValidationError("Email is required")
        if not fullname:
            raise UserValidationError("Fullname is required")
        
        self.email = email
        self.password = password
        self.fullname = fullname
        self.role = role
        self.location = None
        self.basket_id = None
        self.near_stores = []
        self.saved_baskets = []
        self.favourite_stores = []
        self.allergies = []  # List of ingredient IDs or names that user is allergic to
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
            'favourite_stores': self.favourite_stores,
            'allergies': self.allergies,
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
        user.favourite_stores = data.get('favourite_stores', [])
        user.allergies = data.get('allergies', [])
        user.is_enabled = data.get('is_enabled', True)
        user.created_at = data.get('created_at', datetime.utcnow())
        return user
    
    def is_active(self):
        """Check if user account is active"""
        return self.is_enabled
    
    def to_public_dict(self):
        """Return user data without sensitive information"""
        return {
            'email': self.email,
            'fullname': self.fullname,
            'role': self.role,
            'location': self.location,
            'favourite_stores': self.favourite_stores,
            'allergies': self.allergies,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at
        }