"""
Zone-count reconciler.

After a ZONE_CHECK scan, sums per-zone counts and compares
against the last known full-room total. Flags a re-scan if
the numbers don't reconcile within tolerance.
"""


class ZoneReconciler:
    def __init__(self, zones: dict, tolerance: int = 1):
        """
        zones:     dict of zone_name → max_seats (used for sanity bound)
        tolerance: allowed difference between summed zone counts and
                   last reported total before a re-scan is flagged.
        """
        self.zones     = zones
        self.tolerance = tolerance

    def reconcile(
        self,
        zone_counts: dict[str, int],
        last_total: int,
    ) -> tuple[int, bool]:
        """
        Returns (total_count, needs_rescan).

        needs_rescan is True when:
          - Sum of zone counts differs from last_total by more than tolerance,
            AND last_total > 0 (first scan always trusted).
        """
        total = sum(zone_counts.values())

        if last_total == 0:
            return total, False

        diff = abs(total - last_total)
        needs_rescan = diff > self.tolerance
        return total, needs_rescan
