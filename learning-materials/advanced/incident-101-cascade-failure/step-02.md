# Step 2: Circuit Breakers and Bulkheads

---

## Circuit Breaker Pattern

Like an electrical circuit breaker: Opens when fault detected, stops sending traffic.

```
    Closed (normal) ──[too many failures]──> Open (failing)
        ↑                                         │
        │                                         │ [timeout passes]
        └────────────[half-open: test]────────────┘
```

---

## Circuit Breaker in Go

```go
package circuitbreaker

import (
    "context"
    "errors"
    "fmt"
    "sync"
    "time"
)

type State int

const (
    StateClosed State = iota
    StateOpen
    StateHalfOpen
)

func (s State) String() string {
    switch s {
    case StateClosed:
        return "closed"
    case StateOpen:
        return "open"
    case StateHalfOpen:
        return "half-open"
    default:
        return "unknown"
    }
}

type CircuitBreaker struct {
    mu                sync.RWMutex
    maxRequests       uint32         // Max requests in half-open
    failureRatio      float64         // Failure ratio threshold (0.0 - 1.0)
    interval          time.Duration  // Rolling interval for metrics
    timeout           time.Duration  // How long to wait before half-open
    readyToTrip       func(counts Counts) bool
    onStateChange     func(from, to State)

    state          State
    generation     uint64         // Current generation (increments on state change)
    counts         Counts         // Current counts
    expiry         time.Time      // When to clear counts
    lastStateTime  time.Time      // When state last changed
}

type Counts struct {
    Requests         uint32
    TotalSuccesses   uint32
    TotalFailures    uint32
    ConsecutiveSuccesses uint32
    ConsecutiveFailures  uint32
}

func (c Counts) FillFrom(other Counts) {
    c.Requests = other.Requests
    c.TotalSuccesses = other.TotalSuccesses
    c.TotalFailures = other.TotalFailures
    c.ConsecutiveSuccesses = other.ConsecutiveSuccesses
    c.ConsecutiveFailures = other.ConsecutiveFailures
}

// NewCircuitBreaker creates a new circuit breaker
func NewCircuitBreaker(opts ...Option) *CircuitBreaker {
    cb := &CircuitBreaker{
        state:       StateClosed,
        generation:  1,
    }

    for _, opt := range opts {
        opt(cb)
    }

    // Set defaults
    if cb.maxRequests == 0 {
        cb.maxRequests = 1
    }
    if cb.interval == 0 {
        cb.interval = 10 * time.Second
    }
    if cb.timeout == 0 {
        cb.timeout = 60 * time.Second
    }
    if cb.readyToTrip == nil {
        cb.readyToTrip = func(counts Counts) bool {
            failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
            return counts.Requests >= 5 && failureRatio >= 0.5
        }
    }

    return cb
}

type Option func(*CircuitBreaker)

func WithMaxRequests(n uint32) Option {
    return func(cb *CircuitBreaker) { cb.maxRequests = n }
}

func WithFailureRatio(ratio float64) Option {
    return func(cb *CircuitBreaker) {
        cb.readyToTrip = func(counts Counts) bool {
            failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
            return counts.Requests >= 5 && failureRatio >= ratio
        }
    }
}

func WithInterval(interval time.Duration) Option {
    return func(cb *CircuitBreaker) { cb.interval = interval }
}

func WithTimeout(timeout time.Duration) Option {
    return func(cb *CircuitBreaker) { cb.timeout = timeout }
}

func WithOnStateChange(fn func(from, to State)) Option {
    return func(cb *CircuitBreaker) { cb.onStateChange = fn }
}

var (
    ErrOpenState = errors.New("circuit breaker is open")
)

// Execute runs the given function if the circuit breaker allows it
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) error {
    generation, err := cb.allow()
    if err != nil {
        return err
    }

    defer cb.onDone(generation, err)

    return fn()
}

func (cb *CircuitBreaker) allow() (uint64, error) {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    now := time.Now()
    state, expiry := cb.currentState(now)

    if state == StateOpen {
        // Check if we should transition to half-open
        if now.After(expiry) {
            cb.setState(StateHalfOpen, now)
            return cb.generation, nil
        }
        return 0, ErrOpenState
    }

    if state == StateHalfOpen && cb.counts.Requests >= cb.maxRequests {
        return 0, ErrOpenState
    }

    cb.counts.Requests++
    return cb.generation, nil
}

func (cb *CircuitBreaker) onDone(generation uint64, err error) {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    now := time.Now()
    if generation != cb.generation {
        return
    }

    if err != nil {
        cb.counts.TotalFailures++
        cb.counts.ConsecutiveFailures++
        if cb.readyToTrip(cb.counts) {
            cb.setState(StateOpen, now)
        }
    } else {
        cb.counts.TotalSuccesses++
        cb.counts.ConsecutiveSuccesses++
        if cb.state == StateHalfOpen && cb.counts.ConsecutiveSuccesses >= cb.maxRequests {
            cb.setState(StateClosed, now)
        }
    }
}

func (cb *CircuitBreaker) currentState(now time.Time) (State, time.Time) {
    switch cb.state {
    case StateClosed:
        if now.After(cb.expiry) {
            cb.counts.FillFrom(Counts{})
            cb.expiry = now.Add(cb.interval)
        }
    case StateOpen:
        return cb.state, cb.lastStateTime.Add(cb.timeout)
    }
    return cb.state, cb.expiry
}

func (cb *CircuitBreaker) setState(state State, now time.Time) {
    if cb.state == state {
        return
    }

    prevState := cb.state
    cb.state = state
    cb.lastStateTime = now
    cb.generation++

    now = time.Now()
    switch state {
    case StateClosed:
        cb.expiry = now.Add(cb.interval)
    case StateOpen:
        cb.expiry = now.Add(cb.timeout)
    case StateHalfOpen:
        cb.expiry = time.Time{} // No expiry in half-open
    }

    cb.counts.FillFrom(Counts{})

    if cb.onStateChange != nil {
        cb.onStateChange(prevState, state)
    }
}

func (cb *CircuitBreaker) State() State {
    cb.mu.RLock()
    defer cb.mu.RUnlock()
    return cb.state
}

// String representation for debugging
func (cb *CircuitBreaker) String() string {
    cb.mu.RLock()
    defer cb.mu.RUnlock()

    return fmt.Sprintf("CircuitBreaker{state=%s, generation=%d, counts=%+v}",
        cb.state, cb.generation, cb.counts)
}
```

