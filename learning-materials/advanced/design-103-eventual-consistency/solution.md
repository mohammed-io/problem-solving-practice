# Solution: Eventual Consistency & Conflict Resolution

## Answers to Questions

### 1. When Should You Choose CRDTs Over LWW?

**Choose CRDTs when:**
- Data loss is unacceptable
- Automatic merge is required
- Operations are commutative (add/remove, increment)
- You can tolerate storage overhead

**Choose LWW when:**
- Last update should win (user intent)
- Storage overhead is critical
- Conflicts are rare
- Simple timestamps suffice

**Comparison:**
```
Shopping cart "add item" then "remove item":
- LWW: If clocks skewed, might keep OR remove item arbitrarily
- CRDT: Tombstone guarantees removal wins for tagged element

User profile "update email":
- LWW: Last timestamp wins (correct behavior)
- CRDT: Overkill for single-value register
```

---

### 2. What's the Storage Overhead of CRDTs?

**G-Counter:** O(N) where N = number of nodes
- Each node maintains one counter per replica
- 100 nodes → 100 counters per G-Counter

**OR-Set:** O(E × T) where E = elements, T = tags per element
- Each add operation generates unique tag
- Tombstones retained indefinitely
- Periodic compaction needed

**LWW-Register:** O(1) - just timestamp + value

**Is it worth it?**
- For counters: Yes - G-Counter overhead is minimal
- For sets: Maybe - OR-Set can grow large
- for registers: No - LWW is simpler

---

### 3. Handling "Remove" in Collaborative Editing

**Problem:** User A deletes line 5 while User B edits line 5

**Approaches:**

1. **CRDT RGA (Replicated Growable Array):**
   - Each character has unique ID
   - Deletions are tombstones
   - Concurrent edits preserved, then merged

2. **Yjs (CRDT framework):**
   - Uses Item CRDT for array positions
   - Deletes create tombstones
   - GC removes old tombstones

3. **OT (Operational Transformation):**
   - Transform operations against concurrent edits
   - Server or complex protocol required
   - Used by Google Docs

**Recommendation:** Use established CRDT library (Yjs, Automerge) rather than building from scratch.

---

### 4. Vector Clocks When Nodes Join/Leave

**Node joins:**
- Add new entry to vector clock: `{new_node: 0}`
- Existing clocks remain valid (partial order maintained)

**Node leaves permanently:**
- Compress vector clock by removing node
- Only safe after no events from that node remain

**Practical approaches:**
```python
# Compression: Remove nodes with max counter that haven't changed
def compress_vc(vc, active_nodes):
    return {node: count for node, count in vc.items()
            if node in active_nodes or count < max_vc_value(vc)}

# Or use version vectors (per-object, not per-cluster)
```

---

### 5. Global Collaboration Platform Design

**Recommended: AP with CRDTs**

```python
class CollaborationPlatform:
    """
    Architecture:
    - Multi-master writes in each region
    - CRDTs for automatic conflict resolution
    - Event sourcing for audit trail
    - Timeline consistency for user sessions
    """

    def __init__(self):
        # CRDT database for documents
        self.documents = AntidoteDB()  # CRDT database

        # Event log for audit/replay
        self.events = KafkaConnector()

        # Session store for timeline consistency
        self.sessions = RedisCluster()

    # Document as OR-Map (nested CRDTs)
    def edit_document(self, doc_id, user_id, changes):
        # Each edit is CRDT operation
        doc = self.documents.get(doc_id)

        for change in changes:
            if change.type == 'insert':
                doc.content.insert(change.position, change.text, user_id)
            elif change.type == 'delete':
                doc.content.delete(change.position, change.length, user_id)

        self.documents.put(doc_id, doc)
        self.events.publish('DocumentEdited', doc_id, user_id, changes)

    # Cursor position as LWW-Register (last update wins)
    def update_cursor(self, doc_id, user_id, position):
        cursor_key = f"cursor:{doc_id}:{user_id}"
        self.sessions.set(cursor_key, {
            'position': position,
            'timestamp': time.time()
        })
```

**Conflict resolution strategy:**
- Document content: CRDT (automatic merge)
- Cursor positions: LWW (last update wins)
- Document metadata: LWW (title, created_at)
- Permissions: CRDT OR-Set (add/remove)

---

## Key Takeaways

1. **CRDTs guarantee convergence** - mathematical property of commutative, associative, idempotent merge
2. **LWW is simpler but loses data** - acceptable for some use cases, not for others
3. **Vector clocks track causality** - essential for detecting concurrent operations
4. **Storage overhead is real** - plan for compaction and tombstone cleanup
5. **Use existing libraries** - building CRDTs from scratch is error-prone

---

## CRDT Type Selection Guide

| Use Case | CRDT Type | Example |
|----------|-----------|---------|
| Like counter | G-Counter | `likes = {A:5, B:3}` → value = 8 |
| Vote counter | PN-Counter | `votes = {A:5, B:-2}` → value = 3 |
| Shopping cart | OR-Set | Add/remove items with tags |
| User profile | LWW-Register | Last update wins |
| Document | OR-Map | Nested CRDTs for structure |
| Cursor position | LWW-Register | Last position wins |
| Tags | OR-Set | Add/remove tags with tombstones |
| Analytics | G-Counter | Increment-only metrics |
