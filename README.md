# ROBLOX 2017 – App Icon Replacer

A small Windows tray tool (ROHTML App Icon Replacer) that swaps the Roblox window's title and taskbar icon for a classic one. It defaults to the **2017** icon.

## Launcher
Run `python launcher.py` (Windows). It has three tabs:
- **Toolbox Models**: search all 52 models and double-click one to open it in Studio.
- **Places**: open the place files.
- **Icon Replacer**: pick an icon with a preview, set the window title, and start or stop the replacer.

The icon preview uses Pillow (`pip install Pillow`).

## Usage
1. Install Python 3 on Windows.
2. Run `python rohtml_icon_replacer.py`. Missing dependencies (psutil, pystray, Pillow, pywin32) are installed automatically.
3. Launch Roblox. Its window icon and title change right away.

## Configuration
Edit `rohtmlconfig.json`. Changes are picked up live, with no restart needed.

```json
{ "window": { "title": "ROBLOX", "icon": "roblox2017.ico" } }
```

Available icons are in `icons/`: roblox2006, roblox2012, roblox2016, roblox2017, roblox2019, roblox2022 and RBLXSTUDIO, RCC, roldblox.

## Building an .exe (optional)
```
pip install pyinstaller
pyinstaller --onefile --noconsole --icon icons/roblox2017.ico rohtml_icon_replacer.py
```
Put the resulting exe next to `rohtmlconfig.json` and the `icons/` folder.

## ToolboxModels
The `ToolboxModels/` folder holds the 2004–05 Roblox toolbox models (.rbxm), from Block 2x4x1 to Red Figure. They were originally collected by Client Search. See `ToolboxModels/README.md` for history and notes. Insert them into an older Studio version (2007–2008) first, because they get corrupted in modern Studio.

## Places
- `Places/Mobile.rbxl`: Mobile place file. Open it in Roblox Studio.

## Web launcher
https://jogresh7-ship-it.github.io/ROBLOX-2017/ lets you browse every model with a 3D thumbnail. Click a model to open an interactive 3D viewer with a grass baseplate, an adjustable foliage amount, studs and auto-rotate. The viewer reads the original .rbxm files directly. To add a model, put it in `ToolboxModels/` and add its file name to the `FILES` list in `index.html`.
