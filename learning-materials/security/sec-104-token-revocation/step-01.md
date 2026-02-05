# Step 1: Revocation Strategies

---

## Strategy 1: Short-Lived Access Tokens

```
Access token: 5-15 minutes
Refresh token: 7-30 days

Flow:
1. User logs in → gets access (15m) + refresh (7d)
2. Access expires → use refresh to get new access
3. Refresh expires → re-authenticate

Revoke by:
- Delete refresh token from database
- Access expires in 15 minutes max
```

```go
package main

import (
    "time"
    "github.com/golang-jwt/jwt/v5"
)

type TokenPair struct {
    AccessToken  string
    RefreshToken string
    ExpiresIn    int  // seconds
}

func (s *AuthService) Login(user User) (*TokenPair, error) {
    // Access token: short-lived, stateless JWT
    accessClaims := jwt.MapClaims{
        "sub":  user.ID,
        "exp":  time.Now().Add(15 * time.Minute).Unix(),
        "iat":  time.Now().Unix(),
        "type": "access",
    }

    accessToken := jwt.NewWithClaims(jwt.SigningMethodHS256, accessClaims)
    accessString, err := accessToken.SignedString(s.secret)
    if err != nil {
        return nil, err
    }

    // Refresh token: long-lived, stored in DB
    refreshToken := generateSecureToken()
    err = s.db.Create(&RefreshToken{
        Token:     refreshToken,
        UserID:    user.ID,
        ExpiresAt: time.Now().Add(30 * 24 * time.Hour),
    })
    if err != nil {
        return nil, err
    }

    return &TokenPair{
        AccessToken:  accessString,
        RefreshToken: refreshToken,
        ExpiresIn:    900,  // 15 minutes
    }, nil
}
```

---

## Strategy 2: Token Blocklist

```
Store revoked token IDs (jti) in Redis/DB

On request:
1. Decode JWT, extract jti
2. Check if jti in blocklist
3. If yes → 401 Unauthorized

On revocation:
1. Add jti to blocklist
2. Set TTL = remaining token lifetime

Pros: Works with stateless JWT
Cons: Requires state lookup
```

```go
type TokenBlocklist struct {
    redis *redis.Client
}

func (tb *TokenBlocklist) Revoke(tokenString string) error {
    // Parse token (don't verify signature)
    token, _, err := jwt.NewParser().ParseUnverified(tokenString, &jwt.MapClaims{})
    if err != nil {
        return err
    }

    claims := token.Claims.(*jwt.MapClaims)
    jti := (*claims)["jti"].(string)
    exp := int64((*claims)["exp"].(float64))

    // Calculate TTL until expiration
    ttl := time.Until(time.Unix(exp, 0))
    if ttl < 0 {
        ttl = time.Hour  // Minimum TTL
    }

    // Add to blocklist
    return tb.redis.Set(context.Background(), "blocklist:"+jti, "1", ttl).Err()
}

func (tb *TokenBlocklist) IsRevoked(jti string) (bool, error) {
    exists := tb.redis.Exists(context.Background(), "blocklist:"+jti).Val()
    return exists == 1, nil
}
```

---

## Strategy 3: Version Claim

```
Add token_version to JWT
Store current version in user record

On request:
1. Decode JWT, extract sub and token_version
2. Get user's current token_version from DB
3. If mismatch → 401 Unauthorized

On revocation:
1. Increment user's token_version in DB
2. All old tokens now invalid

Pros: Simple, efficient
Cons: Revokes ALL tokens for user
```

```go
type User struct {
    ID            string
    TokenVersion  int
}

func (s *AuthService) ValidateJWT(tokenString string) (*jwt.MapClaims, error) {
    token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
        return s.secret, nil
    })

    if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
        // Check token version
        var user User
        s.db.First(&user, "id = ?", claims["sub"])

        tokenVersion := int(claims["token_version"].(float64))
        if tokenVersion != user.TokenVersion {
            return nil, errors.New("token revoked")
        }

        return &claims, nil
    }

    return nil, err
}

func (s *AuthService) RevokeTokens(userID string) error {
    // Increment token version (invalidates all JWTs)
    return s.db.Model(&User{}).Where("id = ?", userID).
        Update("token_version", gorm.Expr("token_version + 1")).Error
}
```

---

## Comparison

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| Short-lived + refresh | Fast, mostly stateless | Requires DB lookup for refresh | Most apps |
| Token blocklist | Per-token revocation | State lookup on every request | Critical tokens |
| Version claim | Fast, simple | Revokes ALL tokens | Full logout |

---

## Quick Check

Before moving on, make sure you understand:

1. What's the short-lived token strategy? (Access token: 15 min, Refresh token: 7-30 days; revoke by deleting refresh token)
2. What's the token blocklist? (Store revoked token IDs in Redis/DB, check on each request, TTL = remaining lifetime)
3. What's the version claim strategy? (Store version in user record, increment to revoke all tokens)
4. What's the tradeoff between blocklist and version? (Blocklist: per-token revocation but slower; Version: fast but revokes all tokens)
5. Why short-lived tokens are best for most apps? (Fast, mostly stateless, automatic expiry, revoke by deleting refresh token)

---

**Read `step-02.md`**
