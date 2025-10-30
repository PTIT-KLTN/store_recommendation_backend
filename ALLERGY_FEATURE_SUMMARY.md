# 🎉 Feature Mới: Quản Lý Dị Ứng (Allergy Management)

## Tổng Quan

User giờ đây có thể **quản lý danh sách nguyên liệu dị ứng**. Khi phân tích món ăn (text hoặc image), hệ thống sẽ **tự động lọc** các nguyên liệu dị ứng khỏi giỏ hàng.

---

## 🆕 API Endpoints Mới

### 1. **GET** `/api/v1/user/allergies`
Lấy danh sách dị ứng của user.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "allergies": [
    {
      "ingredient_id": "ing_123",
      "name_vi": "Đậu phộng",
      "name_en": "Peanut",
      "category": "nuts"
    }
  ],
  "total": 1
}
```

---

### 2. **POST** `/api/v1/user/allergies`
Thêm nguyên liệu dị ứng.

**Headers:** 
- `Authorization: Bearer <token>`
- `Content-Type: application/json`

**Body:**
```json
{
  "name_vi": "Đậu phộng",
  "name_en": "Peanut",  // optional
  "category": "nuts"     // optional
}
```

**Response:**
```json
{
  "success": true,
  "message": "Allergy added successfully",
  "allergy": {...}
}
```

---

### 3. **DELETE** `/api/v1/user/allergies`
Xóa nguyên liệu dị ứng.

**Headers:**
- `Authorization: Bearer <token>`
- `Content-Type: application/json`

**Body:**
```json
{
  "name_vi": "Đậu phộng"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Allergy removed successfully"
}
```

---

### 4. **POST** `/api/v1/user/allergies/clear`
Xóa tất cả dị ứng.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "All allergies cleared successfully"
}
```

---

## 🔄 Thay Đổi trong AI Analysis APIs

### Automatic Filtering

Khi user **đã login** (có Bearer token) và gọi các AI analysis endpoints:
- `POST /api/v1/ai/recipe-analysis` (text)
- `POST /api/v1/ai/upload-and-analyze` (image)
- `POST /api/v1/ai/image-analysis` (with S3 URL)

Hệ thống sẽ **tự động**:

1. ✅ **Lọc nguyên liệu dị ứng** khỏi `cart.items`
2. ✅ **Thêm warnings** cho mỗi nguyên liệu bị lọc
3. ✅ **Cập nhật** `cart.total_items`

### Example Response

**Trước (không có allergy filtering):**
```json
{
  "status": "success",
  "cart": {
    "total_items": 10,
    "items": [
      {"name_vi": "Tôm", ...},
      {"name_vi": "Bánh tráng", ...},
      ...
    ]
  },
  "warnings": []
}
```

**Sau (user dị ứng hải sản):**
```json
{
  "status": "success",
  "cart": {
    "total_items": 9,  // Giảm 1
    "items": [
      // Tôm đã bị loại bỏ
      {"name_vi": "Bánh tráng", ...},
      ...
    ]
  },
  "warnings": [
    {
      "ingredient_id": "ing_456",
      "name_vi": "Tôm",
      "message": "⚠️ Bạn dị ứng với \"Tôm\" - đã loại bỏ khỏi giỏ hàng",
      "severity": "error",
      "source": "allergy_filter"
    }
  ]
}
```

---

## 📝 Frontend Implementation Guide

### 1. Allergy Manager Component (React)

```jsx
import { useState, useEffect } from 'react';

function AllergyManager() {
  const [allergies, setAllergies] = useState([]);
  const [newAllergy, setNewAllergy] = useState('');
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    fetchAllergies();
  }, []);

  const fetchAllergies = async () => {
    const res = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();
    if (data.success) setAllergies(data.allergies);
  };

  const addAllergy = async (e) => {
    e.preventDefault();
    const res = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name_vi: newAllergy })
    });
    const data = await res.json();
    if (data.success) {
      setAllergies([...allergies, data.allergy]);
      setNewAllergy('');
    }
  };

  const removeAllergy = async (name) => {
    const res = await fetch('http://100.85.88.111:5000/api/v1/user/allergies', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name_vi: name })
    });
    const data = await res.json();
    if (data.success) {
      setAllergies(allergies.filter(a => a.name_vi !== name));
    }
  };

  return (
    <div>
      <h2>Quản lý dị ứng ({allergies.length})</h2>
      
      <form onSubmit={addAllergy}>
        <input
          value={newAllergy}
          onChange={e => setNewAllergy(e.target.value)}
          placeholder="Nhập tên nguyên liệu..."
        />
        <button>Thêm</button>
      </form>

      <ul>
        {allergies.map((a, i) => (
          <li key={i}>
            {a.name_vi}
            <button onClick={() => removeAllergy(a.name_vi)}>Xóa</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### 2. Display Allergy Warnings trong Recipe Result

```jsx
function RecipeResult({ result }) {
  const allergyWarnings = result.warnings.filter(
    w => w.source === 'allergy_filter'
  );

  return (
    <div>
      <h2>{result.dish.name}</h2>
      
      {/* Allergy warnings */}
      {allergyWarnings.length > 0 && (
        <div className="allergy-warnings">
          <h3>⚠️ Cảnh báo dị ứng:</h3>
          {allergyWarnings.map((warning, idx) => (
            <div key={idx} className="warning-item">
              {warning.message}
            </div>
          ))}
        </div>
      )}

      {/* Cart items */}
      <h3>Nguyên liệu ({result.cart.total_items}):</h3>
      <ul>
        {result.cart.items.map((item, idx) => (
          <li key={idx}>
            {item.name_vi}: {item.quantity} {item.unit}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## 🧪 Testing

### Postman / curl Examples

**1. Thêm dị ứng:**
```bash
curl -X POST http://100.85.88.111:5000/api/v1/user/allergies \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name_vi": "Đậu phộng"}'
```

**2. Lấy danh sách:**
```bash
curl http://100.85.88.111:5000/api/v1/user/allergies \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**3. Test AI analysis (text):**
```bash
curl -X POST http://100.85.88.111:5000/api/v1/ai/recipe-analysis \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Tôi muốn ăn gỏi cuốn tôm"}'
```

Response sẽ tự động lọc "tôm" nếu user dị ứng hải sản.

---

## 📋 Database Schema

### User Model - Field mới

```python
class User:
    ...
    allergies: List[Dict] = []
    # Example:
    # [
    #   {
    #     "ingredient_id": "ing_123",
    #     "name_vi": "Đậu phộng",
    #     "name_en": "Peanut",
    #     "category": "nuts"
    #   }
    # ]
```

---

## ✅ Checklist cho Frontend Team

- [ ] Tạo Allergy Manager component
- [ ] Integrate vào User Profile/Settings page
- [ ] Display allergy warnings trong Recipe Result
- [ ] Highlight filtered ingredients (optional)
- [ ] Add allergy badge/icon next to user avatar (optional)
- [ ] Test với user đã login
- [ ] Test với user chưa login (allergies không áp dụng)

---

## 📚 Full Documentation

Xem **API_DOCUMENTATION.md** section "User Allergy Management APIs" để biết chi tiết đầy đủ.

---

**Questions?** Contact backend team! 🚀
