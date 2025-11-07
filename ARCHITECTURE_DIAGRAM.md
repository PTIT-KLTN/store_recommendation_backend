# Single I/O Thread Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Flask Application                            │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ HTTP Request │  │ HTTP Request │  │ HTTP Request │              │
│  │   Thread 1   │  │   Thread 2   │  │   Thread 3   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                       │
│         └──────────────────┼──────────────────┘                       │
│                            │                                          │
│                            ▼                                          │
│                   ┌─────────────────┐                                │
│                   │ RabbitMQService │                                │
│                   │                 │                                │
│                   │  Thread-Safe    │                                │
│                   │  Job Submission │                                │
│                   └────────┬────────┘                                │
│                            │                                          │
│                            ▼                                          │
│                  ┌──────────────────┐                                │
│                  │ _publish_queue   │ ◄─── Thread-Safe Queue         │
│                  │  (queue.Queue)   │                                │
│                  └────────┬─────────┘                                │
│                           │                                           │
│                           ▼                                           │
│           ┌────────────────────────────────┐                         │
│           │   Single I/O Thread            │                         │
│           │   (_io_loop)                   │                         │
│           │                                │                         │
│           │  1. process_data_events()      │ ◄─── ONLY thread        │
│           │  2. Process publish jobs       │      touching pika      │
│           │  3. Handle responses           │                         │
│           └────────┬───────────────────────┘                         │
│                    │                                                  │
└────────────────────┼──────────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   RabbitMQ Server     │
         │                       │
         │  ┌─────────────────┐ │
         │  │ Crawling Queues │ │
         │  │  - Request      │ │
         │  │  - Response     │ │
         │  └─────────────────┘ │
         │                       │
         │  ┌─────────────────┐ │
         │  │ AI Queues       │ │
         │  │  - Request      │ │
         │  │  - Callbacks    │ │
         │  └─────────────────┘ │
         └───────┬───────────────┘
                 │
                 ▼
      ┌──────────────────────┐
      │  External Services   │
      │  - Crawling Service  │
      │  - AI Service        │
      └──────────────────────┘
```

## Request Flow - Crawling Service

```
Flask Handler Thread                 I/O Thread                    RabbitMQ
──────────────────────              ──────────                    ─────────
      │                                 │                             │
      │ 1. send_request()               │                             │
      ├────────────────────┐            │                             │
      │ Create job dict    │            │                             │
      └────────────────────┘            │                             │
      │                                 │                             │
      │ 2. _publish_queue.put(job) ────►│                             │
      │                                 │                             │
      │ [For sync requests]             │ 3. _execute_publish_job()   │
      │ 3. future['event'].wait() ──┐   ├────────────────────────────►│
      │                             │   │ channel.basic_publish()     │
      │                             │   │                             │
      │                             │   │                             │
      │                             │   │ 4. Response arrives         │
      │                             │   │◄────────────────────────────┤
      │                             │   │                             │
      │                             │   │ 5. _handle_response()       │
      │                             │   ├──────────────────┐          │
      │                             │   │ future['result'] = data     │
      │                             │   │ future['event'].set() ──┐   │
      │                             │   └─────────────────────────┘   │
      │                             │                             │   │
      │ 6. Event triggered! ◄───────┼─────────────────────────────┘   │
      │    Return result            │                             │   │
      └─────────────────────────────┘                             │   │
```

## Request Flow - AI Service

```
Flask Handler Thread                 I/O Thread                    RabbitMQ
──────────────────────              ──────────                    ─────────
      │                                 │                             │
      │ 1. send_ai_request()            │                             │
      ├────────────────────┐            │                             │
      │ Create job dict    │            │                             │
      │ correlation_id     │            │                             │
      └────────────────────┘            │                             │
      │                                 │                             │
      │ 2. _publish_queue.put(job) ────►│                             │
      │                                 │                             │
      │ 3. future['event'].wait() ──┐   │ 4. _execute_publish_job()   │
      │                             │   ├────────────────┐            │
      │                             │   │ Create callback│            │
      │                             │   │ queue          │            │
      │                             │   │ Setup consumer │            │
      │                             │   └────────────────┘            │
      │                             │   │                             │
      │                             │   │ ai_channel.basic_publish() ─►│
      │                             │   │ (with reply_to callback)    │
      │                             │   │                             │
      │                             │   │ [AI Service processes...]   │
      │                             │   │                             │
      │                             │   │ Response to callback queue  │
      │                             │   │◄────────────────────────────┤
      │                             │   │                             │
      │                             │   │ 5. _handle_ai_response()    │
      │                             │   ├──────────────────┐          │
      │                             │   │ future['result'] = data     │
      │                             │   │ future['event'].set() ──┐   │
      │                             │   └─────────────────────────┘   │
      │                             │                             │   │
      │ 6. Event triggered! ◄───────┼─────────────────────────────┘   │
      │    Return result            │                             │   │
      └─────────────────────────────┘                             │   │
```

## Thread Safety Mechanism

```
┌─────────────────────────────────────────────────────────────┐
│                    Thread Safety Layers                      │
└─────────────────────────────────────────────────────────────┘

Layer 1: Job Submission (Thread-Safe Queue)
─────────────────────────────────────────
   Flask Thread 1 ──►│              │
   Flask Thread 2 ──►│ queue.Queue  │──► I/O Thread (only reader)
   Flask Thread 3 ──►│              │
                     └──────────────┘
                     ✅ Thread-safe by Python

Layer 2: Response Synchronization (Event)
──────────────────────────────────────────
   Flask Thread ───► future = {
                       'result': None,
                       'event': Event()  ◄─── Thread-safe primitive
                     }
                     
   I/O Thread ─────► future['event'].set()
   Flask Thread ───► future['event'].wait()
                     ✅ Thread-safe by Python

