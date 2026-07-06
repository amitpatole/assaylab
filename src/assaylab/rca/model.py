"""A small, self-contained logistic-regression model for flaky prediction.

Pure Python (batch gradient descent) — no numpy/scikit-learn in the base wheel,
and the trained model serializes to **JSON**, never pickle. That matters: a
pickled model is arbitrary-code-execution on load, so a model pulled from a
registry or CI cache would be a supply-chain hole. JSON weights load inertly.

Features are addressed by name (a dict), so callers never depend on column
order. Unknown/missing features default to 0.0. Inputs are standardized using
means/stds captured at fit time.

For heavier models, train externally and export coefficients into this JSON
shape; prediction stays dependency-free.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

_SCHEMA = "assaylab.flaky-logreg/1"


@dataclass
class LogisticModel:
    feature_names: list[str] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    bias: float = 0.0
    mean: list[float] = field(default_factory=list)
    std: list[float] = field(default_factory=list)

    # ---- inference -------------------------------------------------------
    def _vector(self, features: dict[str, float]) -> list[float]:
        return [float(features.get(name, 0.0)) for name in self.feature_names]

    def _standardize(self, x: list[float]) -> list[float]:
        if not self.mean:
            return x
        return [(xi - m) / s if s else 0.0 for xi, m, s in zip(x, self.mean, self.std, strict=True)]

    def predict_proba(self, features: dict[str, float]) -> float:
        x = self._standardize(self._vector(features))
        z = self.bias + sum(w * xi for w, xi in zip(self.weights, x, strict=True))
        return 1.0 / (1.0 + math.exp(-_clamp(z)))

    # ---- persistence (JSON only) ----------------------------------------
    def to_json(self) -> str:
        return json.dumps({
            "schema": _SCHEMA,
            "feature_names": self.feature_names,
            "weights": self.weights,
            "bias": self.bias,
            "mean": self.mean,
            "std": self.std,
        })

    @classmethod
    def from_json(cls, text: str) -> LogisticModel:
        data = json.loads(text)
        if data.get("schema") != _SCHEMA:
            raise ValueError(f"unexpected model schema {data.get('schema')!r}")
        return cls(
            feature_names=list(data["feature_names"]),
            weights=[float(w) for w in data["weights"]],
            bias=float(data["bias"]),
            mean=[float(m) for m in data.get("mean", [])],
            std=[float(s) for s in data.get("std", [])],
        )


def _clamp(z: float) -> float:
    return max(-60.0, min(60.0, z))


def train(
    samples: list[tuple[dict[str, float], int]],
    *,
    feature_names: list[str] | None = None,
    epochs: int = 400,
    lr: float = 0.3,
    l2: float = 1e-3,
) -> LogisticModel:
    """Fit a logistic model on ``(features, label)`` pairs (label in {0,1}).

    Deterministic: no randomness, weights start at zero, so the same data always
    yields the same model.
    """
    if not samples:
        raise ValueError("no training samples")
    names = feature_names or sorted({k for feats, _ in samples for k in feats})
    rows = [[float(feats.get(n, 0.0)) for n in names] for feats, _ in samples]
    labels = [int(y) for _, y in samples]

    n_feat = len(names)
    mean = [sum(r[j] for r in rows) / len(rows) for j in range(n_feat)]
    var = [sum((r[j] - mean[j]) ** 2 for r in rows) / len(rows) for j in range(n_feat)]
    std = [math.sqrt(v) if v > 1e-12 else 1.0 for v in var]
    xs = [[(r[j] - mean[j]) / std[j] for j in range(n_feat)] for r in rows]

    w = [0.0] * n_feat
    b = 0.0
    m = len(xs)
    for _ in range(epochs):
        grad_w = [0.0] * n_feat
        grad_b = 0.0
        for xi, yi in zip(xs, labels, strict=True):
            z = b + sum(w[j] * xi[j] for j in range(n_feat))
            p = 1.0 / (1.0 + math.exp(-_clamp(z)))
            err = p - yi
            for j in range(n_feat):
                grad_w[j] += err * xi[j]
            grad_b += err
        for j in range(n_feat):
            w[j] -= lr * (grad_w[j] / m + l2 * w[j])
        b -= lr * (grad_b / m)

    return LogisticModel(feature_names=names, weights=w, bias=b, mean=mean, std=std)
