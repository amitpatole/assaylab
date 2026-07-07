# Attested test-selection

This is `assaylab`'s distinctive contribution: reduce a test suite **and** emit a
signed receipt that bounds the confidence lost — a claim a consumer can
independently re-derive.

## The confidence bound

Each candidate test `t` has a detection probability `q_t` — the modelled chance
it fails (catches a regression) on this run, estimated from history (the P2
forecast). If we run a subset `S` and skip `U = All \ S`, the probability that
*at least one* skipped test would have failed is

$$ \varepsilon = 1 - \prod_{t \in U}(1 - q_t) $$

under an independence assumption. `ε` is the **confidence lost** by skipping.
Selection keeps the highest value-density tests (`q_t` per second) until either
`ε ≤ target` or the time budget is spent; the achieved `ε` is always reported.

## Select + attest

```console
$ export ASSAYLAB_SIGNING_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
$ assaylab select history.csv --target-epsilon 0.05 --receipt receipt.json
selected 3/43 tests  speedup 9.0x  confidence 1.0000  (epsilon 0.0000)
  run:  svc.Hot::t0, svc.Hot::t1, svc.Hot::t2
  skip: svc.Cold::t0, svc.Cold::t1, svc.Cold::t10, ...
  receipt d9f197c5e91d sig daa3bd1ae81f…
  wrote signed receipt -> receipt.json
```

Code-touched tests can be force-kept with `--changed a.py,b.py`.

## Verify — signature *and* reproduction

The receipt is HMAC-SHA256 over the **outcome** (inputs hash, selected/skipped
hashes, and the computed `ε`), so the signature binds the real result. Because
selection is deterministic in its committed inputs, a consumer can also *recompute*
the bound from history and confirm it reproduces:

```console
$ assaylab verify receipt.json --against history.csv
receipt d9f197c5e91d: signature VALID  (epsilon 0.0000, confidence 1.0000, selected 3/43, speedup 9.0x)
  reproduction: OK — reproduced: selection and confidence bound are genuine
```

Tamper with the receipt's `epsilon` and it fails closed — both the signature
check and the reproduction reject a forged bound.

## Security

- The signing key resolves from `ASSAYLAB_SIGNING_KEY` (hex/base64/raw, ≥16
  bytes) → else a persisted per-installation key at `<config>/assaylab/signing.key`
  written `0600`. **Never a hardcoded default.**
- Verification is constant-time (`hmac.compare_digest`).

## Honest limits

The bound's residual assumptions — stated, not hidden:

- **Independence** of test failures.
- **Stationarity** of `q_t` (history predicts the next run).
- Coverage only of **regression classes seen historically**.

## External verification (ed25519)

HMAC receipts are a symmetric trust domain — the verifier needs the signing key,
so it could also forge. For **external** verification, sign asymmetrically
(needs the `crypto` extra): the producer signs with a private key and publishes
the public key; anyone verifies against the (trusted, out-of-band) public key
without any secret.

```console
$ pip install "assaylab[crypto]"
$ assaylab pubkey                                   # share this with verifiers
2fb218ec0e8e3993...
$ assaylab select history.csv --target-epsilon 0.05 --alg ed25519 -o receipt.json
$ assaylab verify receipt.json --pubkey 2fb218ec... --against history.csv
receipt 9ab3d19b4dcd [ed25519]: signature VALID  (...)
  reproduction: OK — reproduced: selection and confidence bound are genuine
```

The private key resolves from `ASSAYLAB_ED25519_PRIVATE_KEY` or a persisted
per-install key; verifiers only ever need the public key.

**Remaining residual:** receipts are stateless — a valid receipt re-verifies
indefinitely (no built-in freshness/replay window; enforce that consumer-side
with a nonce ledger + `created_ts` max-age if you need it).
