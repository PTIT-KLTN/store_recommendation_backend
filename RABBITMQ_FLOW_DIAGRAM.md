# RabbitMQ Flow Diagram - Kiến Trúc Hệ Thống Hiện Tại

## Tổng Quan Hệ Thống

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Main Service (Producer)                      │
│                    store_recommendation_backend                      │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              RabbitMQService (Singleton)                     │   │
│  │  ┌────────────────────────────────────────────────────┐     │   │
│  │  │  Single RabbitMQ Connection                        │     │   │
│  │  │  URL: amqp://guest:guest@localhost:5672/           │     │   │
│  │  │                                                     │     │   │
│  │  │  ┌──────────────────┐  ┌──────────────────┐       │     │   │
│  │  │  │  Channel (Main)  │  │  AI Channel      │       │     │   │
│  │  │  │  - Crawling      │  │  - AI Service    │       │     │   │
│  │  │  └──────────────────┘  └──────────────────┘       │     │   │
│  │  └────────────────────────────────────────────────────┘     │   │
│  │                                                               │   │
│  │  Thread Model:                                               │   │
│  │  ┌──────────────────┐   ┌──────────────────┐               │   │
│  │  │ Flask Threads    │   │  I/O Thread      │               │   │
│  │  │ (Multiple)       │──→│  (Single)        │               │   │
│  │  │ Submit jobs to   │   │  Owns all pika   │               │   │
│  │  │ _publish_queue   │   │  operations      │               │   │
│  │  └──────────────────┘   └──────────────────┘               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Single Connection
                                    │ 2 Channels
                                    ▼
         ┌──────────────────────────────────────────────────┐
         │         RabbitMQ Server (localhost:5672)         │
         │                                                   │
         │  ┌────────────────────────────────────────────┐  │
         │  │       Crawling Service Queues              │  │
         │  │  ┌──────────────────────────────────────┐  │  │
         │  │  │ crawling_request_queue (durable)     │  │  │
         │  │  │ - Messages from Main → Crawling      │  │  │
         │  │  └──────────────────────────────────────┘  │  │
         │  │  ┌──────────────────────────────────────┐  │  │
         │  │  │ crawling_response_queue (durable)    │  │  │
         │  │  │ - Messages from Crawling → Main      │  │  │
         │  │  └──────────────────────────────────────┘  │  │
         │  └────────────────────────────────────────────┘  │
         │                                                   │
         │  ┌────────────────────────────────────────────┐  │
         │  │       AI Service Queues (RPC Pattern)      │  │
         │  │  ┌──────────────────────────────────────┐  │  │
         │  │  │ recipe_analysis_request (durable)    │  │  │
         │  │  │ - TTL: 300000ms (5 minutes)          │  │  │
         │  │  │ - Messages from Main → AI Service    │  │  │
         │  │  └──────────────────────────────────────┘  │  │
         │  │  ┌──────────────────────────────────────┐  │  │
         │  │  │ amq.gen-xxx (exclusive, auto-delete) │  │  │
         │  │  │ - Single callback queue for Main     │  │  │
         │  │  │ - Messages from AI Service → Main    │  │  │
         │  │  │ - Created once at startup            │  │  │
         │  │  └──────────────────────────────────────┘  │  │
         │  └────────────────────────────────────────────┘  │
         └──────────────────────────────────────────────────┘
                        │                      │
           ┌────────────┘                      └────────────┐
           │                                                 │
           ▼                                                 ▼
