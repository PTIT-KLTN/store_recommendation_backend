
from models.ingredient import Ingredient
from models.dish import Dish

class Basket:
    def __init__(self, user_id, basket_name="My Basket"):
        self.user_id = user_id
        self.basket_name = basket_name
        self.ingredients = []
        self.dishes = []
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'basket_name': self.basket_name,
            'ingredients': [ing.to_dict() for ing in self.ingredients],
            'dishes': [dish.to_dict() for dish in self.dishes]
        }
    
    @classmethod
    def from_dict(cls, data):
        basket = cls(
            user_id=data['user_id'],
            basket_name=data.get('basket_name', 'My Basket')
        )
        basket.ingredients = [Ingredient.from_dict(ing) for ing in data.get('ingredients', [])]
        basket.dishes = [Dish.from_dict(dish) for dish in data.get('dishes', [])]
        return basket