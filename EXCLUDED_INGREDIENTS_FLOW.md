# Luồng Xử Lý Excluded Ingredients (Nguyên Liệu Dị Ứng Phát Hiện Từ AI)

## Tổng Quan
Khi AI Service phân tích công thức/hình ảnh, nó có thể phát hiện các nguyên liệu mà người dùng không nên ăn. Backend sẽ tự động thêm những nguyên liệu này vào danh sách dị ứng của user trong database.

## Cấu Trúc Dữ Liệu

### ExcludedIngredient từ AI Service
```python
{
    "name": str,              # Tên nguyên liệu (bắt buộc)
    "reason": str,            # Lý do loại trừ (tùy chọn)
    "ingredient_id": str,     # ID nguyên liệu (tùy chọn)
    "category": str           # Danh mục (tùy chọn)
}
```

### Allergy trong Database (User)
```python
{
    "ingredient_id": str,     # ID nguyên liệu
    "name_vi": str,           # Tên tiếng Việt
    "name_en": str,           # Tên tiếng Anh
    "category": str,          # Danh mục
    "reason": str,            # Lý do (ví dụ: "Detected from recipe analysis")
    "added_at": datetime,     # Thời gian thêm (tùy chọn)
    "source": str             # Nguồn: "manual" hoặc "ai_detection"
}
```

## Luồng Xử Lý Chi Tiết

### 1. Client gửi yêu cầu
```
POST /api/v1/ai/recipe-analysis
Content-Type: application/json
Authorization: Bearer <token>

{
    "user_input": "cơm gà vàng"
}
```

### 2. Backend gọi AI Service
- `ai_routes.py::analyze_recipe()` 
- Gửi request tới AI Service qua RabbitMQ
- Chờ response từ AI Service

### 3. AI Service trả về Response
```json
{
    "status": "success",
    "dish": { "name": "Cơm gà vàng" },
    "cart": { "items": [...] },
    "excluded_ingredients": [
        {
            "name": "Cà chua",
            "reason": "User không ăn rau đỏ"
        },
        {
            "name": "Dạo huyết",
            "reason": "Hồ sơ người dùng đánh dấu dị ứng"
        }
    ]
}
```

### 4. Backend Xử Lý (Luồng chính)

#### Bước 4.1: Kiểm tra Status Response
```python
# File: routes/ai_routes.py::analyze_recipe()
if status == 'success':
    # Tiến hành xử lý
```

#### Bước 4.2: Xử Lý Excluded Ingredients
```python
# File: routes/ai_routes.py::process_excluded_ingredients()
result = process_excluded_ingredients(result)
```

**Chi tiết xử lý:**
- Lấy user_email từ JWT token
- Lấy danh sách `excluded_ingredients` từ response
- Gọi service: `allergy_service.add_allergies_from_ai()`

#### Bước 4.3: Batch Add Allergies
```python
# File: services/allergy_service.py::add_allergies_from_ai()
for excluded_item in excluded_ingredients:
    ingredient_data = {
        'name_vi': excluded_item['name'],
        'name_en': excluded_item['name'],
        'ingredient_id': excluded_item.get('ingredient_id', ''),
        'category': excluded_item.get('category', ''),
        'reason': excluded_item['reason'],
        'source': 'ai_detection'
    }
    
    result = add_allergy(user_email, ingredient_data)
    
    if result['success']:
        added_ingredients.append(ingredient_data)
    elif 'already exists' in result['error']:
        skipped_ingredients.append(ingredient_data)
```

#### Bước 4.4: Add Allergy (với kiểm tra trùng)
```python
# File: services/allergy_service.py::add_allergy()
# Kiểm tra nếu nguyên liệu này đã tồn tại trong danh sách dị ứng
if already_exists:
    return { 'success': False, 'error': 'already exists' }

# Chuẩn bị allergy object
allergy_obj = {
    'ingredient_id': ...,
    'name_vi': ...,
    'name_en': ...,
    'category': ...,
    'reason': ...,
    'source': 'ai_detection'
}

# Thêm vào database
db.users.update_one(
    {'email': user_email},
    {'$push': {'allergies': allergy_obj}}
)
```

#### Bước 4.5: Filter Cart Items (Sau khi thêm allergies)
```python
# File: routes/ai_routes.py::apply_allergy_filter()
# Lọc các item trong cart dựa trên danh sách dị ứng mới
user_allergies = get_user_allergies(user_email)
filter_result = filter_cart_items(cart['items'], user_allergies)
# Các item dị ứng sẽ bị loại bỏ khỏi cart
```

