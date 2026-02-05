---
name: design-101-idempotency
description: Idempotency key implementation
difficulty: Advanced
category: Distributed Systems / API Design
level: Principal Engineer
---
# Design 101: Idempotency Keys

---

## Tools & Prerequisites

To design and debug idempotency systems:

### Idempotency Storage Tools

| Tool | Purpose | Quick Usage |
|------|---------|-------------|
| **Redis** | Key-value store with TTL | `SET idem:uuid response_json EX 3600` |
| **Memcached** | Cached key-value | `set idem:uuid 0 3600 <bytes>` |
| **PostgreSQL** | Persistent storage | `INSERT INTO idempotency_keys (key, params, response) VALUES (...)` |
| **etcd** | Distributed KV store | `etcdctl put idem:uuid response --ttl 3600` |
| **DynamoDB** | NoSQL with TTL | `PutItem with TTL attribute` |

### Key Patterns

```python
# Redis-based idempotency check
def process_request(idempotency_key, request_data):
    # Check if key exists
    cached = redis.get(f"idem:{idempotency_key}")
    if cached:
        return json.loads(cached)  # Return cached response

    # Process request
    result = process_payment(request_data)

    # Store with TTL (24-48 hours)
    redis.setex(
        f"idem:{idempotency_key}",
        48 * 3600,  # 48 hours
        json.dumps(result)
    )

    return result

# Database-based with atomic check
def process_request_atomic(idempotency_key, request_data):
    # INSERT with ON CONFLICT (PostgreSQL)
    result = db.execute("""
        INSERT INTO idempotency_keys (key, request_hash, response)
        VALUES (%s, %s, %s)
        ON CONFLICT (key) DO UPDATE
        SET response = EXCLUDED.response
        RETURNING response
    """, (idempotency_key, hash_request(request_data), None))

    if result.response:
        return result.response  # Cached from previous

    # Process and update
    response = process_payment(request_data)
    db.execute("UPDATE idempotency_keys SET response = %s WHERE key = %s",
               (response, idempotency_key))
    return response
```

### Key Concepts

**Idempotency**: Property where operation can be applied multiple times with same result.

**Idempotency Key**: Unique client-generated identifier for request deduplication.

**Exactly-Once**: Processing guarantee that each request is handled exactly once.

**At-Least-Once**: Processing guarantee where each request is handled at least once (may retry).

**At-Most-Once**: Processing guarantee where each request is handled at most once (may drop).

**Request Hashing**: Hash of request parameters to detect parameter changes.

**TTL (Time To Live)**: Expiration time for idempotency key storage.

**Race Condition**: Two identical requests arriving simultaneously; both miss cache.

**Compare-And-Set**: Atomic operation preventing duplicate processing.

---

## Visual: Idempotency

### Idempotent vs Non-Idempotent

```mermaid
flowchart TB
    subgraph Idempotent ["✅ Idempotent Operations"]
        I1["GET /resource/123"]
        I2["PUT /resource/123 {name: 'X'}"]
        I3["DELETE /resource/123"]
        I4["Multiple calls = same result"]

        I1 --> I4
        I2 --> I4
        I3 --> I4
    end

    subgraph NonIdempotent ["❌ Non-Idempotent Operations"]
        N1["POST /payments"]
        N2["POST /orders"]
        N3["PATCH /counter {op: 'increment'}"]
        N4["Multiple calls = different results!"]

        N1 --> N4
        N2 --> N4
        N3 --> N4
    end

    style Idempotent fill:#c8e6c9
    style NonIdempotent fill:#ffcdd2
```

### Request Retry Flow

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Server
    participant Payment as Payment Gateway
    participant Cache as Idempotency Cache

    Client->>Server: POST /payments<br/>Idempotency-Key: abc-123
    Server->>Cache: Check key "abc-123"
    Cache-->>Server: Not found

    Server->>Payment: Charge $100
    Payment-->>Server: ✅ Success

    Server->>Cache: Store response<br/>key: abc-123, ttl: 48h
    Server-->>Client: 200 OK + payment_id

    Note over Client: Network error! Response lost

    Client->>Server: RETRY POST /payments<br/>Idempotency-Key: abc-123
    Server->>Cache: Check key "abc-123"
    Cache-->>Server: ✅ Found!

    Server-->>Client: 200 OK + same payment_id<br/>(Not charged again!)
```

### Race Condition Problem

```mermaid
sequenceDiagram
    autonumber
    participant C1 as Client Request 1
    participant C2 as Client Request 2 (retry)
    participant Server
    participant Cache as Idempotency Cache

    Note over C1,Cache: Both requests sent simultaneously

    par Parallel requests
        C1->>Cache: Check key abc-123
        C2->>Cache: Check key abc-123
    end

    Cache-->>C1: Not found
    Cache-->>C2: Not found

    Note over Server: Both proceed to process!

    par Both process
        C1->>Server: Process payment
        C2->>Server: Process payment
    end

    Server->>Server: ❌ Charged twice!
```

### Atomic Check-and-Set Solution

```mermaid
sequenceDiagram
    autonumber
    participant C1 as Client Request 1
    participant C2 as Client Request 2
    participant DB as Database

    par Both attempt atomic insert
        C1->>DB: INSERT INTO idempotency<br/>(key='abc-123', processing=true)
        C2->>DB: INSERT INTO idempotency<br/>(key='abc-123', processing=true)
    end

    DB->>C1: ✅ Inserted (first)
    DB->>C2: ❌ Conflict (duplicate key)

    C1->>DB: Process payment
    C1->>DB: UPDATE idempotency SET response='...'

    C2->>DB: SELECT response FROM idempotency WHERE key='abc-123'
    DB-->>C2: Returns cached response

    Note over C1,C2: Only one charge!
