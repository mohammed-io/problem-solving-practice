# Step 02: CAP in Practice - Real Engineering Decisions

---

## Netflix: AP with Cassandra

**The decision:** Netflix migrated from Oracle (CA) to Cassandra (AP) for streaming metadata.

```go
// Netflix's tunable consistency approach
type NetflixMetadata struct {
    session *gocql.Session
}

func (n *NetflixMetadata) GetUserProfile(ctx context.Context, userID string) (*Profile, error) {
    // User profile: QUORUM - privacy critical
    // R + W > N for strong consistency
    var profile Profile
    err := n.session.Query(`
        SELECT * FROM profiles WHERE user_id = ?
    `, userID).Consistency(gocql.Quorum).Scan(&profile)

    return &profile, err
}

func (n *NetflixMetadata) GetViewingHistory(ctx context.Context, userID string) ([]*Viewing, error) {
    // Viewing history: LOCAL_QUORUM - acceptable staleness
    var history []*Viewing
    err := n.session.Query(`
        SELECT * FROM history WHERE user_id = ?
    `, userID).Consistency(gocql.LocalQuorum).Select(&history)

    return history, err
}

func (n *NetflixMetadata) RecordView(ctx context.Context, userID, titleID string) error {
    // Record view: ONE - high volume, acceptable loss
    return n.session.Query(`
        INSERT INTO history (user_id, title_id, timestamp)
        VALUES (?, ?, toTimestamp(now()))
    `, userID, titleID).Consistency(gocql.One).Exec()
}

func (n *NetflixMetadata) GetRecommendations(ctx context.Context, userID string) ([]*Recommendation, error) {
    // Recommendations: ONE - precomputed, stale OK
    var recs []*Recommendation
    err := n.session.Query(`
        SELECT * FROM recommendations WHERE user_id = ?
    `, userID).Consistency(gocql.One).Select(&recs)

    return recs, err
}
```

**Key insight:** Netflix uses **different consistency levels for different data types**.

---

## The NRW Formula

**For consistency:** R + W > N

Where:
- **N** = Replication factor (total replicas)
- **R** = Number of nodes queried for read
- **W** = Number of nodes that must acknowledge write

```go
type ConsistencyLevel int

const (
    One      ConsistencyLevel = 1
    Quorum   ConsistencyLevel = 0 // Calculated as N/2 + 1
    All      ConsistencyLevel = 1 // All nodes
)

func IsStronglyConsistent(N int, R, W int) bool {
    return R + W > N
}

// Examples:
// N = 3 replicas
// W = 2, R = 2: 2 + 2 > 3 ✓ Strongly consistent
// W = 1, R = 1: 1 + 1 < 3 ✗ Eventual consistency
```

---

## DynamoDB: Configurable Consistency

```go
import (
    "context"
    "github.com/aws/aws-sdk-go-v2/service/dynamodb"
)

type DynamoDBClient struct {
    client *dynamodb.Client
}

func (d *DynamoDBClient) WriteStrong(ctx context.Context, table, key string, value []byte) error {
    // CP write: Slower, durable
    _, err := d.client.PutItem(ctx, &dynamodb.PutItemInput{
        TableName: aws.String(table),
        Item: map[string]types.AttributeValue{
            "id":   &types.AttributeValueMemberS{Value: key},
            "data": &types.AttributeValueMemberB{Value: value},
        },
    })

    return err
}

func (d *DynamoDBClient) WriteFast(ctx context.Context, table, key string, value []byte) error {
    // AP write: Fast, potentially lost
    _, err := d.client.PutItem(ctx, &dynamodb.PutItemInput{
        TableName: aws.String(table),
        Item: map[string]types.AttributeValue{
            "id":   &types.AttributeValueMemberS{Value: key},
            "data": &types.AttributeValueMemberB{Value: value},
        },
    })

    return err
}

func (d *DynamoDBClient) ReadConsistent(ctx context.Context, table, key string) ([]byte, error) {
    // CP read: Slower, consistent
    resp, err := d.client.GetItem(ctx, &dynamodb.GetItemInput{
        TableName:        aws.String(table),
        Key:              map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: key}},
        ConsistentRead:   aws.Bool(true), // Quorum read!
    })

    if err != nil {
        return nil, err
    }

    return resp.Item["data"].(*types.AttributeValueMemberB).Value, nil
}

func (d *DynamoDBClient) ReadFast(ctx context.Context, table, key string) ([]byte, error) {
    // AP read: Fast, may be stale
    resp, err := d.client.GetItem(ctx, &dynamodb.GetItemInput{
        TableName:        aws.String(table),
        Key:              map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: key}},
        ConsistentRead:   aws.Bool(false), // Default: eventual
    })

    if err != nil {
        return nil, err
    }

    return resp.Item["data"].(*types.AttributeValueMemberB).Value, nil
}
```

