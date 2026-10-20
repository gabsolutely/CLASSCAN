"""
Zone-count reconciler.

After a ZONE_CHECK scan, sums per-zone counts and compares
against the last known full-room total. Flags a re-scan if
the numbers don't reconcile within tolerance.
"""


class ZoneReconciler:
    def __init__(
        self,
        zone_names: list[str] | None = None,
        tolerance: int = 1,
        max_room_capacity: int | None = None,
        max_zone_capacity: dict[str, int] | None = None,
        hysteresis_delta: float = 0.6,
    ):
        """
        zone_names:         list of active zone identifiers (e.g. ['Q1', 'Q2', 'Q3', 'Q4'])
        tolerance:          allowed difference between summed zone counts and
                            last reported total before a re-scan is flagged.
        max_room_capacity:  physical ceiling capacity of the entire room (clips impossible overcounts)
        max_zone_capacity:  dict of physical maximum seat capacities per zone/quadrant
        hysteresis_delta:   dead-band offset required to flip an integer headcount display
        """
        self.zone_names        = zone_names or ["Q1", "Q2", "Q3", "Q4"]
        self.tolerance         = tolerance
        self.max_room_capacity = max_room_capacity
        self.max_zone_capacity = max_zone_capacity or {}
        self.hysteresis_delta  = hysteresis_delta

    def apply_hysteresis(
        self,
        current_raw: float,
        previous_int: int,
        delta: float | None = None,
    ) -> int:
        """
        Apply deadband hysteresis to prevent 1-count flickering on boundary values.
        If current_raw is within previous_int ± delta, maintain previous_int.
        Otherwise round current_raw to nearest integer.
        """
        if delta is None:
            delta = self.hysteresis_delta
        if previous_int <= 0:
            return max(0, round(current_raw))

        lower_bound = previous_int - delta
        upper_bound = previous_int + delta

        if lower_bound <= current_raw <= upper_bound:
            return previous_int
        return max(0, round(current_raw))

    def clip_capacity(self, count: int, max_cap: int | None = None) -> int:
        """Clip headcount to physical room/quadrant seating limits."""
        limit = max_cap if max_cap is not None else self.max_room_capacity
        if limit is not None and limit > 0:
            return min(count, limit)
        return count

    def reconcile(
        self,
        zone_counts: dict[str, int],
        last_total: int,
    ) -> tuple[int, bool]:
        """
        Returns (total_count, needs_rescan).

        Performs:
          1. Optional per-zone capacity clipping against max_zone_capacity
          2. Summation of per-zone counts
          3. Room capacity clipping against max_room_capacity
          4. Tolerance check against last_total

        needs_rescan is True when:
          - Sum of zone counts differs from last_total by more than tolerance,
            AND last_total > 0 (first scan always trusted).
        """
        clipped_counts = {}
        for z, c in zone_counts.items():
            z_limit = self.max_zone_capacity.get(z)
            clipped_counts[z] = min(c, z_limit) if z_limit is not None else c

        total = sum(clipped_counts.values())
        if self.max_room_capacity is not None and self.max_room_capacity > 0:
            total = min(total, self.max_room_capacity)

        if last_total == 0:
            return total, False

        diff = abs(total - last_total)
        needs_rescan = diff > self.tolerance
        return total, needs_rescan

