# Root-cause analysis

Point `rca` at run history (many runs, ideally with commit + outcome). For each
failure signature it assigns a **root cause**, a **flaky-vs-real** verdict, and a
**risk** score. An all-flaky failure set grades **WARN** so flakiness doesn't
block your gate:

```console
$ assaylab rca history.csv
verdict: FAIL  —  4 failing execution(s) across 2 signature(s) (1 real, 1 flaky); 4/8 passed.
  [error]   failure_signature  cause=null_deref (conf 1.0)  flaky=False (p=0.0)  risk=0.7
      NullPointerException across 1 test (3 runs): NullPointerException: card was null at 0x1a
      why: matched 'null_deref' on 'NullPointer'; consistent failures — looks real
  [warning] flaky_suspect  cause=timeout (conf 0.85)  flaky=True (p=0.95)  risk=0.5333
      Failure across 1 test (1 run): timeout waiting for lock after 5000ms
      why: matched 'timeout' on 'timeout'; same commit produced both pass and fail
```

## How it decides

- **Root cause** — a transparent, always-on categorizer maps the signature to a
  cause (`null_deref`, `timeout`, `dependency`, `config`, `resource`,
  `concurrency`, `network`, `assertion`, …) with a confidence and the evidence
  that fired. It's the interpretable floor the learned model is measured against.
- **Flaky-vs-real** — the strongest signal is a single commit that shows **both**
  a pass and a failure (order-agnostic flakiness), backed by flip-rate across
  runs. Real failures are consistent at a given commit.
- **Risk & forecast** — recency-weighted failure rate blended with instability;
  `forecast` estimates the chance the test fails on its next run.

## Rank the riskiest tests

```console
$ assaylab risk history.csv --top 5
  risk  forecast   fail%   flip%  test
 0.700     1.000  100.0%    0.0%  svc.Broken::test_charge
 0.533     0.000   33.3%  100.0%  svc.Flappy::test_race
 0.000     0.000    0.0%    0.0%  svc.Stable::test_ok
```

## The learned model

`assaylab` ships a self-contained logistic-regression classifier for flaky
prediction — pure Python (no scikit-learn in the base wheel), trained by batch
gradient descent, and persisted as **JSON, never pickle** (loading a model can't
execute code — a real supply-chain footgun avoided):

```console
$ assaylab train labeled.csv -o flaky-model.json   # rows of features + a 'flaky' 0/1 label
trained on 80 rows -> flaky-model.json (3 features)

$ assaylab rca history.csv --model flaky-model.json  # use the learned model
```

For heavier models, train externally and export coefficients into the same JSON
shape; prediction stays dependency-free and inert to load.
