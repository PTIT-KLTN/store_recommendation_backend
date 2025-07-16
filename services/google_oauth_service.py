import os
import requests

class GoogleOAuthService:
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/auth/google/callback')
        
    def exchange_code_for_token(self, authorization_code):
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': authorization_code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(token_url, data=data, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
            token_data = response.json()
            
            if 'error' in token_data:
                error_msg = f"{token_data['error']}"
                if 'error_description' in token_data:
                    error_msg += f": {token_data['error_description']}"
                raise Exception(error_msg)
                
            return token_data
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when calling Google: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to get token from Google: {str(e)}")
    
    def get_user_info(self, access_token):
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(user_info_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when getting user info: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to get user info from Google: {str(e)}")
