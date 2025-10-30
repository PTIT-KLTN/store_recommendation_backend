import boto3
import uuid
import os
import logging
from typing import Optional, BinaryIO
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class S3Service:
    
    def __init__(
        self,
        aws_region: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None
    ):
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME", "recipe-images-bucket-v1")
        self.endpoint_url = endpoint_url or os.getenv("AWS_ENDPOINT_URL")
        
        client_config = {"region_name": self.aws_region}
        if self.endpoint_url:
            client_config["endpoint_url"] = self.endpoint_url
        
        try:
            self.s3_client = boto3.client("s3", **client_config)
            logger.info(f"S3 client initialized: bucket={self.bucket_name}, region={self.aws_region}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def upload_image(
        self,
        file: BinaryIO,
        filename: str,
        content_type: Optional[str] = None
    ) -> str:
        try:
            file_extension = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
            key = f"{uuid.uuid4().hex}.{file_extension}"
            
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            else:
                content_types = {
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp",
                    "gif": "image/gif",
                    "bmp": "image/bmp",
                    "tiff": "image/tiff",
                    "tif": "image/tiff"
                }
                extra_args["ContentType"] = content_types.get(
                    file_extension.lower(),
                    "application/octet-stream"
                )
            
            self.s3_client.upload_fileobj(file, self.bucket_name, key, ExtraArgs=extra_args)
            logger.info(f"Uploaded image to S3: {key}")
            return key
            
        except Exception as e:
            logger.error(f"Failed to upload image to S3: {e}")
            raise Exception(f"Failed to upload image: {str(e)}")
    
    def get_s3_url(self, key: str) -> str:
        if self.endpoint_url:
            return f"{self.endpoint_url}/{self.bucket_name}/{key}"
        else:
            return f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{key}"
    
    def delete_image(self, key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted image from S3: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete image from S3: {e}")
            return False


_s3_service_instance: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    global _s3_service_instance
    if _s3_service_instance is None:
        _s3_service_instance = S3Service()
        logger.info("S3 service initialized (singleton)")
    return _s3_service_instance
