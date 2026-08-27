"""
Zone reconciler unit test — no hardware required.
"""

import sys
sys.path.insert(0, "src/pi")
from detection.zone_reconciler import ZoneReconciler


ZONES = {"Q1": 10, "Q2": 10, "Q3": 10, "Q4": 10}


def test_first_scan_always_trusted():
    r = ZoneReconciler(ZONES, tolerance=1)
    total, rescan = r.reconcile({"Q1": 5, "Q2": 3, "Q3": 0, "Q4": 0}, last_total=0)
    assert total == 8
    assert rescan is False, "First scan should never need rescan"

def test_within_tolerance():
    r = ZoneReconciler(ZONES, tolerance=1)
    total, rescan = r.reconcile({"Q1": 5, "Q2": 3, "Q3": 0, "Q4": 0}, last_total=9)
    assert total == 8
    assert rescan is False

def test_outside_tolerance():
    r = ZoneReconciler(ZONES, tolerance=1)
    total, rescan = r.reconcile({"Q1": 1, "Q2": 0, "Q3": 0, "Q4": 0}, last_total=9)
    assert total == 1
    assert rescan is True, "Large delta should flag rescan"


if __name__ == "__main__":
    test_first_scan_always_trusted(); print("✓ test_first_scan_always_trusted")
    test_within_tolerance();          print("✓ test_within_tolerance")
    test_outside_tolerance();         print("✓ test_outside_tolerance")
    print("All tests passed.")
