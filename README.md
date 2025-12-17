# 🛒 Store Recommendation Backend

Hệ thống backend API cho ứng dụng gợi ý cửa hàng tối ưu dựa trên giỏ hàng người dùng. Sử dụng AI/ML để tìm kiếm sản phẩm và thuật toán TOPSIS để đưa ra gợi ý cửa hàng phù hợp nhất.

## 📋 Mục lục

- [Tính năng chính](#-tính-năng-chính)
- [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
- [Cài đặt](#-cài-đặt)
- [Cấu hình](#-cấu-hình)
- [Chạy ứng dụng](#-chạy-ứng-dụng)
- [API Endpoints](#-api-endpoints)
- [Cấu trúc dự án](#-cấu-trúc-dự-án)
- [Thuật toán](#-thuật-toán)

## ✨ Tính năng chính

### 🎯 Gợi ý cửa hàng thông minh
- Phân tích giỏ hàng người dùng (nguyên liệu + món ăn)
- Tìm kiếm sản phẩm phù hợp từ nhiều cửa hàng
- Sử dụng thuật toán **TOPSIS** để đánh giá và xếp hạng cửa hàng dựa trên:
  - Giá cả tổng thể
  - Khoảng cách địa lý
  - Tỷ lệ sản phẩm có sẵn
  - Đánh giá cửa hàng
  - Độ quen thuộc (cửa hàng yêu thích)

### 🔍 Tìm kiếm sản phẩm AI-powered
- **FAISS Vector Search**: Tìm kiếm semantic với embeddings tiếng Việt
- **Fuzzy String Matching**: Tìm kiếm gần đúng cho queries ngắn
- **Hybrid Strategy**: Kết hợp cả 2 phương pháp để đạt độ chính xác cao nhất
- Model: `keepitreal/vietnamese-sbert`

### 👤 Quản lý người dùng
- Đăng ký/đăng nhập với JWT authentication
- Đăng nhập Google OAuth2
- Quản lý giỏ hàng cá nhân
- Lưu cửa hàng yêu thích
- Quản lý dị ứng thực phẩm

### 🍽️ Quản lý món ăn & nguyên liệu
- Thư viện món ăn với công thức chi tiết
- Database nguyên liệu đầy đủ thông tin dinh dưỡng
- Phân loại theo danh mục
- Hỗ trợ tìm kiếm và gợi ý

### 🏪 Quản lý cửa hàng & sản phẩm
- Crawling dữ liệu sản phẩm từ các siêu thị
- Cập nhật giá và khuyến mãi
- Tích hợp bản đồ (OpenRouteService API)
- Tìm cửa hàng gần nhất

### 🤖 AI Features
- Chat AI hỗ trợ người dùng
- Gợi ý món ăn thông minh
- Phân tích preferences

### 📊 Admin Dashboard
- Quản lý người dùng
- Quản lý món ăn & nguyên liệu
- Quản lý cửa hàng & sản phẩm
- Xem báo cáo và thống kê
- Quản lý crawling jobs

## 🔧 Công nghệ sử dụng

### Framework & Core
- **Flask 3.0.0** - Framework web chính để xây dựng API backend
- **pymongo 4.6.1** - Thư viện kết nối và thao tác với MongoDB
- **redis 5.0.1** - Cache dữ liệu và message queue

### Xác thực & Bảo mật
- **Flask-JWT-Extended 4.6.0** - Quản lý token JWT cho xác thực
- **Flask-Bcrypt 1.0.1** - Mã hóa mật khẩu
- **google-auth-oauthlib 1.2.2** - Đăng nhập Google OAuth2

### Xử lý bất đồng bộ
- **celery 5.3.4** - Xử lý tác vụ nền (crawling, batch processing)
- **kombu 5.5.4** - Message broker cho Celery

### API & Network
- **Flask-Cors 4.0.0** - Xử lý CORS
- **requests 2.32.4** - HTTP client cho API calls

### Machine Learning & AI
- **torch 2.7.1** - Deep learning framework
- **transformers 4.54.1** - Hugging Face transformers
- **sentence-transformers** - Tạo embeddings từ văn bản tiếng Việt
- **faiss-cpu** - Vector similarity search

### Search & Matching
- **fuzzywuzzy** - Fuzzy string matching
- **Unidecode 1.4.0** - Unicode normalization

### Data Processing
- **pandas 2.3.1** - Data manipulation
- **numpy 2.3.1** - Numerical computing
- **topsispy 0.0.1** - TOPSIS algorithm cho multi-criteria decision making

### Web Scraping
- **lxml 6.0.0** - HTML/XML parsing

### Configuration
- **python-dotenv 1.0.0** - Environment variable management

## 📦 Cài đặt

### Yêu cầu hệ thống
- Python 3.8+
- MongoDB 4.4+
- Redis 6.0+

### Cài đặt dependencies

```bash
# Clone repository
git clone <repository-url>
cd store_recommendation_backend

# Tạo virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows

# Cài đặt packages
pip install -r requirements.txt
```

### Cài đặt MongoDB

```bash
# macOS
brew install mongodb-community

# Ubuntu
sudo apt-get install mongodb

# Khởi động MongoDB
mongod --dbpath=/path/to/data
```

### Cài đặt Redis

```bash
# macOS
brew install redis
redis-server

# Ubuntu
sudo apt-get install redis-server
sudo service redis-server start
```

## ⚙️ Cấu hình

### Tạo file `.env`

```bash
cp .env.example .env
```

### Cấu hình các biến môi trường trong `.env`

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_PORT=5000
FLASK_ENV=development

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRES_HOURS=24
JWT_REFRESH_TOKEN_EXPIRES_DAYS=90

# MongoDB Configuration
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=store_recommendation
METADATA_DB_NAME=metadata

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# OpenRouteService API (for maps)
OPENROUTE_API_KEY=your-openroute-api-key

# Network Configuration
TAILSCALE_IP=localhost
NGROK_URL=http://localhost
```

## 🚀 Chạy ứng dụng

### 1. Build FAISS Indexes (lần đầu tiên)

```bash
cd scripts
python build_faiss_indexes.py
```

Lệnh này sẽ:
- Tạo vector embeddings cho tất cả sản phẩm
- Build FAISS indexes cho 19 categories
- Lưu indexes vào `scripts/faiss_indexes/`

### 2. Khởi động Flask server

```bash
python app.py
```

Server sẽ chạy tại: `http://localhost:5000`

### 3. Khởi động Celery worker (optional, cho background tasks)

```bash
python run_celery.py
```

### 4. Test API

```bash
curl http://localhost:5000/api/v1/test
```

## 📡 API Endpoints

### Authentication (`/api/v1/auth`)
- `POST /register` - Đăng ký tài khoản mới
- `POST /login` - Đăng nhập
- `POST /google-login` - Đăng nhập Google OAuth
- `POST /refresh` - Refresh JWT token
- `POST /logout` - Đăng xuất

### User Management (`/api/v1/user`)
- `GET /profile` - Xem thông tin cá nhân
- `PUT /profile` - Cập nhật thông tin
- `POST /location` - Cập nhật vị trí
- `GET /favourite-stores` - Danh sách cửa hàng yêu thích
- `POST /favourite-stores` - Thêm cửa hàng yêu thích

### Basket (`/api/v1/basket`)
- `GET /` - Xem giỏ hàng
- `POST /ingredients` - Thêm nguyên liệu
- `POST /dishes` - Thêm món ăn
- `DELETE /ingredients` - Xóa nguyên liệu
- `DELETE /dishes` - Xóa món ăn
- `PUT /dishes/servings` - Cập nhật số phần

### Store Recommendation (`/api/v1/calculate`)
- `POST /recommend` - Gợi ý cửa hàng tối ưu dựa trên giỏ hàng

### Public Data (`/api/v1/public`)
- `GET /dishes` - Danh sách món ăn
- `GET /ingredients` - Danh sách nguyên liệu
- `GET /categories` - Danh mục sản phẩm
- `GET /search/dishes` - Tìm kiếm món ăn
- `GET /search/ingredients` - Tìm kiếm nguyên liệu

### Stores (`/api/v1/stores`)
- `GET /nearby` - Tìm cửa hàng gần nhất
- `GET /:id` - Chi tiết cửa hàng
- `GET /:id/products` - Sản phẩm của cửa hàng

### AI Features (`/api/v1/ai`)
- `POST /chat` - Chat với AI
- `POST /suggest-dishes` - Gợi ý món ăn

### Admin (`/api/v1/admin`) - Yêu cầu admin authentication
- `POST /dishes` - Tạo món ăn
- `PUT /dishes/:id` - Cập nhật món ăn
- `DELETE /dishes/:id` - Xóa món ăn
- `POST /ingredients` - Tạo nguyên liệu
- `PUT /ingredients/:id` - Cập nhật nguyên liệu
- `DELETE /ingredients/:id` - Xóa nguyên liệu

### Crawling (`/api/v1/crawling`) - Admin only
- `POST /start` - Bắt đầu crawling
- `GET /status` - Kiểm tra trạng thái

## 📁 Cấu trúc dự án

```
store_recommendation_backend/
├── app.py                      # Entry point, Flask app initialization
├── run_celery.py              # Celery worker startup
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (not in git)
│
├── database/                  # Database connections
│   └── mongodb.py            # MongoDB connection manager
│
├── models/                    # Data models
│   ├── user.py
│   ├── dish.py
│   ├── ingredient.py
│   └── store.py
│
├── routes/                    # API route blueprints
│   ├── auth_routes.py        # Authentication endpoints
│   ├── user_routes.py        # User management
│   ├── basket_routes.py      # Shopping basket
│   ├── calculate_routes.py   # Store recommendation
│   ├── public_routes.py      # Public data (dishes, ingredients)
│   ├── store_routes.py       # Store management
│   ├── ai_routes.py          # AI features
│   ├── admin_routes.py       # Admin management
│   ├── crawling_routes.py    # Web crawling
│   ├── products_routes.py    # Product management
│   ├── report_routes.py      # Reports & analytics
│   └── schedule_routes.py    # Scheduled tasks
│
├── services/                  # Business logic layer
│   ├── calculate_service.py  # Store recommendation algorithm
│   ├── embedding_service.py  # FAISS vector search
│   ├── user_service.py       # User operations
│   ├── admin_service.py      # Admin operations
│   ├── public_service.py     # Public data services
│   └── ai_service.py         # AI features
│
├── middleware/                # Custom middleware
│   └── auth_middleware.py    # JWT authentication
│
├── validators/                # Input validation
│   ├── auth_validators.py
│   ├── admin_validators.py
│   └── user_validators.py
│
├── utils/                     # Utility functions
│   └── helpers.py
│
└── scripts/                   # Utility scripts
    ├── build_faiss_indexes.py    # Build FAISS indexes
    └── faiss_indexes/            # Stored FAISS index files
        ├── vegetables.index
        ├── vegetables_mapping.pkl
        ├── vegetables_data.pkl
        └── ... (19 categories)
```

## 🧮 Thuật toán

### 1. Product Search Strategy (Hybrid Approach)

#### Short Queries (≤6 ký tự): Ưu tiên Fuzzy Search
```
Query: "Sả", "Muối", "Bún"
↓
Fuzzy String Matching (FIRST)
- Partial ratio matching
- Token sort ratio
- Substring boosting
↓
Nếu không tìm thấy → FAISS Semantic Search (threshold=0.25)
```

#### Long Queries (>6 ký tự): Ưu tiên FAISS
```
Query: "Nấm đông cô", "Dầu ăn thực vật"
↓
FAISS Semantic Search (FIRST, threshold=0.35)
- Vietnamese SBERT embeddings
- Cosine similarity
↓
Nếu score < 0.5 → Fuzzy Search fallback
```

### 2. TOPSIS Algorithm (Store Ranking)

**Criteria** (5 tiêu chí):
1. **Total Cost** (8.72%) - Tổng giá trị giỏ hàng (càng thấp càng tốt)
2. **Distance** (14.99%) - Khoảng cách từ người dùng (càng gần càng tốt)
3. **Store Rating** (4.87%) - Đánh giá cửa hàng (càng cao càng tốt)
4. **Availability** (45.72%) - Tỷ lệ sản phẩm có sẵn (càng cao càng tốt)
5. **Familiarity** (25.96%) - Cửa hàng yêu thích (100 nếu có, 0 nếu không)

**Process**:
```
Input: List of candidate stores with basket matching
↓
1. Build decision matrix (stores × criteria)
↓
2. Normalize matrix values
↓
3. Apply weights to each criterion
↓
4. Calculate ideal best & worst solutions
↓
5. Compute distance to ideal solutions
↓
6. Calculate TOPSIS score (0-100)
↓
Output: Ranked stores with scores
```

### 3. FAISS Vector Search

**Index Type**: `IndexFlatIP` (Inner Product for cosine similarity)

**Process**:
```
Build Phase:
Products → Vietnamese SBERT → Embeddings → L2 Normalize → FAISS Index

Search Phase:
Query → Vietnamese SBERT → Embedding → L2 Normalize → FAISS Search → Top-K results
```

**Collections** (19 categories):
- vegetables, fresh_fruits, fresh_meat, seafood_&_fish_balls
- milk, yogurt, ice_cream_&_cheese
- grains_&_staples, cereals_&_grains, instant_foods
- seasonings, beverages, alcoholic_beverages
- snacks, candies, cakes, dried_fruits, fruit_jam
- cold_cuts:_sausages_&_ham

## 🔄 Workflow

### User Journey: Tìm cửa hàng tối ưu

```
1. User adds items to basket
   ├── Add ingredients (e.g., "Sả", "Muối", "Thịt bò")
   └── Add dishes (e.g., "Phở bò" with servings=4)

2. System processes basket
   ├── Calculate total quantity for each ingredient
   └── Normalize categories

3. For each nearby store:
   ├── For each ingredient:
   │   ├── Determine search strategy (short vs long query)
   │   ├── Search products (fuzzy or FAISS)
   │   ├── Find best match
   │   └── Calculate cost
   └── Calculate store metrics (total cost, availability %)

4. Apply TOPSIS algorithm
   ├── Score stores based on 5 criteria
   └── Rank stores

5. Return top recommendations
   └── Store details + matched products + alternatives
```

## 🛠️ Development

### Code Style
- Follow PEP 8 guidelines
- Use type hints where applicable
- Document complex functions

### Testing
```bash
# Run tests
pytest

# Run with coverage
pytest --cov=services --cov-report=html
```

### Database Schema

**Users Collection**:
```javascript
{
  _id: ObjectId,
  email: String,
  password: String (hashed),
  name: String,
  phone: String,
  location: { lat: Number, lng: Number },
  near_stores: Array,
  favourite_stores: Array,
  basket: {
    ingredients: Array,
    dishes: Array
  },
  allergies: Array,
  created_at: Date
}
```

**Dishes Collection**:
```javascript
{
  _id: ObjectId,
  dish: String,  // English name
  vietnamese_name: String,
  image: String,
  ingredients: [{
    vietnamese_name: String,
    ingredient_name: String,
    unit: String,
    net_unit_value: Number,
    category: String,
    image: String
  }]
}
```

**Products Collections** (19 separate collections by category):
```javascript
{
  _id: ObjectId,
  name: String,  // Vietnamese product name
  name_en: String,
  price: Number,
  sys_price: Number,
  discountPercent: Number,
  unit: String,
  net_unit_value: Number,
  category: String,
  store_id: String,
  chain: String,
  image: String,
  url: String,
  sku: String,
  promotion: String
}
```
