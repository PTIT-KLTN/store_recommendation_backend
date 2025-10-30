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
7. [Frontend Integration Examples](#frontend-integration-examples)
8. [Rate Limits & Best Practices](#rate-limits--best-practices)

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
  "user_input": "Tôi muốn nấu phở bò"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_input` | string | ✅ Yes | Mô tả món ăn từ người dùng (1-500 ký tự) |

#### Response (Success - 200 OK)

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
      "items": [
        {
          "ingredient_id": "ing_001",
          "name_vi": "Bánh phở",
          "name_en": "Rice noodles",
          "quantity": "500",
          "unit": "gram",
          "category": "grains",
          "estimated_price": 15000
        },
        {
          "ingredient_id": "ing_002",
          "name_vi": "Thịt bò",
          "name_en": "Beef",
          "quantity": "300",
          "unit": "gram",
          "category": "protein",
          "estimated_price": 120000
        }
      ]
    },
    "suggestions": [
      {
        "ingredient_id": "ing_050",
        "name_vi": "Rau thơm",
        "name_en": "Herbs",
        "score": 0.85,
        "reason": "Thường ăn kèm với phở"
      }
    ],
    "similar_dishes": [
      {
        "dish_id": "dish_123",
        "name": "Bún bò Huế",
        "match_count": 8,
        "common_ingredients": ["thịt bò", "nước dùng"]
      }
    ],
    "warnings": [
      {
        "message": "Không nên kết hợp bò với sữa",
        "severity": "warning",
        "source": "conflict_detection"
      }
    ],
    "insights": [
      {
        "type": "nutrition",
        "message": "Món ăn giàu protein và carbohydrate"
      }
    ],
    "guardrail": {
      "triggered": false,
      "action": "allow"
    }
  }
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
  "error": "AI Service request timeout"
}
```

#### Example Usage (JavaScript)

```javascript
const analyzeRecipe = async (userInput) => {
  try {
    const response = await fetch('http://100.85.88.111:5000/api/v1/ai/recipe-analysis', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_input: userInput
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      const result = data.result;
      console.log('Món ăn:', result.dish.name);
      console.log('Số nguyên liệu:', result.cart.total_items);
      
      // Display cart items
      result.cart.items.forEach(item => {
        console.log(`- ${item.name_vi}: ${item.quantity} ${item.unit}`);
      });
    } else {
      console.error('Error:', data.error);
    }
  } catch (error) {
    console.error('Network error:', error);
  }
};

// Usage
analyzeRecipe('Tôi muốn nấu phở bò');
```

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

#### Example Usage (JavaScript)

```javascript
const analyzeImageByUrl = async (s3Url, description = '') => {
  try {
    const response = await fetch('http://100.85.88.111:5000/api/v1/ai/image-analysis', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        s3_url: s3Url,
        description: description
      })
    });
    
    const data = await response.json();
    
    if (data.success && data.result.status === 'success') {
      const result = data.result;
      return {
        success: true,
        dish: result.dish,
        cart: result.cart,
        suggestions: result.suggestions
      };
    } else {
      return {
        success: false,
        error: data.result?.error || data.error
      };
    }
  } catch (error) {
    console.error('Network error:', error);
    return { success: false, error: error.message };
  }
};

// Usage
analyzeImageByUrl('abc123.jpg', 'Phở bò Việt Nam');
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

#### Example Usage (JavaScript with FormData)

```javascript
const uploadAndAnalyze = async (imageFile, description = '') => {
  try {
    const formData = new FormData();
    formData.append('image', imageFile);
    
    if (description) {
      formData.append('description', description);
    }
    
    const response = await fetch('http://100.85.88.111:5000/api/v1/ai/upload-and-analyze', {
      method: 'POST',
      body: formData
      // Don't set Content-Type header - browser will set it automatically with boundary
    });
    
    const data = await response.json();
    
    if (data.success && data.result.status === 'success') {
      const result = data.result;
      return {
        success: true,
        s3Key: result.s3_key,
        dish: result.dish,
        cart: result.cart,
        suggestions: result.suggestions,
        warnings: result.warnings
      };
    } else {
      return {
        success: false,
        error: data.result?.error || data.error,
        errorType: data.result?.error_type
      };
    }
  } catch (error) {
    console.error('Upload error:', error);
    return { success: false, error: error.message };
  }
};

// Usage with file input
const handleFileUpload = async (event) => {
  const file = event.target.files[0];
  
  if (!file) return;
  
  // Validate file size
  if (file.size > 10 * 1024 * 1024) {
    alert('File quá lớn! Tối đa 10MB');
    return;
  }
  
  // Validate file type
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
  if (!allowedTypes.includes(file.type)) {
    alert('File không hợp lệ! Chỉ chấp nhận JPG, PNG, WEBP, GIF');
    return;
  }
  
  // Upload and analyze
  const result = await uploadAndAnalyze(file, 'Món ăn Việt Nam');
  
  if (result.success) {
    console.log('Món ăn:', result.dish.name);
    console.log('S3 Key:', result.s3Key);
    console.log('Nguyên liệu:', result.cart.items);
  } else {
    console.error('Error:', result.error);
    
    if (result.errorType === 'dish_not_found') {
      alert('Không nhận diện được món ăn. Vui lòng thử ảnh rõ hơn!');
    } else if (result.errorType === 'guardrail_violation') {
      alert('Hình ảnh không phù hợp!');
    }
  }
};
```

#### Example Usage (React Component)

```jsx
import React, { useState } from 'react';

function ImageUploadAnalyzer() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate
    if (file.size > 10 * 1024 * 1024) {
      setError('File quá lớn! Tối đa 10MB');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('description', 'Món ăn Việt Nam');

      const response = await fetch(
        'http://100.85.88.111:5000/api/v1/ai/upload-and-analyze',
        {
          method: 'POST',
          body: formData
        }
      );

      const data = await response.json();

      if (data.success && data.result.status === 'success') {
        setResult(data.result);
      } else {
        setError(data.result?.error || 'Có lỗi xảy ra');
      }
    } catch (err) {
      setError('Lỗi kết nối: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleFileChange}
        disabled={loading}
      />

      {loading && <p>Đang phân tích hình ảnh...</p>}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <h2>{result.dish.name}</h2>
          <p>Thời gian: {result.dish.prep_time}</p>
          <p>Khẩu phần: {result.dish.servings} người</p>

          <h3>Nguyên liệu ({result.cart.total_items}):</h3>
          <ul>
            {result.cart.items.map((item, idx) => (
              <li key={idx}>
                {item.name_vi}: {item.quantity} {item.unit}
              </li>
            ))}
          </ul>

          {result.warnings.length > 0 && (
            <div className="warnings">
              <h3>⚠️ Cảnh báo:</h3>
              {result.warnings.map((w, idx) => (
                <p key={idx}>{w.message}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ImageUploadAnalyzer;
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

#### Example Usage (JavaScript)

```javascript
const checkHealth = async () => {
  try {
    const response = await fetch('http://100.85.88.111:5000/api/v1/ai/recipe-analysis/health');
    const data = await response.json();
    
    if (data.status === 'healthy') {
      console.log('✅ Service is healthy');
    } else {
      console.warn('⚠️ Service is unhealthy:', data.error);
    }
    
    return data;
  } catch (error) {
    console.error('❌ Health check failed:', error);
    return { status: 'error', error: error.message };
  }
};

// Check health every 30 seconds
setInterval(checkHealth, 30000);
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

#### Example (JavaScript)

```javascript
const getUserAllergies = async () => {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const data = await response.json();
  
  if (data.success) {
    console.log('User allergies:', data.allergies);
    return data.allergies;
  }
};
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

#### Example (JavaScript)

```javascript
const addAllergy = async (allergyData) => {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(allergyData)
  });
  
  const data = await response.json();
  
  if (data.success) {
    console.log('Allergy added:', data.allergy);
  } else {
    console.error('Error:', data.error);
  }
  
  return data;
};

// Usage
await addAllergy({
  name_vi: 'Đậu phộng',
  name_en: 'Peanut',
  category: 'nuts'
});
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

#### Example (JavaScript)

```javascript
const removeAllergy = async (allergyName) => {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name_vi: allergyName
    })
  });
  
  const data = await response.json();
  
  if (data.success) {
    console.log('Allergy removed');
  } else {
    console.error('Error:', data.error);
  }
  
  return data;
};

// Usage
await removeAllergy('Đậu phộng');
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

#### Example (JavaScript)

```javascript
const clearAllAllergies = async () => {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies/clear', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const data = await response.json();
  
  if (data.success) {
    console.log('All allergies cleared');
  }
  
  return data;
};
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

#### Complete React Example với Allergy Management

```jsx
import React, { useState, useEffect } from 'react';

function AllergyManager() {
  const [allergies, setAllergies] = useState([]);
  const [newAllergy, setNewAllergy] = useState('');
  const token = localStorage.getItem('access_token');

  // Fetch allergies on mount
  useEffect(() => {
    fetchAllergies();
  }, []);

  const fetchAllergies = async () => {
    const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    if (data.success) {
      setAllergies(data.allergies);
    }
  };

  const handleAddAllergy = async (e) => {
    e.preventDefault();
    
    const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name_vi: newAllergy
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      setAllergies([...allergies, data.allergy]);
      setNewAllergy('');
    } else {
      alert(data.error);
    }
  };

  const handleRemoveAllergy = async (allergyName) => {
    const response = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name_vi: allergyName
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      setAllergies(allergies.filter(a => a.name_vi !== allergyName));
    }
  };

  return (
    <div className="allergy-manager">
      <h2>Quản lý dị ứng</h2>
      
      {/* Add allergy form */}
      <form onSubmit={handleAddAllergy}>
        <input
          type="text"
          value={newAllergy}
          onChange={(e) => setNewAllergy(e.target.value)}
          placeholder="Nhập tên nguyên liệu (vd: Đậu phộng)"
          required
        />
        <button type="submit">Thêm dị ứng</button>
      </form>

      {/* Allergy list */}
      <div className="allergies-list">
        <h3>Danh sách dị ứng ({allergies.length}):</h3>
        {allergies.length === 0 ? (
          <p>Chưa có dị ứng nào</p>
        ) : (
          <ul>
            {allergies.map((allergy, idx) => (
              <li key={idx}>
                <span>{allergy.name_vi}</span>
                {allergy.name_en && <span> ({allergy.name_en})</span>}
                <button onClick={() => handleRemoveAllergy(allergy.name_vi)}>
                  Xóa
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default AllergyManager;
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

### Error Handling Best Practices

```javascript
const handleApiError = (data, httpStatus) => {
  // Check outer success flag
  if (!data.success) {
    // Network or server error
    console.error('API Error:', data.error);
    return {
      userMessage: 'Không thể kết nối tới server. Vui lòng thử lại!',
      canRetry: true
    };
  }
  
  // Check inner result status
  const result = data.result;
  
  if (result.status === 'success') {
    return { success: true, data: result };
  }
  
  // Handle specific error types
  switch (result.error_type) {
    case 'dish_not_found':
      return {
        userMessage: 'Không nhận diện được món ăn trong hình ảnh. Vui lòng thử ảnh rõ hơn hoặc thêm mô tả!',
        canRetry: true,
        suggestion: 'Try uploading a clearer image or add text description'
      };
      
    case 'recipe_not_found':
      return {
        userMessage: `Hiện chưa có công thức cho món "${result.dish.name}". Bạn có muốn thử món khác không?`,
        canRetry: false
      };
      
    case 'guardrail_violation':
      return {
        userMessage: 'Hình ảnh không phù hợp hoặc vi phạm chính sách. Vui lòng thử ảnh khác!',
        canRetry: true,
        shouldBlock: true
      };
      
    case 'image_download_failed':
      return {
        userMessage: 'Không thể tải hình ảnh. Vui lòng thử lại!',
        canRetry: true
      };
      
    case 'timeout':
      return {
        userMessage: 'Xử lý hình ảnh đang mất nhiều thời gian. Vui lòng thử lại hoặc dùng ảnh nhỏ hơn!',
        canRetry: true
      };
      
    default:
      return {
        userMessage: result.message || 'Có lỗi xảy ra. Vui lòng thử lại sau!',
        canRetry: true
      };
  }
};

// Usage
const result = await uploadAndAnalyze(file);
const errorInfo = handleApiError(result, response.status);

if (errorInfo.success) {
  // Display success UI
  displayRecipeResult(errorInfo.data);
} else {
  // Display error UI
  showErrorMessage(errorInfo.userMessage);
  
  if (errorInfo.canRetry) {
    showRetryButton();
  }
  
  if (errorInfo.shouldBlock) {
    // Block user temporarily or log incident
    logContentViolation(userId);
  }
}
```

---

## Frontend Integration Examples

### Complete React Hook Example

```jsx
import { useState, useCallback } from 'react';

const API_BASE_URL = 'http://100.85.88.111:5000';

export function useRecipeAnalysis() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Text analysis
  const analyzeText = useCallback(async (userInput) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/ai/recipe-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_input: userInput })
      });

      const data = await response.json();

      if (data.success && data.result.status === 'success') {
        setResult(data.result);
        return { success: true, data: data.result };
      } else {
        const errorMsg = data.result?.error || data.error || 'Unknown error';
        setError(errorMsg);
        return { success: false, error: errorMsg };
      }
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  }, []);

  // Image analysis (upload)
  const analyzeImage = useCallback(async (imageFile, description = '') => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // Validate file
      if (imageFile.size > 10 * 1024 * 1024) {
        throw new Error('File quá lớn! Tối đa 10MB');
      }

      const formData = new FormData();
      formData.append('image', imageFile);
      if (description) {
        formData.append('description', description);
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/ai/upload-and-analyze`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (data.success && data.result.status === 'success') {
        setResult(data.result);
        return { success: true, data: data.result };
      } else {
        const errorMsg = data.result?.error || data.error || 'Unknown error';
        setError(errorMsg);
        return { 
          success: false, 
          error: errorMsg,
          errorType: data.result?.error_type 
        };
      }
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    result,
    error,
    analyzeText,
    analyzeImage
  };
}

// Usage in component
function RecipeAnalyzer() {
  const { loading, result, error, analyzeText, analyzeImage } = useRecipeAnalysis();
  const [inputText, setInputText] = useState('');

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    await analyzeText(inputText);
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (file) {
      await analyzeImage(file, 'Món ăn Việt Nam');
    }
  };

  return (
    <div>
      {/* Text Input */}
      <form onSubmit={handleTextSubmit}>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Nhập tên món ăn..."
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          Phân tích
        </button>
      </form>

      {/* Image Upload */}
      <input
        type="file"
        accept="image/*"
        onChange={handleImageUpload}
        disabled={loading}
      />

      {/* Loading State */}
      {loading && <p>Đang phân tích...</p>}

      {/* Error State */}
      {error && <div className="error">{error}</div>}

      {/* Success State */}
      {result && (
        <div className="result">
          <h2>{result.dish.name}</h2>
          <p>Thời gian: {result.dish.prep_time}</p>
          
          <h3>Nguyên liệu ({result.cart.total_items}):</h3>
          <ul>
            {result.cart.items.map((item, idx) => (
              <li key={idx}>
                {item.name_vi}: {item.quantity} {item.unit}
                {item.estimated_price && ` - ${item.estimated_price.toLocaleString()} VND`}
              </li>
            ))}
          </ul>

          {result.suggestions.length > 0 && (
            <div>
              <h3>Gợi ý thêm:</h3>
              {result.suggestions.map((s, idx) => (
                <p key={idx}>{s.name_vi} - {s.reason}</p>
              ))}
            </div>
          )}

          {result.warnings.length > 0 && (
            <div className="warnings">
              <h3>⚠️ Cảnh báo:</h3>
              {result.warnings.map((w, idx) => (
                <p key={idx}>{w.message}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## Rate Limits & Best Practices

### Current Limits

| Resource | Limit | Scope |
|----------|-------|-------|
| Text Analysis | Unlimited | Per IP |
| Image Upload | Unlimited | Per IP |
| Max File Size | 10MB | Per request |
| Request Timeout | 30 seconds | Per request |

> **Note:** Rate limiting sẽ được implement trong tương lai

### Best Practices

#### 1. **Validate trước khi gửi request**

```javascript
const validateImageFile = (file) => {
  const maxSize = 10 * 1024 * 1024; // 10MB
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
  
  if (!file) {
    return { valid: false, error: 'Chưa chọn file' };
  }
  
  if (file.size > maxSize) {
    return { valid: false, error: 'File quá lớn (max 10MB)' };
  }
  
  if (!allowedTypes.includes(file.type)) {
    return { valid: false, error: 'Định dạng không hợp lệ' };
  }
  
  return { valid: true };
};
```

#### 2. **Implement timeout và retry logic**

```javascript
const fetchWithTimeout = async (url, options, timeout = 30000) => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    if (error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  }
};

const retryRequest = async (requestFn, maxRetries = 3) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      
      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
    }
  }
};
```

#### 3. **Optimize hình ảnh trước khi upload**

```javascript
const compressImage = async (file, maxWidth = 1920, maxHeight = 1080, quality = 0.8) => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;
        
        // Calculate new dimensions
        if (width > maxWidth || height > maxHeight) {
          const ratio = Math.min(maxWidth / width, maxHeight / height);
          width *= ratio;
          height *= ratio;
        }
        
        canvas.width = width;
        canvas.height = height;
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        
        canvas.toBlob((blob) => {
          resolve(new File([blob], file.name, { type: 'image/jpeg' }));
        }, 'image/jpeg', quality);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
};

// Usage
const handleImageUpload = async (file) => {
  // Compress if too large
  if (file.size > 5 * 1024 * 1024) {
    file = await compressImage(file);
  }
  
  await analyzeImage(file);
};
```

#### 4. **Cache kết quả để giảm API calls**

```javascript
const recipeCache = new Map();

const analyzeWithCache = async (key, analysisFn) => {
  // Check cache
  if (recipeCache.has(key)) {
    console.log('Cache hit:', key);
    return recipeCache.get(key);
  }
  
  // Call API
  const result = await analysisFn();
  
  // Store in cache (expires after 1 hour)
  recipeCache.set(key, result);
  setTimeout(() => recipeCache.delete(key), 60 * 60 * 1000);
  
  return result;
};

// Usage
const result = await analyzeWithCache(
  `text:${userInput}`,
  () => analyzeText(userInput)
);
```

#### 5. **Hiển thị progress cho image upload**

```javascript
const uploadWithProgress = async (file, onProgress) => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percentage = (e.loaded / e.total) * 100;
        onProgress(percentage);
      }
    });
    
    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error('Upload failed'));
      }
    });
    
    xhr.addEventListener('error', () => reject(new Error('Network error')));
    
    const formData = new FormData();
    formData.append('image', file);
    
    xhr.open('POST', `${API_BASE_URL}/api/v1/ai/upload-and-analyze`);
    xhr.send(formData);
  });
};

// Usage
await uploadWithProgress(file, (progress) => {
  console.log(`Upload progress: ${progress}%`);
  setUploadProgress(progress);
});
```

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

### Browser Console Testing

```javascript
// Test text analysis
fetch('http://100.85.88.111:5000/api/v1/ai/recipe-analysis', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user_input: 'Tôi muốn nấu phở bò' })
})
.then(r => r.json())
.then(console.log);
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

---

**Document Version:** 2.0  
**Last Updated:** October 31, 2025  
**Maintained by:** Backend Development Team