```

### Idempotency Key Storage Options

```mermaid
flowchart TB
    subgraph Redis ["Redis (In-Memory)"]
        R1["✅ Fast lookups"]
        R2["✅ Built-in TTL"]
        R3["❌ Data loss on restart"]
        R4["❌ Memory limited"]
    end

    subgraph Database ["PostgreSQL (Persistent)"]
        D1["✅ Durable"]
        D2["✅ Indexed lookups"]
        D3["❌ Slower than Redis"]
        D4["✅ Can join with data"]
    end

    subgraph Hybrid ["Hybrid Approach"]
        H1["Redis: Hot cache (recent keys)"]
        H2["DB: Persistent storage"]
        H3["✅ Fast + durable"]
    end

    style Redis fill:#e1f5fe
    style Database fill:#c8e6c9
    style Hybrid fill:#fff3e0
```

### Parameter Change Handling

```mermaid
flowchart TB
    subgraph Problem ["❌ Same Key, Different Body"]
        P1["Request 1: key='abc-123'<br/>amount: 100"]
        P2["Request 2: key='abc-123'<br/>amount: 200"]
        P3["Returns cached response from Request 1"]
        P4["❌ Wrong amount charged!"]

        P1 --> P3
        P2 --> P3
        P3 --> P4
    end

    subgraph Solution ["✅ Include Body in Key or Hash"]
        S1["Request 1: key='abc-123'<br/>hash: hash(body)"]
        S2["Request 2: key='abc-123'<br/>hash: hash(different body)"]
        S3["Different hash = different key"]
        S4["✅ Processed separately"]

        S1 --> S3
        S2 --> S3
        S3 --> S4
    end

    style Problem fill:#ffcdd2
    style Solution fill:#c8e6c9
```

### Processing Guarantees

```mermaid
flowchart LR
    subgraph AtMostOnce ["At-Most-Once"]
        AM1["May drop requests"]
        AM2["Never duplicates"]
        AM3["❌ Data loss possible"]
    end

    subgraph AtLeastOnce ["At-Least-Once"]
        AL1["May duplicate"]
        AL2["Never drops"]
        AL3["✅ Requires deduplication"]
    end

    subgraph ExactlyOnce ["Exactly-Once"]
        EO1["No duplicates"]
        EO2["No drops"]
        EO3["✅ Idempotency + retries"]

        AL1 --> EO1
    end

    style AtMostOnce fill:#ffcdd2
    style AtLeastOnce fill:#fff3e0
    style ExactlyOnce fill:#c8e6c9
```

### Idempotency Key Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: Request received

    Pending --> Processing: Check cache (miss)
    Processing --> Completed: Process successfully
    Processing --> Failed: Process failed

    Completed --> Cached: Store response
    Failed --> Cached: Store error response

    Cached --> Expired: TTL expires (24-48h)
    Cached --> Cached: Subsequent requests return cached

    Expired --> [*]

    note right of Cached
        Same idempotency key
        Returns same response
        Prevents duplicate processing
    end note
```

### Storage Schema Design

```mermaid
flowchart TB
    subgraph Schema ["Idempotency Keys Table"]
        Table["idempotency_keys"]
        Key["key VARCHAR(255) PRIMARY KEY"]
        Params["request_params JSONB"]
        Response["response JSONB"]
        Created["created_at TIMESTAMPTZ"]
        Expires["expires_at TIMESTAMPTZ"]

        Key --> Table
        Params --> Table
        Response --> Table
        Created --> Table
        Expires --> Table
    end

    subgraph Index ["Indexes"]
        IDX1["INDEX on expires_at (for cleanup)"]
        IDX2["INDEX on created_at (for lookups)"]
    end

    Table --> IDX1
    Table --> IDX2

    style Table fill:#e8f5e9
```

---

## The Requirement

Design an idempotency system for payment APIs:

**Requirements:**
1. Client can retry requests safely
2. Same request processed only once
3. Client receives same response for retries
4. Idempotency keys expire after 24-48 hours

**Example:**
```http
POST /payments
Idempotency-Key: uuid-v4
Authorization: Bearer secret_key

{ "amount": 1000, "currency": "usd" }
```

---

## What is Idempotency?

**Idempotent operation:** Can be applied multiple times with same result.

**Mathematical definition:** f(f(x)) = f(x)

**Examples:**
- **Idempotent:** GET request, SET x=5, DELETE /resource/123
- **Not idempotent:** POST creating resource, POST charging payment, x++

**In APIs:** Retrying same request should not charge twice, create duplicate records, etc.

---

## The Challenge

```
Client sends payment request with key "abc-123"
→ Server processes, charges card, returns response
→ Network error, client doesn't receive response
→ Client retries with same key "abc-123"
→ Server should NOT charge again!
→ Should return cached response from first attempt
```

---

## Questions

1. **Where do you store idempotency keys?** (Memory, Redis, Database - trade-offs)

2. **How do you handle race conditions?** (Atomic check-and-set, database constraints)

3. **How do you expire old keys?** (TTL, cleanup job)

4. **What if request parameters change?** (Include in hash or reject)

5. **As a Principal Engineer, how do you design for correctness at scale?**

---

## Learning Path

```
step-01.md → The Idempotency Problem
step-02.md → Storage Options and Basic Design
step-03.md → Atomic Check-and-Set
step-04.md → Handling Parameter Changes
step-05.md → Production Concerns
solution.md → Complete Solution
```

---

**When you have a design, read `step-01.md`**
