from ingredient import Ingredient

class Dish:
    def __init__(self, name, vietnamese_name, servings=1, image_url=None):
        self.name = name
        self.vietnamese_name = vietnamese_name
        self.servings = servings
        self.image_url = image_url
        self.ingredients = []
        self.optional_ingredients = []
    
    def to_dict(self):
        return {
            'name': self.name,
            'vietnamese_name': self.vietnamese_name,
            'servings': self.servings,
            'image_url': self.image_url,
            'ingredients': [ing.to_dict() for ing in self.ingredients],
            'optional_ingredients': [ing.to_dict() for ing in self.optional_ingredients]
        }
    
    @classmethod
    def from_dict(cls, data):
        dish = cls(
            name=data['name'],
            vietnamese_name=data['vietnamese_name'],
            servings=data.get('servings', 1),
            image_url=data.get('image_url')
        )
        dish.ingredients = [Ingredient.from_dict(ing) for ing in data.get('ingredients', [])]
        dish.optional_ingredients = [Ingredient.from_dict(ing) for ing in data.get('optional_ingredients', [])]
        return dish