#### Bước 4.6: Trả về Response
```json
{
    "status": "success",
    "message": null,
    "dish": { "name": "Cơm gà vàng" },
    "cart": {
        "items": [... filtered items ...],
        "total_items": 5
    },
    "warnings": [
        {
            "type": "excluded_ingredients_added",
            "message": "Đã thêm 2 nguyên liệu dị ứng mới vào hồ sơ của bạn",
            "added_ingredients": [
                { "name": "Cà chua", "reason": "User không ăn rau đỏ" },
                { "name": "Dạo huyết", "reason": "Hồ sơ người dùng đánh dấu dị ứng" }
            ],
            "severity": "info",
            "source": "ai_recipe_analysis"
        }
    ],
    "excluded_ingredients": [
        { "name": "Cà chua", "reason": "..." },
        { "name": "Dạo huyết", "reason": "..." }
    ]
}
```

## Endpoints Được Cập Nhật

### 1. POST /api/v1/ai/recipe-analysis
**Xử lý text input từ user**
- ✅ Tiếp nhận `excluded_ingredients` từ AI
- ✅ Tự động thêm vào allergies
- ✅ Filter cart items
- ✅ Trả về warnings

### 2. POST /api/v1/ai/image-analysis
**Xử lý S3 URL và description**
- ✅ Tiếp nhận `excluded_ingredients` từ AI
- ✅ Tự động thêm vào allergies
- ✅ Trả về warnings

### 3. POST /api/v1/ai/upload-and-analyze
**Upload hình ảnh + phân tích**
- ✅ Tiếp nhận `excluded_ingredients` từ AI
- ✅ Tự động thêm vào allergies
- ✅ Trả về warnings

## Xử Lý Error

### Khi process_excluded_ingredients gặp lỗi:
```json
{
    "warnings": [
        {
            "type": "excluded_ingredients_error",
            "message": "Lỗi hệ thống khi xử lý nguyên liệu dị ứng",
            "severity": "warning",
            "source": "ai_recipe_analysis"
        }
    ]
}
```

### Nếu một số nguyên liệu được bỏ qua:
```json
{
    "warnings": [
        {
            "type": "excluded_ingredients_added",
            "message": "Đã thêm 2 nguyên liệu dị ứng...",
            "added_ingredients": [...],
            "severity": "info"
        },
        {
            "type": "excluded_ingredients_skipped",
            "message": "1 nguyên liệu đã tồn tại hoặc không hợp lệ",
            "skipped_ingredients": [
                { "name": "Tôm", "reason": "Already in allergies list" }
            ],
            "severity": "info"
        }
    ]
}
```

## Database Schema (User Collection)

```json
{
    "email": "user@example.com",
    "allergies": [
        {
            "ingredient_id": "ing_123",
            "name_vi": "Cà chua",
            "name_en": "Tomato",
            "category": "Vegetable",
            "reason": "User không ăn rau đỏ",
            "source": "ai_detection",
            "added_at": "2024-11-01T10:30:00Z"
        },
        {
            "ingredient_id": "ing_456",
            "name_vi": "Tôm",
            "name_en": "Shrimp",
            "category": "Seafood",
            "reason": "Detected from recipe analysis",
            "source": "ai_detection",
            "added_at": "2024-11-01T10:31:00Z"
        }
    ]
}
```

## Lưu Ý Quan Trọng

1. **Kiểm tra Trùng Lặp**: Service sẽ tự động kiểm tra nếu nguyên liệu đã tồn tại trong danh sách dị ứng
2. **Không Ảnh Hưởng Tới Request**: Nếu process_excluded_ingredients gặp lỗi, request vẫn trả về success nhưng có warning
3. **Source Tracking**: Mỗi allergy có field `source` để phân biệt:
   - `"manual"`: Được thêm bởi người dùng
   - `"ai_detection"`: Phát hiện từ AI Service
4. **Async Processing**: Hiện tại xử lý synchronously, có thể chuyển sang async tasks sau nếu cần

## Testing

### Test Case 1: Thêm Excluded Ingredients Mới
```bash
curl -X POST http://localhost:5000/api/v1/ai/recipe-analysis \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"user_input": "cơm gà vàng có tôm"}'
```

**Kỳ vọng:**
- Excluded ingredients được thêm vào allergies
- Response chứa warnings về allergies được thêm
- Cart items được filter loại bỏ các nguyên liệu dị ứng

### Test Case 2: Excluded Ingredients Đã Tồn Tại
- Nếu nguyên liệu đã trong danh sách dị ứng
- Sẽ được skip (không thêm lại)
- Response chứa `excluded_ingredients_skipped` warning

### Test Case 3: User Không Có Token
- Process excluded ingredients sẽ skip
- Response vẫn trả về success (không lỗi)