Layer 3: Pika Operations (Single Thread)
─────────────────────────────────────────
   I/O Thread ONLY ──► process_data_events()
                    ──► basic_publish()
                    ──► queue_declare()
                    ──► basic_consume()
                     ✅ No concurrent access = No race conditions

Layer 4: Shared Data (Lock Protection)
───────────────────────────────────────
   with self._lock:  ◄─── threading.Lock()
       self.response_futures[correlation_id] = future
       self.ai_callback_queues[correlation_id] = {...}
                     ✅ Protected by lock
```

## Component Interaction

```
┌──────────────────────────────────────────────────────────────┐
│                  RabbitMQService Internal                     │
│                                                               │
│  ┌─────────────┐                                             │
│  │ Public API  │                                             │
│  │ (Thread-Safe)│                                            │
│  ├─────────────┤                                             │
│  │ send_request                                              │
│  │ send_async_request                                        │
│  │ send_ai_request        ┌──────────────────┐              │
│  │ send_ai_image_request  │  _publish_queue  │              │
│  └──────┬──────────────────►  (queue.Queue)  │              │
│         │                  └────────┬─────────┘              │
│         │                           │                        │
│         │                           ▼                        │
│         │                  ┌──────────────────┐              │
│         │                  │    _io_loop()    │              │
│         │                  ├──────────────────┤              │
│         │                  │ process_data_    │              │
│         │                  │   events()       │              │
│         │                  │                  │              │
│         │                  │ _execute_        │              │
│         │                  │   publish_job()  │              │
│         │                  └────────┬─────────┘              │
│         │                           │                        │
│         │                           ▼                        │
│         │                  ┌──────────────────┐              │
│         │                  │  pika Connection │              │
│         │                  │  2 Channels:     │              │
│         │                  │  - channel       │              │
│         │                  │  - ai_channel    │              │
│         │                  └──────────────────┘              │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────┐                                        │
│  │ response_futures│ ◄── Protected by self._lock            │
│  │ (correlation_id │                                        │
│  │  → future dict) │                                        │
│  └─────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

## Data Structures

```python
# Job Structure
job = {
    'type': 'crawling_request' | 'ai_request',
    'correlation_id': 'uuid-string',  # For AI requests
    'routing_key': 'queue_name',
    'body': b'json_bytes',
    'properties': pika.BasicProperties(...)
}

# Future Structure
future = {
    'result': None | response_data,
    'event': threading.Event(),
    'created_at': datetime.now()
}

# Callback Queue Info (AI only)
callback_queue_info = {
    'queue': 'amq.gen-xxx',  # Exclusive queue name
    'consumer_tag': 'ctag1.xxx'  # Consumer identifier
}
```

## Synchronization Pattern

```
┌────────────────────────────────────────────────────────────┐
│              Event-Based Synchronization                    │
└────────────────────────────────────────────────────────────┘

Flask Handler Thread          I/O Thread
────────────────────          ──────────

1. Create Event
   event = Event()
   future = {
     'result': None,
     'event': event
   }

2. Submit job
   _publish_queue.put(job)
                              3. Get job
                                 job = queue.get()
   
4. Wait (blocking)            4. Publish to RabbitMQ
   event.wait(timeout=100)       channel.basic_publish()
   
   │                          5. Response arrives
   │                             process_data_events()
   │                             
   │                          6. Set result & trigger
   │                             future['result'] = data
   │                             event.set() ───────────┐
   │                                                     │
5. Woken up! ◄────────────────────────────────────────────┘
   return future['result']
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Scenarios                           │
└─────────────────────────────────────────────────────────────┘

Scenario 1: Timeout
───────────────────
Flask Thread                  I/O Thread
    │                             │
    │ event.wait(timeout=100)     │ (No response received)
    │                             │
    │ (100s elapsed)              │
    ▼                             │
    TimeoutError raised           │
    Clean up future               │
    Return error to client        │

Scenario 2: Connection Lost
────────────────────────────
    │                             │
    │                             │ Connection.is_closed
    │                             ▼
    │                             Skip process_data_events()
    │                             Attempt reconnect
    │                             │
    │ (Still waiting)             │ (Reconnected)
    │                             ▼
    │                             Continue processing
    ▼                             │

Scenario 3: Service Not Responding
───────────────────────────────────
    │                             │
    │                             │ Publish successful
    │                             │ (But AI service down)
    │                             ▼
    │                             No response
    │                             │
    │ (Timeout after 100s)        │
    ▼                             │
    TimeoutError                  │
    Clean up resources            │
```

## Benefits Visualization

```
┌─────────────────────────────────────────────────────────────┐
│                  Before vs After                             │
└─────────────────────────────────────────────────────────────┘

Before (Multiple Threads):
──────────────────────────
Thread 1 ──┐
Thread 2 ──┼──► pika Connection ──► ❌ Race Conditions
Thread 3 ──┘                          ❌ StreamLostError
                                       ❌ State Corruption

After (Single I/O Thread):
──────────────────────────
Thread 1 ──┐
Thread 2 ──┼──► Queue ──► I/O Thread ──► pika Connection ──► ✅ Thread-Safe
Thread 3 ──┘                                                   ✅ No Races
                                                                ✅ Stable
```

---

## Legend

```
──►  : Data flow
│    : Vertical connection
┐└┤├ : Box corners
◄────: Callback/Response
┌───┐: Component box
◄──►: Bidirectional
```

---

**Visual Guide Complete!**

This diagram helps understand:
1. System architecture
2. Thread interactions
3. Data flow
4. Synchronization mechanisms
5. Error handling
6. Benefits of the new pattern

Use this alongside `SINGLE_IO_THREAD_IMPLEMENTATION.md` for complete understanding.