---

## Usage Example

```go
package main

import (
    "context"
    "fmt"
    "net/http"
    "time"

    "github.com/yourmodule/circuitbreaker"
)

type Service struct {
    client *http.Client
    cb     *circuitbreaker.CircuitBreaker
}

func NewService() *Service {
    cb := circuitbreaker.NewCircuitBreaker(
        circuitbreaker.WithMaxRequests(3),
        circuitbreaker.WithFailureRatio(0.5),
        circuitbreaker.WithInterval(10*time.Second),
        circuitbreaker.WithTimeout(60*time.Second),
        circuitbreaker.WithOnStateChange(func(from, to circuitbreaker.State) {
            fmt.Printf("Circuit breaker state changed: %s -> %s\n", from, to)
        }),
    )

    return &Service{
        client: &http.Client{Timeout: 5 * time.Second},
        cb:     cb,
    }
}

func (s *Service) CallServiceA(ctx context.Context) error {
    err := s.cb.Execute(ctx, func() error {
        resp, err := s.client.Get("http://service-a/api/orders")
        if err != nil {
            return err
        }
        defer resp.Body.Close()

        if resp.StatusCode >= 500 {
            return fmt.Errorf("server error: %d", resp.StatusCode)
        }
        return nil
    })

    if errors.Is(err, circuitbreaker.ErrOpenState) {
        // Circuit breaker is open - return degraded response
        return fmt.Errorf("service temporarily unavailable (circuit open)")
    }

    return err
}
```

---

## Bulkhead Pattern

Isolate components so one failure doesn't affect others.

```go
package bulkhead

import (
    "context"
    "errors"
    "sync"
)

var (
    ErrBulkheadOverflow = errors.New("bulkhead: too many concurrent operations")
)

type Bulkhead struct {
    max   int
    mu    sync.Mutex
    count int
    wait  chan struct{}
}

func NewBulkhead(max int) *Bulkhead {
    return &Bulkhead{
        max:  max,
        wait: make(chan struct{}, max),
    }
}

func (b *Bulkhead) Do(ctx context.Context, fn func() error) error {
    select {
    case b.wait <- struct{}{}:
        // Acquired
        defer func() { <-b.wait }()
    case <-ctx.Done():
        return ctx.Err()
    default:
        // Bulkhead is full
        return ErrBulkheadOverflow
    }

    return fn()
}

// Example: Separate connection pools
type ServicePools struct {
    serviceA *Bulkhead
    serviceB *Bulkhead
    serviceC *Bulkhead
}

func NewServicePools() *ServicePools {
    return &ServicePools{
        serviceA: NewBulkhead(50), // Service A gets 50 connections
        serviceB: NewBulkhead(50), // Service B gets 50 connections
        serviceC: NewBulkhead(50), // Service C gets 50 connections
    }
}

func (p *ServicePools) CallA(ctx context.Context, fn func() error) error {
    return p.serviceA.Do(ctx, fn)
}
```

**Also: Thread pools, queue limits, memory limits per service.**

---

## Summary: Patterns Comparison

| Pattern | Purpose | Trade-off |
|---------|---------|-----------|
| Circuit Breaker | Stop calling failing service | Temporary unavailability |
| Bulkhead | Isolate resource pools | Potential queueing delay |
| Retry | Handle transient failures | Can amplify overload |
| Timeout | Prevent hanging requests | May cut off slow valid requests |

---

## Quick Check

Before moving on, make sure you understand:

1. What is a circuit breaker? (Stops sending traffic to failing service)
2. What are the three states? (Closed, Open, Half-open)
3. How does half-open work? (Allow one request to test if service recovered)
4. What is the bulkhead pattern? (Isolate resource pools to prevent cascading failure)
5. Why use both circuit breaker and bulkhead? (CB protects downstream, bulkhead protects upstream)

---

**Continue to `solution.md`**
