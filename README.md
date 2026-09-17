# canspector

ELM327-based CAN bus inspector with live monitoring, before/after diff analysis, and DBC signal decoding.

## Features

- **Live monitor** — cansniffer-style live table of every CAN ID seen, with changed bytes highlighted.
- **Diff mode** — capture a "before" snapshot, perform an action in the vehicle, capture "after", and see exactly which IDs/bytes changed. Built for reverse-engineering what a given CAN ID controls.
- **DBC decoding** — optionally load a `.dbc` file to show human-readable signal names/values instead of raw bytes.
- **Logging & replay** — save raw captures to a file and replay them later, with or without original timing.
- **Adapter autodetection** — probes common baud rates to find and identify an ELM327-compatible adapter automatically, and detects if an SLCAN-protocol device is connected instead.

## Requirements

- An ELM327-compatible USB/OBD2 adapter
- Python 3.11+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# live view
python3 -m canspector.cli monitor --port /dev/ttyUSB0 [--dbc file.dbc] [--log capture.log] [--autodetect]

# find what a specific action controls
python3 -m canspector.cli diff --port /dev/ttyUSB0 [--autodetect]

# review a previous capture offline
python3 -m canspector.cli replay --file capture.log [--dbc file.dbc] [--realtime]

# just identify the adapter on a port
python3 -m canspector.cli detect --port /dev/ttyUSB0
```

## Contributors

- **[syntaxerrortion](https://github.com/syntaxerrortion)** — concept & idea
- Implementation built with [Claude Code](https://claude.com/claude-code)
