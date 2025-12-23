# User Management API Documentation

## Overview
API để quản lý người dùng (USER) trong hệ thống. Chỉ dành cho Admin và Super Admin.

---

## 1. Lấy danh sách người dùng

**Endpoint:** `GET /api/v1/admin/users`

**Quyền truy cập:** Admin và Super Admin

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 0 | Số trang (bắt đầu từ 0) |
| size | integer | No | 20 | Số lượng user trên mỗi trang |
| search | string | No | - | Tìm kiếm theo email hoặc fullname |

**Example Request:**
```bash
GET /api/v1/admin/users?page=0&size=20&search=nguyen
```

**Response Success (200):**
```json
{
  "users": [
    {
      "id": "689b04d20617a1cd335b1c9c",
      "email": "ngphthao031028@gmail.com",
      "fullname": "Nguyễn Thị Phương Thảo",
      "role": "USER",
      "location": {
        "latitude": 10.778799835470902,
        "longitude": 106.75003057837614,
        "address": "Đường D3, Khu phố 25, Phường Bình Trưng, Thủ Đức, Ho Chi Minh City, 71..."
      },
      "near_stores": [...],
      "saved_baskets": [...],
      "favourite_stores": ["store_id_1", "store_id_2"],
      "allergies": ["ingredient_id_1", "ingredient_id_2"],
      "is_enabled": true,
      "created_at": "2025-08-12T09:09:38.936+00:00",
      "near_stores_updated_at": "2025-12-20T07:01:08.029+00:00",
      "updated_at": "2025-12-20T08:30:25.987+00:00"
    }
  ],
  "pagination": {
    "currentPage": 0,
    "pageSize": 20,
    "totalPages": 5,
    "totalElements": 95,
    "hasNext": true,
    "hasPrevious": false
  }
}
```

**Response Error (403):**
```json
{
  "message": "Access denied. Admin role required"
}
```

---

## 2. Disable/Enable tài khoản người dùng

**Endpoint:** `PATCH /api/v1/admin/users/:user_id/status`

**Quyền truy cập:** Super Admin only

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | Yes | MongoDB ObjectId của user |

**Request Body:**
```json
{
  "is_enabled": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| is_enabled | boolean | Yes | `true` để bật, `false` để tắt tài khoản |

**Example Request:**
```bash
PATCH /api/v1/admin/users/689b04d20617a1cd335b1c9c/status
Content-Type: application/json

{
  "is_enabled": false
}
```

**Response Success (200):**
```json
{
  "message": "User account disabled successfully",
  "user": {
    "id": "689b04d20617a1cd335b1c9c",
    "email": "ngphthao031028@gmail.com",
    "fullname": "Nguyễn Thị Phương Thảo",
    "role": "USER",
    "is_enabled": false,
    "updated_at": "2025-12-23T10:30:00.000+00:00"
  }
}
```

**Response Error (400) - Invalid ObjectId:**
```json
{
  "message": "Invalid ObjectId format"
}
```

**Response Error (403) - Insufficient permissions:**
```json
{
  "message": "Access denied. Super admin role required"
}
```

**Response Error (404) - User not found:**
```json
{
  "message": "User not found"
}
```

---

## UI Implementation Guide

### 1. Danh sách người dùng (User List)

**Gợi ý Components:**
- Table/DataGrid hiển thị danh sách users
- Search bar để tìm kiếm
- Pagination controls
- Filter theo status (enabled/disabled)

**Hiển thị thông tin:**
- Email
- Họ tên
- Trạng thái (Active/Disabled)
- Số lượng cửa hàng yêu thích
- Số lượng dị ứng
- Ngày tạo
- Actions (View detail, Disable/Enable)

**Permissions:**
- Admin: Chỉ xem được danh sách
- Super Admin: Xem được danh sách + Disable/Enable user

### 2. Chi tiết người dùng (User Detail)

**Hiển thị đầy đủ:**
- Thông tin cá nhân
- Location với map
- Danh sách cửa hàng yêu thích
- Danh sách dị ứng
- Near stores
- Saved baskets
- Timeline hoạt động

### 3. Actions

**Toggle Status Button:**
```javascript
// Chỉ hiển thị cho Super Admin
{userRole === 'SUPER_ADMIN' && (
  <Button 
    onClick={() => toggleUserStatus(userId, !isEnabled)}
    variant={isEnabled ? 'danger' : 'success'}
  >
    {isEnabled ? 'Disable Account' : 'Enable Account'}
  </Button>
)}
```

**Confirm Dialog:**
- Hiển thị confirm dialog trước khi disable/enable
- Warning message rõ ràng về hành động

---

## Notes

- Password không được trả về trong response
- `near_stores_updated_at` là thời điểm cập nhật danh sách cửa hàng gần
- `location` có thể null nếu user chưa cập nhật
- Disabled user vẫn tồn tại trong database nhưng không thể login
- Tất cả timestamps theo định dạng ISO 8601 UTC
