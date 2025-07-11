class Ingredient:
    def __init__(self, name, vietnamese_name, unit, quantity, category, image_url=None):
        self.name = name
        self.vietnamese_name = vietnamese_name
        self.unit = unit
        self.quantity = quantity
        self.category = category
        self.image_url = image_url
        self.token_ngrams = []
    
    def to_dict(self):
        return {
            'name': self.name,
            'vietnamese_name': self.vietnamese_name,
            'unit': self.unit,
            'quantity': self.quantity,
            'category': self.category,
            'image_url': self.image_url,
            'token_ngrams': self.token_ngrams
        }
    
    @classmethod
    def from_dict(cls, data):
        ingredient = cls(
            name=data['name'],
            vietnamese_name=data['vietnamese_name'],
            unit=data['unit'],
            quantity=data['quantity'],
            category=data['category'],
            image_url=data.get('image_url')
        )
        ingredient.token_ngrams = data.get('token_ngrams', [])
        return ingredient