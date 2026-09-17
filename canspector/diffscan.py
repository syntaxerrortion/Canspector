from dataclasses import dataclass, field


@dataclass
class DiffResult:
    can_id: int
    before: bytes | None
    after: bytes | None
    changed_byte_indexes: list[int] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.before is None:
            return "new"
        if self.after is None:
            return "gone"
        return "changed"


class DiffSession:
    """Captures two snapshots of the live CAN bus state and diffs them,
    to find which IDs/bytes react to a specific vehicle action
    (e.g. press a button, then compare before/after).
    """

    def __init__(self):
        self.snapshot_a: dict[int, bytes] = {}
        self.snapshot_b: dict[int, bytes] = {}

    def take_snapshot_a(self, live_state: dict[int, bytes]) -> None:
        self.snapshot_a = dict(live_state)

    def take_snapshot_b(self, live_state: dict[int, bytes]) -> None:
        self.snapshot_b = dict(live_state)

    def diff(self) -> list[DiffResult]:
        results = []
        all_ids = set(self.snapshot_a) | set(self.snapshot_b)
        for can_id in sorted(all_ids):
            before = self.snapshot_a.get(can_id)
            after = self.snapshot_b.get(can_id)
            if before == after:
                continue
            changed = []
            if before is not None and after is not None:
                changed = [
                    i for i in range(min(len(before), len(after)))
                    if before[i] != after[i]
                ]
            results.append(DiffResult(can_id, before, after, changed))
        return results
