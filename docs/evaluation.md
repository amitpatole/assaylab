# Evaluation on public data

`assaylab` is evaluated on the **FlakeFlagger** dataset (Zenodo
[4450723](https://zenodo.org/records/4450723), CC BY 4.0) — 26,765 tests across
23 Java projects, each rerun 10,000 times to establish ground-truth flakiness.

Run it yourself (only the small summary CSVs are fetched, never the multi-GB
raw logs):

```console
$ pip install "assaylab[datasets]"
$ assaylab eval flakeflagger --fetch
```

Or point at local copies with `--features test_features.csv --results test_results.csv`.

## Result 1 — confidence bound holds on real data (the headline)

Using each test's **measured** per-run failure probability (from its fail/pass
counts over 10,000 reruns) as `q`, `assaylab select` was run at a target
confidence-loss of `ε = 0.05`:

```
confidence-bound validation (target epsilon = 0.05):
  26765 tests, speedup 35.878x, claimed epsilon 0.049958, realized miss rate 0.049957
  bound holds (realized <= claimed): True
```

**A 35.9× reduction in test-time, and the realized regression-miss rate
(0.049957) stayed within the bound the receipt claimed (0.049958).** The signed
receipt's ε is not a marketing number — on real measured failure rates it
matches reality.

## Result 2 — flaky prediction from features (lightweight baseline)

assaylab's built-in pure-Python logistic model, trained on FlakeFlagger's
static/dynamic feature table (held-out 70/30 split, decision threshold tuned on
the training split only):

```
flaky prediction (assaylab logistic model on features, held-out split):
  train=18633 test=7986 (positives=58)  threshold=0.13
  precision=0.3409 recall=0.2586  F1=0.2941
  confusion: tp=15 fp=29 fn=43 tn=7899
```

This is a deliberately lightweight baseline (no scikit-learn, JSON-serializable
weights). The set is severely imbalanced — 0.7% positive — so a fixed 0.5
threshold collapses to the majority class; tuning the threshold on the training
split recovers a real precision/recall tradeoff. FlakeFlagger's own tuned
random-forest reports higher F1 (~0.6); assaylab's baseline trades accuracy for
a dependency-free, inspectable model. Class weighting is future work.

## Honesty notes

- Numbers above are **real captured output**, reproducible with the command
  shown against the cited public data.
- The confidence-bound result validates the bound *given the measured `q`* — it
  does not eliminate the modelling assumptions (independence, `q` stationarity)
  stated in [Attested selection](selection.md).
- RTPTorrent (commit→outcome linkage, CC BY 4.0) is the planned next corpus for
  evaluating change-based selection; the ingestion schema already supports it.