┌──────────────────────┐                    ┌──────────────────────┐
│  Crawling Service    │                    │    AI Service        │
│   (Consumer)         │                    │    (Consumer)        │
│                      │                    │                      │
│  - Listen on         │                    │  - Listen on         │
│    crawling_request  │                    │    recipe_analysis   │
│  - Process tasks     │                    │  - Analyze recipes   │
│  - Send to           │                    │  - Analyze images    │
│    crawling_response │                    │  - Send to reply_to  │
└──────────────────────┘                    └──────────────────────┘
```

## Chi Tiết Luồng Hoạt Động

### 1. Crawling Service Flow (Work Queue Pattern)

#### 1.1 Async Request (Fire-and-Forget)
```
Flask Handler                I/O Thread              RabbitMQ               Crawling Service
─────────────               ──────────              ────────               ────────────────
     │                           │                      │                         │
     │ 1. send_async_request()   │                      │                         │
     │   job = {                 │                      │                         │
     │     type: 'crawling_req'  │                      │                         │
     │     body: {...}           │                      │                         │
     │   }                       │                      │                         │
     │                           │                      │                         │
     │ 2. put(job)              │                      │                         │
     ├──────────────────────────►│                      │                         │
     │                           │                      │                         │
     │ 3. Return immediately     │                      │                         │
     ◄───────────────────────────┤                      │                         │
     │                           │                      │                         │
     │                           │ 4. basic_publish()   │                         │
     │                           ├─────────────────────►│                         │
     │                           │   routing_key:       │                         │
     │                           │   crawling_request   │ 5. Route to queue       │
     │                           │                      ├────────────────────────►│
     │                           │                      │                         │
     │                           │                      │                         │ 6. Process task
     │                           │                      │                         ├───────────┐
     │                           │                      │                         │           │
     │                           │                      │                         ◄───────────┘
     │                           │                      │                         │
     │                           │                      │ 7. Send result          │
     │                           │                      │◄────────────────────────┤
     │                           │ 8. Receive on        │    routing_key:         │
     │                           │    crawling_response │    crawling_response    │
     │                           ◄─────────────────────┤                         │
     │                           │                      │                         │
     │                           │ 9. _handle_response  │                         │
     │                           │    Store in cache    │                         │
```

**Đặc điểm:**
- ✅ Không đợi response
- ✅ Return ngay sau khi submit job
- ✅ Response được cache để query sau
- ✅ Phù hợp cho crawling tasks (thời gian chạy lâu)

#### 1.2 Sync Request (Wait for Response)
```
Flask Handler                I/O Thread              RabbitMQ               Crawling Service
─────────────               ──────────              ────────               ────────────────
     │                           │                      │                         │
     │ 1. send_request()         │                      │                         │
     │   Create future + Event   │                      │                         │
     │   future = {              │                      │                         │
     │     'result': None,       │                      │                         │
     │     'event': Event()      │                      │                         │
     │   }                       │                      │                         │
     │                           │                      │                         │
     │ 2. put(job)              │                      │                         │
     ├──────────────────────────►│                      │                         │
     │                           │                      │                         │
     │ 3. Wait on Event          │                      │                         │
     │   event.wait(timeout=30) │                      │                         │
     │   ┌──────────────────┐   │                      │                         │
     │   │   BLOCKING       │   │                      │                         │
     │   └──────────────────┘   │                      │                         │
     │         │                 │ 4. basic_publish()   │                         │
     │         │                 ├─────────────────────►│                         │
     │         │                 │                      │                         │
     │         │                 │                      │ 5. Route to queue       │
     │         │                 │                      ├────────────────────────►│
     │         │                 │                      │                         │
     │         │                 │                      │                         │ 6. Process
     │         │                 │                      │                         ├──────┐
     │         │                 │                      │                         │      │
     │         │                 │                      │                         ◄──────┘
     │         │                 │                      │                         │
     │         │                 │                      │ 7. Send result          │
     │         │                 │                      │◄────────────────────────┤
     │         │                 │ 8. _handle_response  │                         │
     │         │                 ◄─────────────────────┤                         │
     │         │                 │   Match job_id       │                         │
     │         │                 │   future['result']=  │                         │
     │         │                 │   future['event'].   │                         │
     │         │                 │   set()              │                         │
     │         │                 │                      │                         │
     │ 4. Event triggered!       │                      │                         │
     │    Return result          │                      │                         │
     ◄─────────────────────────┘ │                      │                         │
     │                           │                      │                         │
