# Step 1: TLS Handshake Costs

---

## Full Handshake Timeline

```
0ms    ClientHello → (send ciphers, random)
10ms   ← ServerHello, Certificate, ServerHelloDone
20ms   ClientKeyExchange, ChangeCipherSpec →
30ms   ← ChangeCipherSpec, Finished
35ms   Application Data →
40ms   ← Application Data

With mTLS (additional):
0ms    ClientHello + ClientCert →
10ms   ← ServerHello, ServerCert, CertificateRequest
20ms   Certificate, ClientKeyExchange →
30ms   ← ChangeCipherSpec, Finished, CertificateVerify
35ms   ChangeCipherSpec, Finished →
40ms   ← Application Data
```

---

## Session Resumption

```
Full handshake: 3-4 RTTs
Session resumption: 1-2 RTTs

Using session tickets:
- Client stores encrypted session state
- Presents ticket in ClientHello
- Server decrypts, resumes session
- Skips certificate exchange
```

---

## Quick Check

Before moving on, make sure you understand:

1. How many RTTs does a full TLS handshake take? (3-4 RTTs)
2. How many RTTs with session resumption? (1-2 RTTs)
3. What's mTLS? (Mutual TLS - both client and server present certificates)
4. What's a session ticket? (Encrypted session state stored by client, enables faster resumption)
5. Why is TLS handshake expensive? (Multiple round trips, crypto operations, certificate exchange)

---

**Read `step-02.md`
