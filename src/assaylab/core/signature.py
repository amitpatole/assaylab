"""Failure-signature normalization and clustering.

Given failing :class:`TestRecord` executions, collapse the ones that differ only
in *incidental* detail — memory addresses, object hashes, line numbers, temp
paths, timestamps, UUIDs, numbers — into a single :class:`FailureSignature`
identified by a stable fingerprint. This is the evidence layer everything else
(RCA, flaky classification, confidence bounds) grounds on.

Pure-stdlib and deterministic: the same corpus always yields the same
signature ids, so verdicts are reproducible.
"""

from __future__ import annotations

import hashlib
import re

from ..models import FailureSignature, Outcome, TestRecord

# Ordered substitutions that strip incidental variation into stable placeholders.
_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"0x[0-9a-fA-F]+"), "<ADDR>"),                     # memory addresses / object ids
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),   # UUIDs
    (re.compile(r"\b[0-9a-fA-F]{16,}\b"), "<HEX>"),                # long hex blobs / hashes
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*"), "<TS>"),  # ISO timestamps
    (re.compile(r"(/tmp|/var/folders|C:\\Users\\[^\\]+\\AppData)\S*"), "<TMP>"),  # temp paths
    (re.compile(r":\d+\b"), ":<N>"),                               # :line — before bare-number sub
    (re.compile(r"\b\d+(?:\.\d+)?\b"), "<N>"),                     # remaining numbers
    (re.compile(r"\s+"), " "),                                     # collapse whitespace
)

# Exception type: "package.ClassNameError" or "ClassNameError:" at a line head.
_EXC_TYPE = re.compile(r"\b([A-Za-z_][\w.]*(?:Error|Exception|Failure|AssertionError))\b")
# Stack frames: Python `File "x.py", line N, in func` and Java `at pkg.Cls.method(File.java:N)`.
_PY_FRAME = re.compile(r'File "([^"]+)", line \d+, in (\S+)')
_JAVA_FRAME = re.compile(r"at ([\w.$]+)\(([^):]+)(?::\d+)?\)")
_MAX_FRAMES = 5


def normalize(text: str) -> str:
    """Strip incidental variation, returning a stable template string."""
    out = text.strip()
    for pattern, repl in _SUBS:
        out = pattern.sub(repl, out)
    return out.strip()


def _exception_type(record: TestRecord) -> str:
    for blob in (record.message, record.stacktrace):
        m = _EXC_TYPE.search(blob or "")
        if m:
            return m.group(1)
    return ""


def _top_frames(stacktrace: str) -> list[str]:
    """Extract up to ``_MAX_FRAMES`` frames as ``file:func`` (line numbers dropped)."""
    frames: list[str] = []
    for m in _PY_FRAME.finditer(stacktrace or ""):
        frames.append(f"{m.group(1)}:{m.group(2)}")
    if not frames:
        for m in _JAVA_FRAME.finditer(stacktrace or ""):
            frames.append(f"{m.group(2)}:{m.group(1)}")
    return frames[:_MAX_FRAMES]


def _files_from_frames(frames: list[str]) -> list[str]:
    files: list[str] = []
    for f in frames:
        head = f.split(":", 1)[0]
        if head and head not in files:
            files.append(head)
    return files


def fingerprint(record: TestRecord) -> tuple[str, str, str, list[str]]:
    """Return ``(signature_id, template, exception_type, files)`` for a failing record.

    The template combines the normalized message with normalized top frames, so
    two failures with the same root but different incidental text collapse.
    """
    exc = _exception_type(record)
    frames = _top_frames(record.stacktrace)
    body = normalize(record.message)
    frame_sig = " | ".join(normalize(fr) for fr in frames)
    template = f"{exc} || {body} || {frame_sig}".strip()
    sig_id = hashlib.sha1(template.encode("utf-8", "replace")).hexdigest()[:12]
    return sig_id, template, exc, _files_from_frames(frames)


def cluster(records: list[TestRecord]) -> list[FailureSignature]:
    """Cluster failing records into signatures, ordered by descending run count.

    Passing/skipped records are ignored (only failures carry a signature).
    """
    sigs: dict[str, FailureSignature] = {}
    for rec in records:
        if not rec.outcome.failed:
            continue
        sig_id, template, exc, files = fingerprint(rec)
        sig = sigs.get(sig_id)
        if sig is None:
            sig = FailureSignature(
                signature_id=sig_id,
                template=template,
                exception_type=exc,
                sample_message=(rec.message or rec.stacktrace or "").strip()[:500],
            )
            sigs[sig_id] = sig
        sig.count += 1
        if rec.test_id and rec.test_id not in sig.tests:
            sig.tests.append(rec.test_id)
        for f in files:
            if f not in sig.files:
                sig.files.append(f)
        if rec.file and rec.file not in sig.files:
            sig.files.append(rec.file)
    return sorted(sigs.values(), key=lambda s: (-s.count, s.signature_id))


def failing(records: list[TestRecord]) -> list[TestRecord]:
    return [r for r in records if r.outcome.failed]


def passing(records: list[TestRecord]) -> list[TestRecord]:
    return [r for r in records if r.outcome == Outcome.PASS]
