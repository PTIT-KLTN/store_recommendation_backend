from datetime import datetime
from bson import ObjectId

class AdminValidationError(Exception):
    """Exception raised khi dữ liệu Admin không hợp lệ."""
    pass

class Admin:
    def __init__(self,
                 email: str,
                 password: str,
                 fullname: str,
                 is_enabled: bool = True,
                 created_at: datetime = None,
                 updated_at: datetime = None,
                 _id: ObjectId = None):
        
        # Validate bắt buộc
        if not email:
            raise AdminValidationError("Email is required")
        if not password:
            raise AdminValidationError("Password is required")
        if not fullname:
            raise AdminValidationError("Fullname is required")

        # Field MongoDB
        self._id = _id or ObjectId()

        # Các trường chính
        self.email = email
        self.password = password
        self.fullname = fullname
        self.is_enabled = is_enabled

        # Timestamps
        now = datetime.utcnow()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def to_dict(self) -> dict:
        """Chuyển Admin thành dict để lưu vào MongoDB."""
        return {
            "_id": self._id,
            "email": self.email,
            "password": self.password,
            "fullname": self.fullname,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Admin":
        return cls(
            email=data.get("email"),
            password=data.get("password"),
            fullname=data.get("fullname"),
            is_enabled=data.get("is_enabled", True),
            created_at=data.get("created_at", datetime.utcnow().now()),
            updated_at=data.get("updated_at", datetime.utcnow().now()),
            _id=data.get("_id")
        )

    def is_active(self) -> bool:
        return self.is_enabled

    def to_public_dict(self) -> dict:
        return {
            "id": str(self._id),
            "email": self.email,
            "fullname": self.fullname,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
