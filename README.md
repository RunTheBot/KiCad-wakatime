# KiCad WakaTime

Track your KiCad design time with WakaTime.

## Features

- Tracks active KiCad windows
- Reports time spent on KiCad projects to WakaTime
- Works with KiCad schematic editor, PCB editor, and other KiCad tools

## Todo

- [ ] Add configuration menu to set WakaTime API key and URL
- [ ] Test on other KiCad versions
- [ ] Add support for Mac and Linux
- [ ] Mouse and keyboard activity tracking

## Requirements

- WakaTime account with API key and URL configured
- WakaTime CLI installed (`~/.wakatime/wakatime-cli.*`)
- KiCad 9+ (or with IPC support)

### Tested on
- KiCad 9.0.0
- WakaTime CLI v1.115.3
- Windows 11
- Python 3.13.2

Configuration menu will be added in the future.

## Usage
Run the script in the background while using KiCad

## Installation

Build or run the script youself with instructions below, or download the pre-built binary from the releases page.

Alternatively, you can use run the script directly.

### Build from source (Windows)

#### Prerequisites

- Python 3.8 or later
- pip (Python package installer)
- pyinstaller (for building the executable)

#### Configure venv

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### Install dependencies

```pwsh
pip install -r requirements.txt
```

#### Build the executable

```pwsh
pyinstaller --onefile --console --paths .\.venv\Lib\site-packages .\kicad_wakatime.py
```

## Troubleshooting

Check the log file at `~/.wakatime/kicad-wakatime.log` for any errors.

## License

MIT
