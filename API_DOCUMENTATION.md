# 📚 Main Service API Documentation

**Version:** 2.0  
**Last Updated:** October 31, 2025  
**For:** Frontend Development Team

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Base URL & Authentication](#base-url--authentication)
3. [AI Recipe Analysis APIs](#ai-recipe-analysis-apis)
   - [Text Analysis](#1-text-analysis)
   - [Image Analysis (with S3 URL)](#2-image-analysis-with-s3-url)
   - [Upload & Analyze](#3-upload--analyze-image)
   - [Health Check](#4-health-check)
4. [User Allergy Management APIs](#user-allergy-management-apis)
   - [Get User Allergies](#1-get-user-allergies)
   - [Add Allergy](#2-add-allergy)
   - [Remove Allergy](#3-remove-allergy)
   - [Clear All Allergies](#4-clear-all-allergies)
5. [Response Format](#response-format)
6. [Error Handling](#error-handling)
7. [Rate Limits](#rate-limits)
8. [Testing & Debugging](#testing--debugging)

---

## Overview

Main Service cung cấp API để phân tích công thức nấu ăn từ **văn bản** hoặc **hình ảnh**, trả về:
- 🍲 Thông tin món ăn
- 🛒 Danh sách nguyên liệu (shopping cart)
- 💡 Gợi ý nguyên liệu bổ sung
- ⚠️ Cảnh báo xung đột thực phẩm
- 🔍 Món ăn tương tự

---

## Base URL & Authentication

### Base URL

| Environment | URL |
|------------|-----|
| **Development** | `http://localhost:5000` |
| **Production** | `http://100.85.88.111:5000` |

### Authentication

Hiện tại API không yêu cầu authentication. Các endpoints là public.

> **Note:** Rate limiting sẽ được áp dụng trong tương lai (max 100 requests/hour per IP)

---

## AI Recipe Analysis APIs

### 1. Text Analysis

Phân tích món ăn từ mô tả văn bản của người dùng.

#### Endpoint

```
POST /api/v1/ai/recipe-analysis
```

#### Request Headers

```
Content-Type: application/json
```

#### Request Body

```json
{
  "user_input": "Tôi muốn nấu canh cua chua ăn kèm với cam"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_input` | string | ✅ Yes | Mô tả món ăn từ người dùng (1-500 ký tự) |

#### Response (Success - 200 OK)

```json
{
    "cart": {
        "items": [
            {
                "category": "seafood_&_fish_balls",
                "ingredient_id": "ingre01344",
                "name_vi": "Cua đồng",
                "note": null,
                "quantity": "500 g",
                "unit": "g"
            },
            {
                "category": "vegetables",
                "ingredient_id": "ingre01354",
                "name_vi": "Cà chua",
                "note": null,
                "quantity": "200 g",
                "unit": "g"
            },
            {
                "category": "vegetables",
                "ingredient_id": "ingre05383",
                "name_vi": "Rau thì là",
                "note": null,
                "quantity": "200 g",
                "unit": "g"
            },
            {
                "category": "vegetables",
                "ingredient_id": "ingre02768",
                "name_vi": "Hành tím",
                "note": null,
                "quantity": "300 g",
                "unit": "g"
            },
            {
                "category": "fresh_fruits",
                "ingredient_id": "ingre03644",
                "name_vi": "Mẻ chua",
                "note": null,
                "quantity": "15 ml",
                "unit": "ml"
            },
            {
                "category": "others",
                "ingredient_id": "ingre04687",
                "name_vi": "Nước mắm",
                "note": null,
                "quantity": "45 ml",
                "unit": "ml"
            },
            {
                "category": "snacks",
                "ingredient_id": "ingre02093",
                "name_vi": "Dầu màu điều",
                "note": null,
                "quantity": "5 ml",
                "unit": "ml"
            },
            {
                "category": "fresh_fruits",
                "ingredient_id": "ingre01972",
                "name_vi": "Dầu ăn",
                "note": null,
                "quantity": "30 ml",
                "unit": "ml"
            },
            {
                "category": "seasonings",
                "ingredient_id": "ingre03736",
                "name_vi": "Muối/ tiêu xay",
                "note": null,
                "quantity": "1 g",
                "unit": "g"
            },
            {
                "category": "fresh_fruits",
                "ingredient_id": "ingre01046",
                "name_vi": "cam",
                "note": null,
                "quantity": "tùy thích",
                "unit": "tùy thích"
            }
        ],
        "total_items": 10
    },
    "dish": {
        "name": "Canh cua chua",
        "prep_time": null,
        "servings": null
    },
    "error": null,
    "error_type": null,
    "guardrail": {
        "action": "allow",
        "request_id": "06946a7e-b5d0-4da9-b297-ce7ceca45ade",
        "timestamp": "2025-11-01T00:19:07.658929Z",
        "triggered": false,
        "violation_codes": [],
        "violation_count": 0
    },
    "insights": [
        "Theo khuyến cáo dân gian: cua ăn cùng cam/quýt dễ sinh khó chịu đường tiêu hóa."
    ],
    "message": null,
    "similar_dishes": [
        {
            "dish_id": "dish0109",
            "dish_name": "Canh cua chua",
            "match_count": 5,
            "match_ratio": 0.5555555555555556,
            "matched_roles": [
                "core_produce",
                "core_protein",
                "flavor_enhancer"
            ],
            "required_roles": [
                "core_produce",
                "core_protein"
            ],
            "role_coverage": 1.0,
            "weighted_score": 0.6470588235294118
        },
        {
            "dish_id": "dish0011",
            "dish_name": "Canh riêu cá",
            "match_count": 3,
            "match_ratio": 0.2727272727272727,
            "matched_roles": [
                "core_produce"
            ],
            "required_roles": [
                "core_produce",
                "core_protein"
            ],
            "role_coverage": 0.5,
            "weighted_score": 0.38095238095238093
        },
        {
            "dish_id": "dish0793",
            "dish_name": "Hàu nấu canh chua",
            "match_count": 3,
            "match_ratio": 0.375,
            "matched_roles": [
                "core_produce"
            ],
            "required_roles": [
                "core_produce",
                "core_protein"
            ],
            "role_coverage": 0.5,
            "weighted_score": 0.3333333333333333
        }
    ],
    "status": "success",
    "suggestions": [
        {
            "category": "others",
            "ingredient_id": "ingre04166",
            "name_vi": "mẻ chua",
            "note": null,
            "quantity": "tùy thích",
            "unit": "tùy thích"
        },
        {
            "category": "fresh_meat",
            "ingredient_id": "ingre06856",
            "name_vi": "trứng vịt lộn",
            "note": null,
            "quantity": "tùy thích",
            "unit": "tùy thích"
        },
        {
            "category": "vegetables",
            "ingredient_id": "ingre05239",
            "name_vi": "rau cần nước",
            "note": null,
            "quantity": "tùy thích",
            "unit": "tùy thích"
        },
        {
            "category": "vegetables",
            "ingredient_id": "ingre05410",
            "name_vi": "rau xà lách",
            "note": null,
            "quantity": "tùy thích",
            "unit": "tùy thích"
        },
        {
            "category": "grains_staples",
            "ingredient_id": "ingre00357",
            "name_vi": "bún tươi",
            "note": null,
            "quantity": "tùy thích",
            "unit": "tùy thích"
        }
    ],
    "warnings": [
        {
            "details": {
                "conflict_type": "ingredient_ingredient",
                "conflicting_item_1": [
                    "Cua đồng"
                ],
                "conflicting_item_2": [
                    "cam"
                ],
                "id": "cua-cam-quyt",
                "message": "Theo khuyến cáo dân gian: cua ăn cùng cam/quýt dễ sinh khó chịu đường tiêu hóa.",
                "replacement_suggestions": [
                    {
                        "category": "fresh_fruits",
                        "ingredient_id": "ingre00040",
                        "name_en": "Blueberries",
                        "name_vi": "blueberries:"
                    },
                    {
                        "category": "fresh_fruits",
                        "ingredient_id": "ingre00230",
                        "name_en": "Zucchini",
                        "name_vi": "bầu"
                    }
                ],
                "severity": "low",
                "sources": [
                    {
                        "name": "CDC Quảng Ninh",
                        "url": "https://www.quangninhcdc.vn/93-cap-thuc-pham-ky-nhau-va-cach-giai-doc/"
                    }
                ]
            },
            "message": "Theo khuyến cáo dân gian: cua ăn cùng cam/quýt dễ sinh khó chịu đường tiêu hóa.",
            "severity": "low",
            "source": "conflict"
        }
    ]
}
```

#### Response (Error - 400 Bad Request)

```json
{
  "success": false,
  "error": "user_input is required"
}
```

#### Response (Error - 500 Internal Server Error)

```json
{
  "success": false,
  "error": "AI Service error: Processing failed"
}
```

#### Response (Timeout - 504 Gateway Timeout)

```json
{
  "success": false,
  "error": "No response from AI Service within 30 seconds"
}
```

> **Note về Timeout:** Khi timeout xảy ra, AI Service có thể vẫn đang xử lý request. Response trả về muộn sẽ được consumer nhận nhưng không được trả về cho request đã timeout (để tránh race condition). Request tiếp theo sẽ không bị ảnh hưởng do correlation_id được reset.

---

### 2. Image Analysis (with S3 URL)

Phân tích món ăn từ hình ảnh đã được upload lên S3.

#### Endpoint

```
POST /api/v1/ai/image-analysis
```

#### Request Headers

```
Content-Type: application/json
```

#### Request Body

```json
{
  "s3_url": "abc123def456.jpg",
  "description": "Phở bò Việt Nam"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `s3_url` | string | ✅ Yes | S3 key hoặc full URL của hình ảnh |
| `description` | string | ❌ No | Mô tả bổ sung để AI hiểu context tốt hơn |

**Supported S3 URL formats:**
- S3 key only: `"image.jpg"`
- Full URL: `"https://bucket.s3.region.amazonaws.com/image.jpg"`
- S3 URI: `"s3://bucket/image.jpg"`

#### Response (Success - 200 OK)

Response format giống y hệt [Text Analysis](#1-text-analysis), bao gồm 10 fields cố định:

```json
{
  "success": true,
  "result": {
    "status": "success",
    "error": null,
    "error_type": null,
    "dish": {...},
    "cart": {...},
    "suggestions": [...],
    "similar_dishes": [...],
    "warnings": [...],
    "insights": [...],
    "guardrail": {...}
  }
}
```

#### Response (Error - Dish Not Found)

```json
{
  "success": true,
  "result": {
    "status": "error",
    "error": "Không tìm thấy tên món ăn trong hình ảnh",
    "error_type": "dish_not_found",
    "message": "Không nhận diện được món ăn trong hình ảnh. Vui lòng thử hình ảnh rõ hơn hoặc thêm mô tả.",
    "dish": {
      "name": ""
    },
    "cart": null,
    "suggestions": [],
    "similar_dishes": [],
    "warnings": [],
    "insights": [],
    "guardrail": null
  }
}
```

#### Response (Error - Image Download Failed)

```json
{
  "success": true,
  "result": {
    "status": "error",
    "error": "Không thể tải ảnh từ S3",
    "error_type": "image_download_failed",
    "message": "Không thể tải hình ảnh từ S3. Vui lòng kiểm tra lại URL hoặc quyền truy cập.",
    "dish": {
      "name": ""
    },
    "cart": null,
    "suggestions": [],
    "similar_dishes": [],
    "warnings": [],
    "insights": [],
    "guardrail": null
  }
}
```

#### Response (Error - Guardrail Blocked)

```json
{
  "success": true,
  "result": {
    "status": "guardrail_blocked",
    "error": "Hình ảnh vi phạm chính sách an toàn",
    "error_type": "guardrail_violation",
    "message": "Hình ảnh không phù hợp hoặc vi phạm chính sách an toàn. Vui lòng thử lại với hình ảnh khác.",
    "dish": {
      "name": ""
    },
    "cart": null,
    "suggestions": [],
    "similar_dishes": [],
    "warnings": [
      {
        "message": "INAPPROPRIATE_CONTENT detected",
        "severity": "error",
        "source": "guardrail"
      }
    ],
    "insights": [],
    "guardrail": {
      "input_blocked": true,
      "triggered": true,
      "action": "blocked"
    }
  }
}
```

---

### 3. Upload & Analyze Image

Upload hình ảnh lên S3 và phân tích món ăn trong một request duy nhất (Recommended).

#### Endpoint

```
POST /api/v1/ai/upload-and-analyze
```

#### Request Headers

```
Content-Type: multipart/form-data
```

#### Request Body (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | File | ✅ Yes | File hình ảnh (jpg, jpeg, png, webp, gif, bmp, tiff) |
| `description` | String | ❌ No | Mô tả bổ sung |

**File constraints:**
- **Max size:** 10MB
- **Allowed formats:** jpg, jpeg, png, webp, gif, bmp, tiff, tif
- **Recommended:** JPEG/PNG, < 5MB, resolution 800x600 - 1920x1080

#### Response (Success - 200 OK)

Giống [Image Analysis](#2-image-analysis-with-s3-url) nhưng có thêm field `s3_key`:

```json
{
  "success": true,
  "result": {
    "status": "success",
    "error": null,
    "error_type": null,
    "dish": {
      "name": "Phở bò",
      "prep_time": "45 phút",
      "servings": 4
    },
    "cart": {
      "total_items": 12,
      "items": [...]
    },
    "suggestions": [...],
    "similar_dishes": [...],
    "warnings": [],
    "insights": [],
    "guardrail": {
      "triggered": false
    },
    "s3_key": "abc123def456.jpg"
  }
}
```

**Extra field:**
- `s3_key` (string): S3 key của hình ảnh đã upload (để reference sau này)

#### Response (Error - Missing Image)

```json
{
  "success": false,
  "error": "Image file is required"
}
```

#### Response (Error - Invalid File Type)

```json
{
  "success": false,
  "error": "Invalid file type. Allowed: jpg, jpeg, png, webp, gif, bmp, tiff, tif"
}
```

#### Response (Error - File Too Large)

```json
{
  "success": false,
  "error": "File too large. Maximum size: 10MB"
}
```

---

### 4. Health Check

Kiểm tra trạng thái của AI Service.

#### Endpoint

```
GET /api/v1/ai/recipe-analysis/health
```

#### Response (Healthy - 200 OK)

```json
{
  "status": "healthy",
  "service": "AI Recipe Analysis",
  "timestamp": "2025-10-31T00:00:00Z",
  "ai_service_connected": true
}
```

#### Response (Unhealthy - 503 Service Unavailable)

```json
{
  "status": "unhealthy",
  "service": "AI Recipe Analysis",
  "timestamp": "2025-10-31T00:00:00Z",
  "ai_service_connected": false,
  "error": "Connection timeout"
}
```

---

## User Allergy Management APIs

### Overview

User có thể quản lý danh sách nguyên liệu dị ứng. Khi phân tích món ăn (text hoặc image), hệ thống sẽ **tự động lọc** các nguyên liệu dị ứng khỏi giỏ hàng và thêm warnings.

**Authentication required:** ✅ Yes (Bearer token)

---

### 1. Get User Allergies

Lấy danh sách dị ứng của user hiện tại.

#### Endpoint

```
GET /api/v1/user/allergies
```

#### Request Headers

```
Authorization: Bearer <access_token>
```

#### Response (200 OK)

```json
{
  "success": true,
  "allergies": [
    {
      "ingredient_id": "ing_123",
      "name_vi": "Đậu phộng",
      "name_en": "Peanut",
      "category": "nuts"
    },
    {
      "ingredient_id": "",
      "name_vi": "Hải sản",
      "name_en": "Seafood",
      "category": "protein"
    }
  ],
  "total": 2
}
```

---

### 2. Add Allergy

Thêm nguyên liệu dị ứng cho user.

#### Endpoint

```
POST /api/v1/user/allergies
```

#### Request Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

#### Request Body

```json
{
  "ingredient_id": "ing_123",
  "name_vi": "Đậu phộng",
  "name_en": "Peanut",
  "category": "nuts"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name_vi` | string | ✅ Yes | Tên tiếng Việt (1-100 ký tự) |
| `ingredient_id` | string | ❌ No | ID nguyên liệu (nếu có) |
| `name_en` | string | ❌ No | Tên tiếng Anh |
| `category` | string | ❌ No | Loại (nuts, seafood, dairy, etc.) |

#### Response (201 Created)

```json
{
  "success": true,
  "message": "Allergy added successfully",
  "allergy": {
    "ingredient_id": "ing_123",
    "name_vi": "Đậu phộng",
    "name_en": "Peanut",
    "category": "nuts"
  }
}
```

#### Response (400 Bad Request - Duplicate)

```json
{
  "success": false,
  "error": "Allergy \"Đậu phộng\" already exists"
}
```

---

### 3. Remove Allergy

Xóa nguyên liệu dị ứng của user.

#### Endpoint

```
DELETE /api/v1/user/allergies
```

#### Request Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

#### Request Body

```json
{
  "name_vi": "Đậu phộng"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name_vi` | string | ✅ Yes | Tên tiếng Việt của nguyên liệu cần xóa |

#### Response (200 OK)

```json
{
  "success": true,
  "message": "Allergy removed successfully"
}
```

#### Response (400 Bad Request - Not Found)

```json
{
  "success": false,
  "error": "Allergy not found or already removed"
}
```

---

### 4. Clear All Allergies

Xóa tất cả dị ứng của user.

#### Endpoint

```
POST /api/v1/user/allergies/clear
```

#### Request Headers

```
Authorization: Bearer <access_token>
```

#### Response (200 OK)

```json
{
  "success": true,
  "message": "All allergies cleared successfully"
}
```

---

### Allergy Filtering trong AI Analysis

Khi user **đã đăng nhập** và gọi AI analysis endpoints (text hoặc image), hệ thống sẽ:

1. ✅ **Tự động lọc** nguyên liệu dị ứng khỏi `cart.items`
2. ✅ **Thêm warnings** cho mỗi nguyên liệu bị lọc
3. ✅ **Cập nhật** `cart.total_items`

#### Example Response với Allergy Filtering

```json
{
  "status": "success",
  "dish": {
    "name": "Gỏi cuốn tôm"
  },
  "cart": {
    "total_items": 8,
    "items": [
      // Tôm đã bị loại bỏ vì user dị ứng hải sản
      {
        "name_vi": "Bánh tráng",
        "quantity": "200",
        "unit": "gram"
      }
      // ... other items
    ]
  },
  "warnings": [
    {
      "ingredient_id": "ing_456",
      "name_vi": "Tôm",
      "name_en": "Shrimp",
      "message": "⚠️ Bạn dị ứng với \"Tôm\" - đã loại bỏ khỏi giỏ hàng",
      "severity": "error",
      "source": "allergy_filter"
    }
  ]
}
```

---

## Response Format

### Common Response Structure

Tất cả AI analysis endpoints trả về **10 fields cố định** trong `result`:

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `status` | string | ✅ Yes | `"success"`, `"error"`, `"guardrail_blocked"` |
| `error` | string \| null | ✅ Yes | Error message (null nếu success) |
| `error_type` | string \| null | ✅ Yes | Error type code (null nếu success) |
| `dish` | object | ✅ Yes | Thông tin món ăn |
| `cart` | object \| null | ✅ Yes | Giỏ hàng nguyên liệu (null nếu error) |
| `suggestions` | array | ✅ Yes | Gợi ý nguyên liệu bổ sung |
| `similar_dishes` | array | ✅ Yes | Món ăn tương tự |
| `warnings` | array | ✅ Yes | Cảnh báo (xung đột, dị ứng...) |
| `insights` | array | ✅ Yes | Thông tin phân tích |
| `guardrail` | object \| null | ✅ Yes | Thông tin về content safety |

### Dish Object

```typescript
{
  name: string;           // Tên món ăn
  prep_time?: string;     // Thời gian chuẩn bị (vd: "45 phút")
  servings?: number;      // Số khẩu phần
}
```

### Cart Object

```typescript
{
  total_items: number;    // Tổng số nguyên liệu
  items: Array<{
    ingredient_id: string;      // ID nguyên liệu
    name_vi: string;            // Tên tiếng Việt
    name_en?: string;           // Tên tiếng Anh
    quantity: string;           // Số lượng
    unit: string;               // Đơn vị (gram, kg, ml, lít...)
    category: string;           // Loại (protein, vegetable, spice...)
    estimated_price?: number;   // Giá ước tính (VND)
  }>;
}
```

### Suggestion Object

```typescript
{
  ingredient_id: string;   // ID nguyên liệu
  name_vi: string;         // Tên tiếng Việt
  name_en?: string;        // Tên tiếng Anh
  score: number;           // Độ phù hợp (0-1)
  reason: string;          // Lý do gợi ý
}
```

### Similar Dish Object

```typescript
{
  dish_id?: string;        // ID món ăn (nếu có)
  name: string;            // Tên món
  match_count: number;     // Số nguyên liệu giống nhau
  common_ingredients: string[];  // Danh sách nguyên liệu chung
}
```

### Warning Object

```typescript
{
  message: string;         // Nội dung cảnh báo
  severity: string;        // "warning" | "error" | "info"
  source: string;          // Nguồn (conflict_detection, allergy, guardrail...)
}
```

### Guardrail Object

```typescript
{
  triggered: boolean;      // Có vi phạm không
  action?: string;         // "allow" | "blocked"
  input_blocked?: boolean; // Input có bị chặn không
}
```

---

## Error Handling

### Error Types

| Error Type | HTTP Code | Description | User Message (Suggested) |
|-----------|-----------|-------------|--------------------------|
| `validation_error` | 400 | Thiếu hoặc sai format request | "Vui lòng kiểm tra lại thông tin nhập vào" |
| `dish_not_found` | 400 | Không tìm thấy món ăn | "Không nhận diện được món ăn. Vui lòng thử lại!" |
| `recipe_not_found` | 404 | Không có công thức trong DB | "Hiện chưa có công thức cho món này" |
| `guardrail_violation` | 400 | Nội dung không phù hợp | "Nội dung không phù hợp. Vui lòng thử lại!" |
| `image_download_failed` | 400 | Không tải được ảnh từ S3 | "Không thể tải hình ảnh. Vui lòng thử lại!" |
| `processing_error` | 500 | Lỗi xử lý AI Service | "Có lỗi xảy ra. Vui lòng thử lại sau!" |
| `timeout` | 504 | Request timeout | "Xử lý quá lâu. Vui lòng thử lại!" |
| `unknown` | 500 | Lỗi không xác định | "Có lỗi xảy ra. Vui lòng thử lại!" |

### Timeout Behavior

Khi request timeout (30 giây):
- ✅ Client sẽ raise `TimeoutError` và không đợi response
- ✅ Callback queue sẽ được **xóa và tạo lại** để tránh nhận response muộn
- ✅ Request tiếp theo sẽ không bị ảnh hưởng bởi response của request đã timeout
- ⚠️ AI Service có thể vẫn đang xử lý - response muộn sẽ bị loại bỏ

**Recommendation:** Nếu gặp timeout thường xuyên:
1. Sử dụng hình ảnh nhỏ hơn (< 5MB)
2. Thêm mô tả text để AI xử lý nhanh hơn
3. Thử lại sau vài giây

---

## Rate Limits

### Current Limits

| Resource | Limit | Scope |
|----------|-------|-------|
| Text Analysis | Unlimited | Per IP |
| Image Upload | Unlimited | Per IP |
| Max File Size | 10MB | Per request |
| Request Timeout | 30 seconds | Per request |
| Concurrent Requests | 1 per connection | Per AI client instance |

> **Note:** Rate limiting sẽ được implement trong tương lai

> **Technical Note - RabbitMQ Timeout:** 
> - Client sử dụng blocking connection với correlation_id để track requests
> - Khi timeout, callback queue được xóa và tạo lại để loại bỏ response muộn
> - Mỗi request mới sẽ purge queue trước khi gửi để đảm bảo sạch sẽ

---

## Testing & Debugging

### Test URLs

```bash
# Health check
curl http://100.85.88.111:5000/api/v1/ai/recipe-analysis/health

# Text analysis
curl -X POST http://100.85.88.111:5000/api/v1/ai/recipe-analysis \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Tôi muốn nấu phở bò"}'

# Image analysis (với S3 URL)
curl -X POST http://100.85.88.111:5000/api/v1/ai/image-analysis \
  -H "Content-Type: application/json" \
  -d '{"s3_url": "test.jpg", "description": "Phở bò"}'

# Upload and analyze
curl -X POST http://100.85.88.111:5000/api/v1/ai/upload-and-analyze \
  -F "image=@/path/to/image.jpg" \
  -F "description=Phở bò Việt Nam"
```

---

## Support & Contact

### Issues & Bug Reports
- **Repository:** https://github.com/PTIT-KLTN/store_recommendation_backend
- **Issues:** https://github.com/PTIT-KLTN/store_recommendation_backend/issues

### API Status
- Check health endpoint: `GET /api/v1/ai/recipe-analysis/health`

### Response Time
- **Text Analysis:** 3-8 seconds
- **Image Analysis:** 10-25 seconds
- **Timeout:** 30 seconds (configurable via `AI_SERVICE_TIMEOUT` env var)

### Technical Architecture Notes

#### RabbitMQ Client Behavior
- **Connection:** Persistent BlockingConnection với heartbeat 600s
- **Reply Queue:** Exclusive, auto-delete queue (rotated after timeout)
- **Correlation ID:** UUID v4 để track từng request
- **Timeout Handling:** 
  - Client purge queue trước mỗi request mới
  - Khi timeout, xóa callback queue cũ và tạo queue mới
  - Response muộn sẽ không được nhận bởi request tiếp theo
- **Thread Safety:** Request serialization với `threading.Lock`

---

**Document Version:** 2.1  
**Last Updated:** November 1, 2025  
**Maintained by:** Backend Development Team
