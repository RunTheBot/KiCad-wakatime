# KiCad WakaTime

Track your KiCad design time with WakaTime.

## Pay attention to console warnings otherwise your your time will not be tracked!

See [Known Issues](#known-issues) for more information.

## Features

- Tracks active KiCad windows
- Reports time spent on KiCad projects to WakaTime
- Works with KiCad schematic editor, PCB editor, and other KiCad tools

## How it works
Looks at window names to determine if KiCad is active, and uses WakaTime CLI to report time spent in KiCad.

### KiCad IPC SUCKS

The API is very limited and inconsistent across document types. I plan to add support for KiCad IPC in the future, but for now this is the best I can do.

### Getting absolute path of active project

The script reads the KiCad config that conviniently lists the absolute path of the active project. 

## Todo

- [ ] Add configuration menu to set WakaTime API key and URL
- [ ] Test on other KiCad versions
- [ ] Add support for Mac and Linux
- [X] Mouse and keyboard activity tracking
- [ ] Actually use KiCad IPC to get active window

## Known Issues
Only works if all three KiCad files (schematic, PCB, and project) have the same name and are in the same directory.

Will not work with multiple KiCad projects open at the same time. (Will be buggy only will tack for the last opened project)

## Requirements

- WakaTime account with API key and URL configured
- WakaTime CLI installed (`~/.wakatime/wakatime-cli.*`)

### Tested on
- KiCad 9.0.2
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