```

**Đặc điểm:**
- ✅ Đợi response trong timeout (30s default)
- ✅ Sử dụng Event.wait() - không busy polling
- ✅ Thread-safe với lock
- ✅ Phù hợp cho operations cần kết quả ngay

### 2. AI Service Flow (RPC Pattern)

#### 2.1 Recipe Analysis Request
```
Flask Handler                I/O Thread              RabbitMQ               AI Service
─────────────               ──────────              ────────               ──────────
     │                           │                      │                      │
     │ 1. send_ai_request()      │                      │                      │
     │   correlation_id = uuid   │                      │                      │
     │   future = {              │                      │                      │
     │     'result': None,       │                      │                      │
     │     'event': Event()      │                      │                      │
     │   }                       │                      │                      │
     │   response_futures[       │                      │                      │
     │     correlation_id        │                      │                      │
     │   ] = future              │                      │                      │
     │                           │                      │                      │
     │ 2. put(job) to queue     │                      │                      │
     ├──────────────────────────►│                      │                      │
     │   job = {                 │                      │                      │
     │     type: 'ai_request',   │                      │                      │
     │     correlation_id: xxx,  │                      │                      │
     │     routing_key: recipe_  │                      │                      │
     │       analysis_request,   │                      │                      │
     │     body: {...},          │                      │                      │
     │     properties: {         │                      │                      │
     │       correlation_id: xxx │                      │                      │
     │     }                     │                      │                      │
     │   }                       │                      │                      │
     │                           │                      │                      │
     │ 3. Wait on Event          │                      │                      │
     │   event.wait(timeout=100) │                      │                      │
     │   ┌──────────────────┐   │                      │                      │
     │   │   BLOCKING       │   │                      │                      │
     │   └──────────────────┘   │                      │                      │
     │         │                 │ 4. Get job from queue│                      │
     │         │                 │    Add reply_to to   │                      │
     │         │                 │    properties:       │                      │
     │         │                 │    reply_to =        │                      │
     │         │                 │    amq.gen-xxx       │                      │
     │         │                 │    (callback queue)  │                      │
     │         │                 │                      │                      │
     │         │                 │ 5. basic_publish()   │                      │
     │         │                 ├─────────────────────►│                      │
     │         │                 │   routing_key:       │                      │
     │         │                 │   recipe_analysis_   │                      │
     │         │                 │   request            │                      │
     │         │                 │   properties:        │                      │
     │         │                 │   - correlation_id   │                      │
     │         │                 │   - reply_to         │                      │
     │         │                 │                      │                      │
     │         │                 │                      │ 6. Route to queue    │
     │         │                 │                      ├─────────────────────►│
     │         │                 │                      │                      │
     │         │                 │                      │                      │ 7. Analyze
     │         │                 │                      │                      ├────┐
     │         │                 │                      │                      │    │
     │         │                 │                      │                      ◄────┘
     │         │                 │                      │                      │
     │         │                 │                      │ 8. Publish response  │
     │         │                 │                      │    routing_key =     │
     │         │                 │                      │    props.reply_to    │
     │         │                 │                      │    (amq.gen-xxx)     │
     │         │                 │                      │◄─────────────────────┤
     │         │                 │                      │    correlation_id =  │
     │         │                 │                      │    props.corr_id     │
     │         │                 │                      │                      │
     │         │                 │ 9. Route to callback │                      │
     │         │                 │    queue (amq.gen-xxx│                      │
     │         │                 ◄─────────────────────┤                      │
     │         │                 │                      │                      │
     │         │                 │ 10. _handle_ai_      │                      │
     │         │                 │     response()       │                      │
     │         │                 │     Match corr_id    │                      │
     │         │                 │     future['result'] │                      │
     │         │                 │     = response       │                      │
     │         │                 │     future['event']. │                      │
     │         │                 │     set()            │                      │
     │         │                 │                      │                      │
     │ 4. Event triggered!       │                      │                      │
     │    Return result          │                      │                      │
     ◄─────────────────────────┘ │                      │                      │
     │                           │                      │                      │
```

**Đặc điểm RPC Pattern:**
- ✅ Single callback queue (amq.gen-xxx) được tạo 1 lần khi init
- ✅ Mọi AI requests dùng chung callback queue này
- ✅ Match request/response bằng correlation_id
- ✅ reply_to property chỉ đến callback queue
- ✅ Timeout 100s mặc định
- ✅ Thread-safe với Event.wait()

#### 2.2 Image Analysis Request
```
[Luồng tương tự như Recipe Analysis]

Flask Handler → I/O Thread → RabbitMQ → AI Service
      ↑                                        ↓
      └────────── Response via callback ───────┘
                  (correlation_id matching)
```

**Request format:**
```json
{
  "user_input": "{\"s3_url\": \"https://...\", \"description\": \"...\"}"
}
```

## Kiến Trúc Kết Nối

### Single Connection, Dual Channels

```
RabbitMQService (Main Service)
    │
    ├─ connection (Single BlockingConnection)
    │   │
    │   ├─ channel (Main Channel)
    │   │   ├─ Producer: crawling_request_queue
    │   │   └─ Consumer: crawling_response_queue
    │   │
    │   └─ ai_channel (AI Channel)
    │       ├─ Producer: recipe_analysis_request
    │       ├─ Consumer: amq.gen-xxx (callback queue)
    │       └─ Single callback queue for all AI requests
    │
    └─ _io_thread (Single I/O Thread)
        ├─ process_data_events() - handle incoming
        └─ _publish_queue.get() - handle outgoing
```

**Lý do tách 2 channels:**
- ✅ Tránh xung đột giữa Crawling và AI operations
- ✅ Độc lập QoS settings
- ✅ Dễ debug và monitor
- ✅ Isolation khi có lỗi

## Thread Model - Single I/O Thread Pattern

```
┌────────────────────────────────────────────────────────┐
│              Flask Application                          │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Thread 1   │  │  Thread 2   │  │  Thread 3   │   │
│  │  HTTP Req   │  │  HTTP Req   │  │  HTTP Req   │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                 │                 │           │
│         │ put(job)        │ put(job)       │ put(job) │
│         └────────┬────────┴────────┬────────┘          │
│                  ▼                 ▼                    │
│         ┌──────────────────────────────────┐           │
│         │    _publish_queue                │           │
│         │    (queue.Queue - Thread-Safe)   │           │
│         └──────────────┬───────────────────┘           │
│                        │                                │
│                        │ get_nowait()                   │
│                        ▼                                │
│         ┌────────────────────────────────────┐         │
│         │     I/O Thread (Single)            │         │
│         │  - process_data_events()           │         │
│         │  - _execute_publish_job()          │         │
│         │  - OWNS all pika operations        │         │
│         └────────────┬───────────────────────┘         │
│                      │                                  │
└──────────────────────┼──────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │  pika Connection │
            │  (Not Thread-Safe│
            │   → Only 1 thread│
            │     can touch)   │
            └──────────────────┘
```

**Tại sao Single I/O Thread?**
- ❌ `pika.BlockingConnection` is NOT thread-safe
- ❌ Multiple threads → Race conditions → StreamLostError
- ✅ Single thread owns all pika calls → No races
- ✅ Flask threads submit jobs via thread-safe queue.Queue
- ✅ Event.wait() for synchronization (no polling)

## Message Properties

### Crawling Service Messages

**Request:**
```python
properties = pika.BasicProperties(
    delivery_mode=2,  # Persistent
    content_type='application/json'
)
```

**Response:**
```python
# AI Service tự động reply
# Không cần properties đặc biệt
```

### AI Service Messages (RPC)

**Request:**
```python
properties = pika.BasicProperties(
    correlation_id='uuid-string',      # Match request/response
    reply_to='amq.gen-xxx',           # Callback queue
    content_type='application/json',
    delivery_mode=2                    # Persistent
)
```

**Response (from AI Service):**
```python
properties = pika.BasicProperties(
    correlation_id='uuid-string'  # Same as request
)
# routing_key = props.reply_to from request
```

## Queue Characteristics

### Crawling Queues
```python
# crawling_request_queue
- Type: Classic queue
- Durable: True
- Auto-delete: False
- Exclusive: False
- Arguments: None

# crawling_response_queue
- Type: Classic queue
- Durable: True
- Auto-delete: False
- Exclusive: False
- Arguments: None
```

### AI Service Queues
```python
# recipe_analysis_request
- Type: Classic queue
- Durable: True
- Auto-delete: False
- Exclusive: False
- Arguments: {'x-message-ttl': 300000}  # 5 minutes

# amq.gen-xxx (callback queue)
- Type: Server-named queue
- Durable: False
- Auto-delete: True   # Deleted when connection closes
- Exclusive: True     # Only this connection can access
- Arguments: None
```

## Error Handling

### Timeout Scenarios

```
Request Sent                    Timeout Occurs
    │                                │
    │ event.wait(timeout=100)        │
    ├────────────────────────────────┤
    │                                │
    │                                ▼
    │                          TimeoutError
    │                          - Pop future
    │                          - Return error
    │                          - Client handles
```

### Connection Lost

```
I/O Thread                     RabbitMQ
    │                              │
    │ process_data_events()        │
    ├─────────────────────────────►│
    │                              │
    │                              ✗ Connection lost
    │◄─────────────────────────────┤
    │                              │
    │ Detect connection.is_closed  │
    │                              │
    ▼                              │
Sleep 5s                          │
Retry connection                  │
    │                              │
    ├─────────────────────────────►│
    │                              │
    ▼                              ▼
Resume operations            Back online
```

## Configuration (.env)

```bash
# Single RabbitMQ Connection
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Crawling Service Queues
RABBITMQ_CRAWLING_REQUEST_QUEUE=crawling_request_queue
RABBITMQ_CRAWLING_RESPONSE_QUEUE=crawling_response_queue

# AI Service Queue
AI_QUEUE_NAME=recipe_analysis_request
```

## Performance Characteristics

### Throughput
- **Crawling async requests:** ~1000/s (limited by queue throughput)
- **Crawling sync requests:** ~100/s (limited by processing time)
- **AI requests:** ~10/s (limited by AI service processing)

### Latency
- **Crawling async:** < 50ms (just enqueue)
- **Crawling sync:** 100ms - 5s (depends on crawling task)
- **AI recipe analysis:** 2-10s (depends on AI processing)
- **AI image analysis:** 5-15s (depends on image size + AI)

### Resource Usage
- **Connections:** 1 (shared)
- **Channels:** 2 (crawling + AI)
- **Threads:** 1 I/O thread + N Flask threads
- **Callback queues:** 1 (shared for all AI requests)

## Monitoring Points

### Health Checks
```python
# Check connection
connection.is_open

# Check last heartbeat
_last_heartbeat < datetime.now() - timedelta(minutes=2)

# Check I/O thread
_io_thread.is_alive()

# Check pending jobs
_publish_queue.qsize()
```

### Metrics to Track
- Request count per service
- Response time percentiles (p50, p95, p99)
- Timeout rate
- Queue depths
- Connection uptime
- Error rates

## Troubleshooting Guide

### Issue: Timeout on AI requests
**Check:**
1. Is AI Service running and connected?
2. Is callback queue created? (Look for log: "AI callback queue created")
3. Is `reply_to` property set? (Look for log: "AI request published")
4. Is correlation_id matching? (Check response handler logs)

### Issue: Crawling response not received
**Check:**
1. Is Crawling Service running?
2. Is `job_id` included in request?
3. Is response queue being consumed?
4. Check `_handle_crawling_response` logs

### Issue: Connection lost frequently
**Check:**
1. Network stability
2. RabbitMQ server health
3. Heartbeat timeout settings
4. Resource usage (memory, CPU)

---

**Document Version:** 1.0  
**Last Updated:** November 5, 2025  
**Status:** ✅ Current Implementation  
**Pattern:** RPC + Work Queue Hybrid
