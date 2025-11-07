# Tổng Quan Hệ Thống RabbitMQ — Main, AI Service, Crawling Service

Tài liệu này mô tả chi tiết cách RabbitMQ được sử dụng trong hệ thống: kiến trúc tổng thể, mô hình kết nối, các hàng đợi, mô hình luồng I/O, luồng xử lý end‑to‑end, hợp đồng dữ liệu (payload), cơ chế độ tin cậy, giám sát/vận hành và xử lý sự cố.


## 1) Kiến trúc & Vai trò

- Main Service (repo này):
  - Producer: đẩy job sang Crawling Service
  - Consumer: nhận kết quả từ Crawling thông qua response queue
  - RPC Client: gửi yêu cầu đến AI Service và chờ phản hồi qua callback queue
  - Sở hữu 1 kết nối RabbitMQ duy nhất và 2 channel logic (Crawling, AI)
- Crawling Service (dịch vụ bên ngoài):
  - Consumer: lắng nghe `crawling_request_queue`
  - Producer: trả kết quả về `crawling_response_queue`
- AI Service (dịch vụ bên ngoài):
  - Consumer: lắng nghe `recipe_analysis_request` (và biến thể cho ảnh nếu dùng)
  - Producer: trả phản hồi về callback queue được chỉ định trong `reply_to`


## 2) Kết nối & Kênh (Channels)

- 1 kết nối RabbitMQ (pika BlockingConnection) trong `services/rabbitmq_service.py`
- 2 channel trên cùng kết nối:
  - `channel` cho Crawling (work queue pattern)
  - `ai_channel` cho AI (RPC pattern)
- 1 I/O thread duy nhất tương tác với pika (publish, consume, `process_data_events`); các thread xử lý HTTP của Flask chỉ đưa job vào hàng đợi nội bộ (thread‑safe).

Biến môi trường (.env):
- `RABBITMQ_URL=amqp://<user>:<pass>@<host>:5672/<vhost>`
- `RABBITMQ_CRAWLING_REQUEST_QUEUE=crawling_request_queue`
- `RABBITMQ_CRAWLING_RESPONSE_QUEUE=crawling_response_queue`
- `AI_QUEUE_NAME=recipe_analysis_request`


## 3) Hàng đợi (Queues) & Default exchange

- Crawling (durable):
  - Request: `crawling_request_queue`
  - Response: `crawling_response_queue`
- AI:
  - Request: `recipe_analysis_request` (durable, TTL 5 phút)
  - Callback: server‑named exclusive callback queue (ví dụ `amq.gen-XXXXX`) tạo 1 lần khi khởi động và tái sử dụng cho mọi RPC request
- Exchange: dùng default exchange ""; `routing_key` chính là tên queue

Độ bền & TTL:
- Crawling queues: `durable=True` (tồn tại sau khi broker restart)
- AI request queue: `durable=True` với `x-message-ttl: 300000` (5 phút)
- Callback queue: `exclusive`/`auto-delete` (tự hủy khi connection đóng)


## 4) Mô hình luồng I/O (Single I/O Thread)

- Thread HTTP (Flask) KHÔNG chạm trực tiếp vào pika. Chúng push job vào `_publish_queue` (queue.Queue)
- 1 I/O thread chạy `_io_loop()`:
  1) `connection.process_data_events(time_limit≈0.1)` để xử lý message đến
  2) Rút job từ `_publish_queue` để `basic_publish`
- Đồng bộ cho request đồng bộ (sync) dùng `threading.Event` gắn với mỗi `correlation_id`
- Thiết kế này loại bỏ race condition vì BlockingConnection không thread‑safe


## 5) Luồng xử lý End‑to‑End

### 5.1 Crawling — Async (Fire‑and‑Forget) & Sync

- Luồng Async (ví dụ ping/enqueue job):
  1) Main đẩy job vào `crawling_request_queue`
  2) Trả về client ngay (không chờ kết quả)
  3) Crawling xử lý và có thể gửi trạng thái/kết quả về `crawling_response_queue`