---

## Multi-Database Architecture

```go
// Different CAP choices for different services
type MultiDatabaseService struct {
    // CP: Payment processing
    paymentsDB *sql.DB // PostgreSQL with serializable isolation

    // AP: Social feed
    feedDB *gocql.Session // Cassandra with ONE consistency

    // Timeline: Shopping cart (user sees own changes)
    cartCache *redis.Client
    cartDB    *sql.DB

    // CP: Configuration
    config *clientv3.Client // etcd for strong consistency
}

func (s *MultiDatabaseService) CreatePayment(ctx context.Context, userID string, amount int) error {
    // CP: Strong consistency required
    tx, err := s.paymentsDB.BeginTx(ctx, &sql.TxOptions{
        Isolation: sql.LevelSerializable,
    })
    if err != nil {
        return err
    }
    defer tx.Rollback()

    var balance int
    err = tx.QueryRowContext(ctx, "SELECT balance FROM accounts WHERE id = $1 FOR UPDATE", userID).Scan(&balance)
    if err != nil {
        return err
    }

    if balance < amount {
        return fmt.Errorf("insufficient funds")
    }

    _, err = tx.ExecContext(ctx, "UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, userID)
    if err != nil {
        return err
    }

    return tx.Commit()
}

func (s *MultiDatabaseService) GetFeed(ctx context.Context, userID string) ([]byte, error) {
    // AP: Stale data acceptable
    // Try local cache first
    cached, err := s.cartCache.Get(ctx, "feed:"+userID).Result()
    if err == redis.Nil {
        // Build from Cassandra
        var feed []byte
        err = s.feedDB.Query(`
            SELECT * FROM user_feed WHERE user_id = ?
        `, userID).Consistency(gocql.One).Scan(&feed)
        return feed, err
    }

    return []byte(cached), nil
}

func (s *MultiDatabaseService) AddToCart(ctx context.Context, userID, itemID string, qty int) error {
    // Timeline: User sees their own changes
    key := fmt.Sprintf("cart:%s", userID)

    // Write to local Redis (session consistency)
    s.cartCache.HSet(ctx, key, itemID, qty)

    // Async: persist to PostgreSQL
    go func() {
        _, err := s.cartDB.Exec(
            "INSERT INTO cart_items (user_id, item_id, quantity) VALUES ($1, $2, $3)",
            userID, itemID, qty,
        )
        if err != nil {
            log.Printf("Failed to persist cart: %v", err)
        }
    }()

    return nil
}

func (s *MultiDatabaseService) GetFeatureFlag(ctx context.Context, flagName string) (bool, error) {
    // CP: All servers must agree
    resp, err := s.config.Get(ctx, "/flags/"+flagName)
    if err != nil {
        return false, err
    }

    return strconv.ParseBool(string(resp.Value))
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What is the NRW formula? (R + W > N for consistency)
2. How does DynamoDB achieve both AP and CP? (Configurable R/W per query)
3. Why mix different databases? (Different CAP needs per data type)
4. What's timeline consistency? (User sees own writes, others may see stale)
5. When should you use CP vs AP? (CP for financial, AP for social)

---

## CAP Decision Matrix

| Use Case | Consistency | Availability | Example System |
|----------|-------------|---------------|----------------|
| Payments | **Required** | Degraded OK | PostgreSQL (CP) |
| Inventory | **Required** | Degraded OK | MongoDB (CP) |
| Social Feed | Optional | **Required** | Cassandra (AP) |
| Analytics | Optional | **Required** | BigQuery (AP) |
| Config | **Required** | Degraded OK | etcd (CP) |
| Shopping Cart | Timeline | **Required** | Redis + DB (Hybrid) |

---

**Proceed to `solution.md`**
