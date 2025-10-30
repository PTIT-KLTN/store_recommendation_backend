import logging
from typing import List, Dict, Any, Optional
from database.mongodb import get_database

logger = logging.getLogger(__name__)


class AllergyService:
    
    def __init__(self):
        self.db = get_database()
        self.users_collection = self.db['users']
    
    def add_allergy(self, user_email: str, ingredient_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Validate input
            if not ingredient_data.get('name_vi'):
                return {
                    'success': False,
                    'error': 'name_vi is required'
                }
            
            normalized_name = ingredient_data['name_vi'].lower().strip()
            
            # Check if allergy already exists
            user = self.users_collection.find_one({'email': user_email})
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            existing_allergies = user.get('allergies', [])
            
            # Check duplicate by name
            for allergy in existing_allergies:
                if allergy.get('name_vi', '').lower().strip() == normalized_name:
                    return {
                        'success': False,
                        'error': f'Allergy "{ingredient_data["name_vi"]}" already exists'
                    }
            
            # Prepare allergy object
            allergy_obj = {
                'ingredient_id': ingredient_data.get('ingredient_id', ''),
                'name_vi': ingredient_data['name_vi'],
                'name_en': ingredient_data.get('name_en', ''),
                'category': ingredient_data.get('category', '')
            }
            
            # Add to user's allergies
            result = self.users_collection.update_one(
                {'email': user_email},
                {'$push': {'allergies': allergy_obj}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Added allergy '{ingredient_data['name_vi']}' for user {user_email}")
                return {
                    'success': True,
                    'message': 'Allergy added successfully',
                    'allergy': allergy_obj
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to add allergy'
                }
                
        except Exception as e:
            logger.error(f"Error adding allergy: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def remove_allergy(self, user_email: str, allergy_name: str) -> Dict[str, Any]:
        try:
            normalized_name = allergy_name.lower().strip()
            
            # Remove allergy by name
            result = self.users_collection.update_one(
                {'email': user_email},
                {
                    '$pull': {
                        'allergies': {
                            'name_vi': {'$regex': f'^{normalized_name}$', '$options': 'i'}
                        }
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Removed allergy '{allergy_name}' for user {user_email}")
                return {
                    'success': True,
                    'message': 'Allergy removed successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Allergy not found or already removed'
                }
                
        except Exception as e:
            logger.error(f"Error removing allergy: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_allergies(self, user_email: str) -> List[Dict[str, Any]]:
        try:
            user = self.users_collection.find_one(
                {'email': user_email},
                {'allergies': 1}
            )
            
            if user:
                return user.get('allergies', [])
            else:
                logger.warning(f"User {user_email} not found")
                return []
                
        except Exception as e:
            logger.error(f"Error getting allergies: {e}", exc_info=True)
            return []
    
    def filter_cart_items(
        self,
        cart_items: List[Dict[str, Any]],
        user_allergies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not user_allergies:
            return {
                'filtered_items': cart_items,
                'allergy_warnings': [],
                'removed_count': 0
            }
        
        # Create set of allergy names (lowercase) for fast lookup
        allergy_names = set()
        for allergy in user_allergies:
            allergy_names.add(allergy.get('name_vi', '').lower().strip())
            if allergy.get('name_en'):
                allergy_names.add(allergy.get('name_en', '').lower().strip())
        
        filtered_items = []
        allergy_warnings = []
        
        for item in cart_items:
            item_name_vi = item.get('name_vi', '').lower().strip()
            item_name_en = item.get('name_en', '').lower().strip()
            
            # Check if item is in allergy list
            is_allergic = (
                item_name_vi in allergy_names or
                item_name_en in allergy_names
            )
            
            if is_allergic:
                # Add warning
                allergy_warnings.append({
                    'ingredient_id': item.get('ingredient_id', ''),
                    'name_vi': item.get('name_vi', ''),
                    'name_en': item.get('name_en', ''),
                    'message': f'Bạn dị ứng với "{item.get("name_vi")}" - đã loại bỏ khỏi giỏ hàng',
                    'severity': 'error',
                    'source': 'allergy_filter'
                })
                logger.info(f"Filtered allergic ingredient: {item.get('name_vi')}")
            else:
                # Keep item if not allergic
                filtered_items.append(item)
        
        return {
            'filtered_items': filtered_items,
            'allergy_warnings': allergy_warnings,
            'removed_count': len(cart_items) - len(filtered_items)
        }
    
    def clear_all_allergies(self, user_email: str) -> Dict[str, Any]:
        try:
            result = self.users_collection.update_one(
                {'email': user_email},
                {'$set': {'allergies': []}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Cleared all allergies for user {user_email}")
                return {
                    'success': True,
                    'message': 'All allergies cleared successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'No allergies to clear or user not found'
                }
                
        except Exception as e:
            logger.error(f"Error clearing allergies: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
_allergy_service_instance: Optional[AllergyService] = None


def get_allergy_service() -> AllergyService:
    global _allergy_service_instance
    
    if _allergy_service_instance is None:
        _allergy_service_instance = AllergyService()
        logger.info("Allergy service initialized")
    
    return _allergy_service_instance