- Luồng Sync (khi cần kết quả ngay):
  1) Main tạo future (Event)
  2) Publish request kèm `job_id` vào `crawling_request_queue`
  3) Chờ Event với timeout
  4) Consumer ở `crawling_response_queue` match theo `job_id`, set Event, trả kết quả

Consumer phía Main:
- `basic_consume(queue=crawling_response_queue, on_message_callback=_handle_crawling_response, auto_ack=False)`
- Handler parse JSON, match action/job_id, hoàn tất future và `basic_ack`

### 5.2 AI — RPC Pattern (1 callback queue dùng chung)

- Khi khởi động (1 lần):
  - Tạo callback queue dạng server‑named, exclusive trên `ai_channel`
  - Đăng ký `basic_consume` callback queue với `_handle_ai_response`

- Mỗi request:
  1) Main tạo `correlation_id` và future (Event)
  2) Job gửi sang I/O thread kèm properties:
     - `correlation_id=<uuid>`
     - `reply_to=<callback_queue>` (I/O thread gắn vào)
  3) I/O thread publish đến `recipe_analysis_request`
  4) AI Service xử lý và publish response về `reply_to` với cùng `correlation_id`
  5) `_handle_ai_response` match `correlation_id`, set future, `basic_ack`
  6) Thread HTTP được đánh thức và trả JSON cho client

Thiết kế này đúng theo chuẩn RPC của RabbitMQ, tránh phải tạo callback queue cho từng request.


## 6) Hợp đồng dữ liệu (Payload Schemas)

Tất cả payload là JSON (`content_type=application/json`, `delivery_mode=2` cho message bền — trừ callback).

### 6.1 Crawling Requests (ví dụ)

- Ping / trạng thái đơn giản
```
{
  "action": "ping",
  "timestamp": "2025-11-06T15:00:00Z",
  "job_id": "<uuid>"
}
```

- Crawl URL
```
{
  "action": "crawl_url",
  "url": "https://example.com/product/123",
  "depth": 1,
  "job_id": "<uuid>"
}
```

### 6.2 Crawling Responses
```
{
  "action": "task_status_update" | "crawl_result",
  "job_id": "<uuid>",
  "status": "done|failed|in_progress",
  "data": { ... },
  "error": null | { "message": "..." }
}
```

### 6.3 AI Requests

- Phân tích text/recipe
```
{
  "user_input": "<string hoặc JSON dạng chuỗi>"
}
```

- Phân tích ảnh
```
{
  "user_input": "{\"s3_url\":\"https://...\", \"description\":\"...\"}"
}
```

Thuộc tính (I/O thread gắn):
- `correlation_id=<uuid>`
- `reply_to=<amq.gen-...>` (callback dùng chung)

### 6.4 AI Responses
```
{
  "success": true,
  "result": { ... }
}
```
(hoặc cấu trúc domain‑specific tùy thao tác AI). Broker sẽ chuyển kèm `props.correlation_id` trùng với request.


## 7) Độ tin cậy & Back‑Pressure

- Ack: consumer `basic_ack` sau khi xử lý thành công; `basic_nack(requeue=False)` với lỗi parse nghiêm trọng
- QoS: trên channel Crawling dùng `basic_qos(prefetch_count=10)` để tránh quá tải consumer
- Persistence: publish với `delivery_mode=2` đến các queue durable (callback queue không cần bền)
- TTL trên AI request queue giúp dọn request cũ (5 phút)
- Timeouts:
  - Crawling sync: chờ Event với timeout cấu hình (ví dụ 30s)
  - AI RPC: chờ Event (mặc định 100s). Hết hạn thì xóa future và HTTP trả 503/504
- Reconnect: khi lỗi kết nối, service retry, re‑declare consumer cho Crawling response và callback consumer của AI


## 8) Giám sát & Sức khỏe hệ thống

