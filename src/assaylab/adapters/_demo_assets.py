"""Synthetic JUnit reports for ``assaylab demo`` — no API key, no network.

``broken_suite`` has three failures that collapse into two signatures (two tests
raise the *same* NullPointerException at addresses/lines that differ only
incidentally — proving the clustering). ``fixed_suite`` is the same suite green.
"""

from __future__ import annotations

BROKEN_SUITE = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="checkout" tests="4" failures="2" errors="1">
  <testcase classname="checkout.CartTest" name="test_total" time="0.012">
    <failure message="AssertionError: expected 42 but got 41">
Traceback (most recent call last):
  File "checkout/cart.py", line 88, in total
    return sum(items) + tax
AssertionError: expected 42 but got 41
    </failure>
  </testcase>
  <testcase classname="checkout.PaymentTest" name="test_charge" time="0.031">
    <error message="NullPointerException: card was null at 0x7ffa12">
Traceback (most recent call last):
  File "checkout/pay.py", line 140, in charge
    gateway.submit(card.token)
NullPointerException: card was null at 0x7ffa12
    </error>
  </testcase>
  <testcase classname="checkout.RefundTest" name="test_refund" time="0.028">
    <error message="NullPointerException: card was null at 0x9b3c01">
Traceback (most recent call last):
  File "checkout/pay.py", line 140, in charge
    gateway.submit(card.token)
NullPointerException: card was null at 0x9b3c01
    </error>
  </testcase>
  <testcase classname="checkout.CatalogTest" name="test_list" time="0.005"/>
</testsuite>
"""

FIXED_SUITE = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="checkout" tests="4" failures="0" errors="0">
  <testcase classname="checkout.CartTest" name="test_total" time="0.011"/>
  <testcase classname="checkout.PaymentTest" name="test_charge" time="0.030"/>
  <testcase classname="checkout.RefundTest" name="test_refund" time="0.027"/>
  <testcase classname="checkout.CatalogTest" name="test_list" time="0.005"/>
</testsuite>
"""


def broken_suite() -> str:
    return BROKEN_SUITE


def fixed_suite() -> str:
    return FIXED_SUITE
