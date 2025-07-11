import boto3
import uuid
from config import Config

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY,
            aws_secret_access_key=Config.AWS_SECRET_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=Config.AWS_ENDPOINT
        )
        self.bucket_name = Config.AWS_BUCKET_NAME
    
    def upload_image(self, file):
        try:
            key = f"{uuid.uuid4()}_{file.filename}"
            
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                key,
                ExtraArgs={'ContentType': file.content_type}
            )
            
            return key
        except Exception as e:
            raise Exception(f"Failed to upload image: {str(e)}")