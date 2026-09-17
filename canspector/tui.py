import threading
import time

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from canspector.busstate import BusState
from canspector.decoder import Decoder
from canspector.diffscan import DiffSession
from canspector.elm327 import ELM327, autodetect_connect, parse_monitor_line
from canspector.logger import FrameLogger, load_log

console = Console()


def _format_data_cell(frame) -> Text:
    text = Text()
    changed = set(frame.changed_byte_indexes())
    for i, byte in enumerate(frame.data):
        style = "bold red" if i in changed else "white"
        text.append(f"{byte:02X} ", style=style)
    return text


def _format_signals_cell(decoder: Decoder, can_id: int, data: bytes) -> str:
    signals = decoder.decode(can_id, data)
    if not signals:
        return ""
    return ", ".join(f"{k}={v}" for k, v in signals.items())


def build_table(bus_state: BusState, decoder: Decoder, show_signals: bool) -> Table:
    table = Table(title="canspector — live CAN bus", expand=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("DLC", justify="right")
    table.add_column("Data")
    table.add_column("Count", justify="right")
    table.add_column("Age (s)", justify="right")
    if show_signals:
        table.add_column("Signals")

    now = time.monotonic()
    for can_id in sorted(bus_state.frames):
        frame = bus_state.frames[can_id]
        age = now - frame.last_seen
        row = [
            f"{can_id:03X}",
            str(len(frame.data)),
            _format_data_cell(frame),
            str(frame.count),
            f"{age:.1f}",
        ]
        if show_signals:
            row.append(_format_signals_cell(decoder, can_id, frame.data))
        table.add_row(*row)
    return table


def _reader_thread(elm: ELM327, bus_state: BusState, logger: FrameLogger | None, stop_event: threading.Event):
    for line in elm.read_monitor_lines():
        if stop_event.is_set():
            break
        parsed = parse_monitor_line(line)
        if parsed is None:
            continue
        can_id, data = parsed
        bus_state.update(can_id, data)
        if logger is not None:
            logger.log(can_id, data)


def _connect(port: str, protocol: str, autodetect: bool) -> ELM327:
    if autodetect:
        elm, identity, baud = autodetect_connect(port, protocol=protocol)
        console.print(f"[green]Bulundu:[/] {identity} ({baud} baud)")
        return elm
    elm = ELM327(port)
    elm.connect()
    console.print(f"[green]Bağlandı:[/] {elm.command('ATI')}")
    elm.initialize(protocol=protocol)
    return elm


def run_monitor(port: str, protocol: str, dbc_path: str | None, log_path: str | None,
                 autodetect: bool = False, refresh_hz: float = 4.0):
    bus_state = BusState()
    decoder = Decoder(dbc_path)
    logger = FrameLogger(log_path) if log_path else None
    stop_event = threading.Event()

    elm = _connect(port, protocol, autodetect)
    elm.start_monitor()

    thread = threading.Thread(target=_reader_thread, args=(elm, bus_state, logger, stop_event), daemon=True)
    thread.start()

    try:
        with Live(build_table(bus_state, decoder, dbc_path is not None), console=console, refresh_per_second=refresh_hz) as live:
            while True:
                time.sleep(1.0 / refresh_hz)
                live.update(build_table(bus_state, decoder, dbc_path is not None))
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        elm.stop_monitor()
        thread.join(timeout=2.0)
        elm.close()
        if logger is not None:
            logger.close()
        console.print("\n[yellow]Durduruldu.[/]")


def _diff_table(results, decoder: Decoder) -> Table:
    table = Table(title="canspector — diff sonucu", expand=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Durum")
    table.add_column("Önce")
    table.add_column("Sonra")
    table.add_column("Sinyaller (sonra)")

    for r in results:
        before_text = Text(" ".join(f"{b:02X}" for b in r.before) if r.before else "—")
        after_text = Text()
        after_bytes = r.after or b""
        for i, byte in enumerate(after_bytes):
            style = "bold red" if i in r.changed_byte_indexes else "white"
            after_text.append(f"{byte:02X} ", style=style)
        signals = _format_signals_cell(decoder, r.can_id, r.after) if r.after else ""
        table.add_row(f"{r.can_id:03X}", r.status, before_text, after_text, signals)
    return table


def run_diff(port: str, protocol: str, dbc_path: str | None, autodetect: bool = False):
    bus_state = BusState()
    decoder = Decoder(dbc_path)
    stop_event = threading.Event()

    elm = _connect(port, protocol, autodetect)
    elm.start_monitor()

    thread = threading.Thread(target=_reader_thread, args=(elm, bus_state, None, stop_event), daemon=True)
    thread.start()

    session = DiffSession()
    try:
        console.print("[bold]Araçta hiçbir şey değiştirmeden[/] Enter'a bas — bu 'önce' anlık görüntüsü olacak.")
        input()
        session.take_snapshot_a(bus_state.snapshot())
        console.print(f"[green]Önce anlık görüntüsü alındı[/] ({len(session.snapshot_a)} ID).")

        while True:
            console.print("\n[bold]Şimdi aracta aksiyonu yap[/] (düğmeye bas vb.), sonra Enter'a bas ('q' + Enter çıkış):")
            answer = input()
            if answer.strip().lower() == "q":
                break
            session.take_snapshot_b(bus_state.snapshot())
            results = session.diff()
            if not results:
                console.print("[yellow]Hiçbir ID değişmedi.[/]")
                continue
            console.print(_diff_table(results, decoder))
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        elm.stop_monitor()
        thread.join(timeout=2.0)
        elm.close()
        console.print("\n[yellow]Durduruldu.[/]")


def run_replay(log_path: str, dbc_path: str | None, realtime: bool):
    decoder = Decoder(dbc_path)
    prev_ts = None
    for ts, can_id, data in load_log(log_path):
        if realtime and prev_ts is not None:
            time.sleep(max(0.0, ts - prev_ts))
        prev_ts = ts
        hex_data = " ".join(f"{b:02X}" for b in data)
        line = f"[cyan]{can_id:03X}[/]  {hex_data}"
        signals = _format_signals_cell(decoder, can_id, data) if dbc_path else ""
        if signals:
            line += f"   [dim]{signals}[/]"
        console.print(line)
