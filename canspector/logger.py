import time


class FrameLogger:
    """Appends captured frames to a simple text log:
    '<unix_time> <hex_id> <hex_bytes...>' - one per line, replayable later.
    """

    def __init__(self, path: str):
        self._fh = open(path, "a", buffering=1)

    def log(self, can_id: int, data: bytes) -> None:
        hex_bytes = " ".join(f"{b:02X}" for b in data)
        self._fh.write(f"{time.time():.6f} {can_id:X} {hex_bytes}\n")

    def close(self) -> None:
        self._fh.close()


def load_log(path: str):
    """Yields (timestamp: float, can_id: int, data: bytes) from a log file
    written by FrameLogger.
    """
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 2:
                continue
            ts = float(parts[0])
            can_id = int(parts[1], 16)
            data = bytes(int(b, 16) for b in parts[2:])
            yield ts, can_id, data
