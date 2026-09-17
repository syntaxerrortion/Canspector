import cantools


class Decoder:
    """Optional DBC-based signal decoder. Falls back to raw hex if no DBC
    is loaded, or if a given CAN ID isn't defined in the DBC file.
    """

    def __init__(self, dbc_path: str | None = None):
        self.db = cantools.database.load_file(dbc_path) if dbc_path else None

    def decode(self, can_id: int, data: bytes) -> dict[str, str] | None:
        if self.db is None:
            return None
        try:
            message = self.db.get_message_by_frame_id(can_id)
            signals = message.decode(data, allow_truncated=True)
            return {name: str(value) for name, value in signals.items()}
        except (KeyError, cantools.database.DecodeError):
            return None
