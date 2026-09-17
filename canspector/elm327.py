import time
import serial


class ELM327Error(Exception):
    pass


class ELM327:
    """Serial connection to an ELM327 (or compatible clone) OBD2 adapter."""

    def __init__(self, port: str, baudrate: int = 38400, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: serial.Serial | None = None
        self._in_monitor_mode = False

    def connect(self) -> None:
        self.ser = serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout)
        time.sleep(1.0)
        self.ser.reset_input_buffer()

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            if self._in_monitor_mode:
                self.stop_monitor()
            self.ser.close()

    def _send_raw(self, cmd: str) -> str:
        assert self.ser is not None
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode("ascii"))
        raw = self.ser.read_until(b">")
        text = raw.decode("ascii", errors="replace")
        text = text.replace(cmd, "", 1).replace("\r", "\n").strip(">\n \r")
        return text.strip()

    def command(self, cmd: str) -> str:
        reply = self._send_raw(cmd)
        if reply.upper() in ("?", "NO DATA", "UNABLE TO CONNECT", "ERROR"):
            raise ELM327Error(f"{cmd} -> {reply}")
        return reply

    def initialize(self, protocol: str = "6") -> str:
        """Reset and configure the adapter. protocol '6' = ISO 15765-4 CAN 11bit 500kbps.
        '0' lets the adapter auto-detect the protocol instead.
        """
        self._send_raw("ATZ")
        time.sleep(0.5)
        self._send_raw("ATE0")   # echo off
        self._send_raw("ATL0")   # linefeeds off
        self._send_raw("ATH1")   # headers on (need the CAN ID in each line)
        self._send_raw("ATS1")   # spaces on (keeps ID/data bytes separable)
        reply = self._send_raw(f"ATSP{protocol}")
        return reply

    def start_monitor(self) -> None:
        """Enter ATMA (monitor all) passive listening mode."""
        assert self.ser is not None
        self.ser.reset_input_buffer()
        self.ser.write(b"ATMA\r")
        self._in_monitor_mode = True

    def stop_monitor(self) -> None:
        assert self.ser is not None
        self.ser.write(b"\x1b")  # ESC, or any byte, interrupts ATMA
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self._in_monitor_mode = False

    def read_monitor_lines(self):
        """Generator yielding raw text lines while in monitor mode."""
        assert self.ser is not None
        buf = b""
        while self._in_monitor_mode:
            chunk = self.ser.read(64)
            if not chunk:
                continue
            buf += chunk
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                text = line.decode("ascii", errors="replace").strip()
                if text:
                    yield text


COMMON_ELM_BAUDS = [38400, 9600, 115200, 230400, 57600, 500000]
SLCAN_PROBE_BAUDS = [115200, 230400, 1000000, 2000000]


class AdapterNotFoundError(ELM327Error):
    pass


class SLCANAdapterDetected(ELM327Error):
    def __init__(self, baud: int):
        self.baud = baud
        super().__init__(
            f"SLCAN protokolü konuşan bir adaptör bulundu ({baud} baud) — "
            "canspector şu an sadece ELM327 uyumlu adaptörleri destekliyor."
        )


def _try_elm_at_baud(port: str, baud: int) -> str | None:
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.write(b"ATI\r")
        time.sleep(0.4)
        raw = ser.read(64)
        ser.close()
    except serial.SerialException:
        return None
    text = raw.decode("ascii", errors="replace")
    if any(tag in text.upper() for tag in ("ELM", "OBD", "STN")):
        return text.strip(" \r\n>")
    return None


def _try_slcan_at_baud(port: str, baud: int) -> str | None:
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.write(b"V\r")
        time.sleep(0.4)
        raw = ser.read(32)
        ser.close()
    except serial.SerialException:
        return None
    if raw[:1] == b"V" and len(raw) > 1:
        return raw.decode("ascii", errors="replace").strip()
    return None


def autodetect_connect(port: str, protocol: str = "0") -> tuple["ELM327", str, int]:
    """Probe common baud rates to find a working ELM327-compatible adapter
    on `port`, without needing to know its exact model/chip beforehand.

    Returns (connected+initialized ELM327 instance, identity string, baud).
    Raises SLCANAdapterDetected if an SLCAN-protocol device answers instead
    (different hardware family, not supported here), or AdapterNotFoundError
    if nothing on the port answers either protocol.
    """
    for baud in COMMON_ELM_BAUDS:
        identity = _try_elm_at_baud(port, baud)
        if identity:
            elm = ELM327(port, baudrate=baud)
            elm.connect()
            elm.initialize(protocol=protocol)
            return elm, identity, baud

    for baud in SLCAN_PROBE_BAUDS:
        version = _try_slcan_at_baud(port, baud)
        if version:
            raise SLCANAdapterDetected(baud)

    raise AdapterNotFoundError(
        f"{port} üzerinde ELM327 ya da SLCAN protokolü konuşan bir cihaz bulunamadı."
    )


def parse_monitor_line(line: str):
    """Parse one ATMA output line into (can_id: int, data: bytes).
    Expected format with ATH1+ATS1: '7E8 04 41 04 00 00 00 00 00'
    Returns None if the line isn't a data frame (e.g. status text).
    """
    parts = line.split()
    if not parts:
        return None
    id_hex = parts[0]
    if not all(c in "0123456789ABCDEFabcdef" for c in id_hex):
        return None
    try:
        can_id = int(id_hex, 16)
        data_bytes = bytes(int(b, 16) for b in parts[1:] if len(b) == 2)
    except ValueError:
        return None
    return can_id, data_bytes
