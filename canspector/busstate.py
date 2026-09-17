import time
from dataclasses import dataclass, field


@dataclass
class FrameState:
    can_id: int
    data: bytes = b""
    prev_data: bytes = b""
    count: int = 0
    last_seen: float = field(default_factory=time.monotonic)

    def update(self, data: bytes) -> None:
        self.prev_data = self.data
        self.data = data
        self.count += 1
        self.last_seen = time.monotonic()

    def changed_byte_indexes(self) -> list[int]:
        return [
            i for i in range(min(len(self.data), len(self.prev_data)))
            if self.data[i] != self.prev_data[i]
        ]


class BusState:
    """Live table of the most recent frame per CAN ID, cansniffer-style."""

    def __init__(self):
        self.frames: dict[int, FrameState] = {}

    def update(self, can_id: int, data: bytes) -> FrameState:
        frame = self.frames.get(can_id)
        if frame is None:
            frame = FrameState(can_id)
            self.frames[can_id] = frame
        frame.update(data)
        return frame

    def snapshot(self) -> dict[int, bytes]:
        return {can_id: f.data for can_id, f in self.frames.items()}
