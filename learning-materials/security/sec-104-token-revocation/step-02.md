# Step 2: Implementation

---

## Recommended: Short-Lived + Refresh Tokens

```go
package main

import (
    "errors"
    "fmt"
    "time"

    "github.com/golang-jwt/jwt/v5"
    "gorm.io/gorm"
)

type TokenPair struct {
    AccessToken  string
    RefreshToken string
    ExpiresIn    int  // seconds
}

type RefreshToken struct {
    Token     string
    UserID    string
    ExpiresAt time.Time
}

type AuthService struct {
    secret []byte
    db     *gorm.DB
}

func (s *AuthService) Login(user User) (*TokenPair, error) {
    // Access token: short-lived, stateless JWT
    accessClaims := jwt.MapClaims{
        "sub":           user.ID,
        "exp":           time.Now().Add(15 * time.Minute).Unix(),
        "iat":           time.Now().Unix(),
        "token_version": user.TokenVersion,
        "type":          "access",
    }

    accessToken := jwt.NewWithClaims(jwt.SigningMethodHS256, accessClaims)
    accessString, err := accessToken.SignedString(s.secret)
    if err != nil {
        return nil, err
    }

    // Refresh token: long-lived, stored in DB
    refreshToken := generateSecureToken()
    dbToken := &RefreshToken{
        Token:     refreshToken,
        UserID:    user.ID,
        ExpiresAt: time.Now().Add(30 * 24 * time.Hour),
    }

    if err := s.db.Create(dbToken).Error; err != nil {
        return nil, err
    }

    return &TokenPair{
        AccessToken:  accessString,
        RefreshToken: refreshToken,
        ExpiresIn:    900,  // 15 minutes
    }, nil
}

func (s *AuthService) Refresh(refreshToken string) (*TokenPair, error) {
    // Validate refresh token
    var dbToken RefreshToken
    err := s.db.Where("token = ? AND expires_at > ?", refreshToken, time.Now()).
        First(&dbToken).Error
    if err != nil {
        return nil, errors.New("invalid refresh token")
    }

    // Get user
    var user User
    err = s.db.First(&user, "id = ?", dbToken.UserID).Error
    if err != nil {
        return nil, errors.New("user not found")
    }

    // Delete old refresh token
    s.db.Delete(&dbToken)

    // Issue new token pair
    return s.Login(user)
}

func (s *AuthService) RevokeTokens(userID string) error {
    // Delete all refresh tokens
    s.db.Where("user_id = ?", userID).Delete(&RefreshToken{})

    // Increment token version (invalidates all JWTs)
    return s.db.Model(&User{}).Where("id = ?", userID).
        Update("token_version", gorm.Expr("token_version + 1")).Error
}

func (s *AuthService) ValidateJWT(tokenString string) (*jwt.MapClaims, error) {
    token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
        // Verify signing method
        if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
            return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
        }
        return s.secret, nil
    })

    if err != nil {
        return nil, err
    }

    if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
        // Check token type
        if claims["type"] != "access" {
            return nil, errors.New("not an access token")
        }

        // Check token version
        var user User
        err := s.db.Select("token_version").First(&user, "id = ?", claims["sub"]).Error
        if err != nil {
            return nil, err
        }

        tokenVersion := int(claims["token_version"].(float64))
        if tokenVersion != user.TokenVersion {
            return nil, errors.New("token revoked")
        }

        return &claims, nil
    }

    return nil, errors.New("invalid token")
}
```

---

## Refresh Token Rotation

```go
// Rotate refresh tokens on each use for security
func (s *AuthService) RefreshWithRotation(refreshToken string) (*TokenPair, error) {
    // Validate old refresh token
    var dbToken RefreshToken
    err := s.db.Where("token = ? AND expires_at > ?", refreshToken, time.Now()).
        First(&dbToken).Error
    if err != nil {
        return nil, errors.New("invalid refresh token")
    }

    // Get user
    var user User
    err = s.db.First(&user, "id = ?", dbToken.UserID).Error
    if err != nil {
        return nil, errors.New("user not found")
    }

    // Delete old refresh token (rotation)
    s.db.Delete(&dbToken)

    // Issue new token pair with new refresh token
    return s.Login(user)
}
```

---

## Middleware for Token Validation

```go
func (s *AuthService) AuthMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Extract token from Authorization header
        authHeader := r.Header.Get("Authorization")
        if authHeader == "" {
            http.Error(w, "Missing authorization header", http.StatusUnauthorized)
            return
        }

        tokenString := strings.TrimPrefix(authHeader, "Bearer ")

        // Validate token
        claims, err := s.ValidateJWT(tokenString)
        if err != nil {
            http.Error(w, "Invalid token", http.StatusUnauthorized)
            return
        }

        // Add user info to context
        userID := (*claims)["sub"].(string)
        ctx := context.WithValue(r.Context(), "userID", userID)
        ctx = context.WithValue(ctx, "claims", claims)

        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

---

## Logout Handler

```go
func (s *AuthService) Logout(w http.ResponseWriter, r *http.Request) {
    // Get user from context
    userID := r.Context().Value("userID").(string)

    // Revoke all tokens for user
    if err := s.RevokeTokens(userID); err != nil {
        http.Error(w, "Logout failed", http.StatusInternalServerError)
        return
    }

    // Optionally, add current access token to blocklist
    // for immediate revocation (not shown here)

    w.WriteHeader(http.StatusNoContent)
}
```

---

## Quick Check

Before moving on, make sure you understand:

1. What's the recommended token strategy? (Short-lived access tokens + long-lived refresh tokens stored in DB)
2. Why rotate refresh tokens? (Detect stolen refresh tokens quickly; old token becomes invalid after first use)
3. How does version-based revocation work? (Store version in user record; increment to revoke all tokens; check version on JWT validation)
4. Why delete refresh token on use? (Rotation - prevents reuse of stolen tokens)
5. What's the full revocation flow? (Delete all refresh tokens from DB + increment token_version to invalidate access tokens)

---

**Read `solution.md`**
