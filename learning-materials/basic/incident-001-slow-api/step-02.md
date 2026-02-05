# Step 02

---

## Look At The Code

Re-examine the checkout endpoint code:

```javascript
app.post('/api/checkout', async (req, res) => {
  const cartItems = await db.query(                    // Query 1
    'SELECT * FROM cart_items WHERE user_id = $1', [userId]
  );

  let total = 0;
  for (const item of cartItems.rows) {                 // Loop over cart items
    const product = await db.query(                     // Query PER item
      'SELECT * FROM products WHERE id = $1', [item.product_id]
    );
    total += product.rows[0].price * item.quantity;
  }

  await db.query(                                        // Final insert
    'INSERT INTO orders (user_id, total) VALUES ($1, $2)', [userId, total]
  );

  res.json({ orderId: result.rows[0].id, total });
});
```

---

## Questions

1. **How many database queries happen** for a checkout with 5 items?

2. **What's inside the loop** that's executed for each item?

3. **What pattern does this represent?**

(Hint: This is a classic anti-pattern that has a name...)

---

**Still stuck? Read `step-03.md`**
