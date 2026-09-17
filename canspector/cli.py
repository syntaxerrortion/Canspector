import argparse
import sys

from canspector.elm327 import AdapterNotFoundError, SLCANAdapterDetected, autodetect_connect
from canspector.tui import console, run_diff, run_monitor, run_replay


def main():
    parser = argparse.ArgumentParser(prog="canspector", description="ELM327 tabanlı CAN bus inceleme aracı")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_monitor = sub.add_parser("monitor", help="Canlı CAN trafiğini izle (cansniffer benzeri)")
    p_monitor.add_argument("--port", default="/dev/ttyUSB0")
    p_monitor.add_argument("--protocol", default="0", help="ELM327 ATSP protokol kodu (0=oto, 6=ISO15765-4 CAN 11bit 500k)")
    p_monitor.add_argument("--dbc", default=None, help="Sinyal çözmek için .dbc dosyası")
    p_monitor.add_argument("--log", default=None, help="Ham frame'leri bu dosyaya kaydet")
    p_monitor.add_argument("--autodetect", action="store_true", help="Baud hızını ve adaptör tipini otomatik bul")

    p_diff = sub.add_parser("diff", help="Önce/sonra karşılaştırmasıyla hangi ID'nin neyi kontrol ettiğini bul")
    p_diff.add_argument("--port", default="/dev/ttyUSB0")
    p_diff.add_argument("--protocol", default="0")
    p_diff.add_argument("--dbc", default=None)
    p_diff.add_argument("--autodetect", action="store_true")

    p_detect = sub.add_parser("detect", help="Porttaki adaptörün baud hızını ve kimliğini bul")
    p_detect.add_argument("--port", default="/dev/ttyUSB0")

    p_replay = sub.add_parser("replay", help="Daha önce kaydedilmiş bir log dosyasını incele")
    p_replay.add_argument("--file", required=True)
    p_replay.add_argument("--dbc", default=None)
    p_replay.add_argument("--realtime", action="store_true", help="Orijinal zamanlamayla oynat")

    args = parser.parse_args()

    if args.cmd == "monitor":
        run_monitor(args.port, args.protocol, args.dbc, args.log, autodetect=args.autodetect)
    elif args.cmd == "diff":
        run_diff(args.port, args.protocol, args.dbc, autodetect=args.autodetect)
    elif args.cmd == "replay":
        run_replay(args.file, args.dbc, args.realtime)
    elif args.cmd == "detect":
        try:
            elm, identity, baud = autodetect_connect(args.port)
            console.print(f"[green]Bulundu:[/] {identity} ({baud} baud)")
            elm.close()
        except SLCANAdapterDetected as e:
            console.print(f"[yellow]{e}[/]")
        except AdapterNotFoundError as e:
            console.print(f"[red]{e}[/]")


if __name__ == "__main__":
    sys.exit(main())
