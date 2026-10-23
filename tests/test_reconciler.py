"""
Zone reconciler unit test — no hardware required.
"""

import sys
sys.path.insert(0, "src/pi")
from detection.zone_reconciler import ZoneReconciler


ZONE_NAMES = ["Q1", "Q2", "Q3", "Q4"]


def test_first_scan_always_trusted():
    r = ZoneReconciler(ZONE_NAMES, tolerance=1)
    total, rescan = r.reconcile({"Q1": 5, "Q2": 3, "Q3": 0, "Q4": 0}, last_total=0)
    assert total == 8
    assert rescan is False, "First scan should never need rescan"

def test_within_tolerance():
    r = ZoneReconciler(ZONE_NAMES, tolerance=1)
    total, rescan = r.reconcile({"Q1": 5, "Q2": 3, "Q3": 0, "Q4": 0}, last_total=9)
    assert total == 8
    assert rescan is False

def test_outside_tolerance():
    r = ZoneReconciler(ZONE_NAMES, tolerance=1)
    total, rescan = r.reconcile({"Q1": 1, "Q2": 0, "Q3": 0, "Q4": 0}, last_total=9)
    assert total == 1
    assert rescan is True, "Large delta should flag rescan"

def test_capacity_clipping():
    r = ZoneReconciler(ZONE_NAMES, tolerance=1, max_room_capacity=40, max_zone_capacity={"Q1": 10})
    total, _ = r.reconcile({"Q1": 15, "Q2": 35, "Q3": 0, "Q4": 0}, last_total=0)
    # Q1 clipped to 10 + Q2 35 = 45 -> room clipped to 40
    assert total == 40
    assert r.clip_capacity(55, 45) == 45
    assert r.clip_capacity(30, 45) == 30

def test_hysteresis_filtering():
    r = ZoneReconciler(ZONE_NAMES, hysteresis_delta=0.6)
    # Previous count was 5. Current raw is 5.4 -> stays 5
    assert r.apply_hysteresis(5.4, 5) == 5
    # Current raw is 4.6 -> stays 5
    assert r.apply_hysteresis(4.6, 5) == 5
    # Current raw is 5.7 -> flips to 6
    assert r.apply_hysteresis(5.7, 5) == 6
    # Current raw is 4.3 -> flips to 4
    assert r.apply_hysteresis(4.3, 5) == 4
    # If previous was 0, immediate round
    assert r.apply_hysteresis(3.2, 0) == 3


if __name__ == "__main__":
    test_first_scan_always_trusted(); print("[PASS] test_first_scan_always_trusted")
    test_within_tolerance();          print("[PASS] test_within_tolerance")
    test_outside_tolerance();         print("[PASS] test_outside_tolerance")
    test_capacity_clipping();         print("[PASS] test_capacity_clipping")
    test_hysteresis_filtering();      print("[PASS] test_hysteresis_filtering")
    print("All tests passed.")