Chỉ số chính:
- Độ sâu queue & số consumer:
  - `crawling_request_queue`, `crawling_response_queue`
  - `recipe_analysis_request`
  - Callback queue (amq.gen-xxx) luôn có đúng 1 consumer (service này)
- Tốc độ: publish/ack per queue
- I/O thread còn sống
- Mốc heartbeat gần nhất từ `_io_loop`
- Tỷ lệ timeout theo endpoint

Kiểm tra vận hành:
- RabbitMQ Management UI (http://<host>:15672): queues, consumers, message rates
- Logs:
  - "RabbitMQ-IO-Thread started"
  - "AI callback queue created: amq.gen-..."
  - "AI request published: <corr_id> → reply_to: amq.gen-..."
  - "AI response received: correlation_id=<corr_id>"


## 9) Sự cố thường gặp & Cách xử lý

- Không có consumer ở crawling queues → đảm bảo Crawling Service đang chạy và subscribe đúng queue
- AI request bị timeout → kiểm `reply_to`, callback consumer, AI Service có publish trả về kèm `correlation_id` không
- `PRECONDITION_FAILED` khi declare queue → dùng `passive=True` nếu queue đã tồn tại; nếu tạo mới phải khớp `arguments` (ví dụ TTL)
- `StreamLostError`/lỗi NoneType bên trong pika → thường do nhiều thread chạm vào pika; dùng I/O thread đơn để tránh
- Message kẹt ở trạng thái unacked → kiểm tra log worker, chắc chắn gọi `basic_ack` sau khi xử lý


## 10) Mapping Endpoint (chọn lọc)

- Crawling (trong `routes/crawling_routes.py` — không trích dẫn tại đây):
  - Enqueue ping/crawl: publish vào `crawling_request_queue`
  - Nếu sync, chờ ở `crawling_response_queue` (match theo `job_id`)

- AI (trong `routes/ai_routes.py`):
  - `/api/ai/analyze-recipe` → publish `recipe_analysis_request`, chờ RPC reply ở callback queue
  - `/api/ai/analyze-image` → publish `recipe_analysis_request` (payload ảnh), chờ RPC reply ở callback queue


## 11) Bảo mật & Truy cập

- Thông tin đăng nhập cung cấp qua `RABBITMQ_URL`
- Không dùng `guest/guest` cho truy cập từ xa; tạo user riêng với quyền tối thiểu
- Callback queue độc quyền (exclusive) cho connection này để an toàn


## 12) Năng lực & Tối ưu (gợi ý)

- Thông lượng Crawling async chủ yếu phụ thuộc số worker của Crawling và I/O của broker; có thể bật publisher confirms (độ an toàn ↑, độ trễ ↑)
- Tốc độ AI phụ thuộc compute của AI Service; scale ngang bằng cách chạy nhiều worker AI
- Dùng `prefetch_count` để cân bằng tải và tránh dồn việc vào 1 consumer


## 13) Files & Tham chiếu

- Code chính: `services/rabbitmq_service.py`
- Tài liệu liên quan:
  - `SINGLE_IO_THREAD_IMPLEMENTATION.md`
  - `RPC_PATTERN_FIX.md`
  - `RABBITMQ_FLOW_DIAGRAM.md`
  - `ARCHITECTURE_DIAGRAM.md`


## 14) Trình tự nhanh (AI RPC) — ASCII

```
Client → Main (HTTP) → _publish_queue → I/O Thread → recipe_analysis_request
                                              ↓
                                        AI Service (consume, process)
                                              ↓
                                  reply_to: amq.gen-xxx (correlation_id)
                                              ↓
                                    _handle_ai_response (ack)
                                              ↓
                          future['event'].set() → HTTP response
```


## 15) Trình tự nhanh (Crawling Sync)

```
Client → Main (HTTP) → _publish_queue → I/O Thread → crawling_request_queue
                                              ↓
                                      Crawling Service (consume)
                                              ↓
                               crawling_response_queue (publish result)
                                              ↓
                       _handle_crawling_response (ack, match job_id)
                                              ↓
                          future['event'].set() → HTTP response
```
