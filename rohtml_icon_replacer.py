import os
import json
import time
import sys
import subprocess
import importlib.util

# --- Dependency Management ---
def install_missing_package(package_name, pip_name=None):
    """Install missing package if not available (only for .py source)"""
    if getattr(sys, 'frozen', False):
        return
        
    if pip_name is None:
        pip_name = package_name
    
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is not None:
            return
    except (ImportError, ValueError):
        pass
    
    print(f"Installing missing dependency: {pip_name}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
    except Exception as e:
        print(f"Failed to install {pip_name}: {e}")

# Install dependencies if running as script
if not getattr(sys, 'frozen', False):
    install_missing_package("psutil")
    install_missing_package("pystray")
    install_missing_package("Pillow", "Pillow")
    install_missing_package("pywin32", "pywin32")

import psutil
import gc
import threading
import ctypes
import ctypes.wintypes

# --- WinEventHook Definitions ---
user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32

EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_NAMECHANGE = 0x800C
WINEVENT_OUTOFCONTEXT = 0x0000

WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD
)

# Shared flag for instant updates
_instant_update_requested = threading.Event()
_config_update_requested = threading.Event()

def win_event_handler(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    # We only care about window creation or name changes
    if idObject == 0: # OBJID_WINDOW
        _instant_update_requested.set()

def watch_config_file():
    """Watch the config file for changes using a more robust method than mtime polling alone"""
    last_mtime = 0
    if os.path.exists(CONFIG_PATH):
        last_mtime = os.path.getmtime(CONFIG_PATH)
    
    while True:
        try:
            if os.path.exists(CONFIG_PATH):
                current_mtime = os.path.getmtime(CONFIG_PATH)
                if current_mtime > last_mtime:
                    last_mtime = current_mtime
                    _config_update_requested.set()
        except Exception:
            pass
        time.sleep(0.05) # Check every 50ms

def start_win_event_hook():
    """Starts a Windows Event Hook to detect window creation instantly"""
    ole32.CoInitialize(None)
    
    proc = WinEventProcType(win_event_handler)
    
    # Hook for window creation
    hook_create = user32.SetWinEventHook(
        EVENT_OBJECT_CREATE, EVENT_OBJECT_CREATE,
        0, proc, 0, 0, WINEVENT_OUTOFCONTEXT
    )
    
    # Hook for title changes (in case Roblox launches with a generic title first)
    hook_name = user32.SetWinEventHook(
        EVENT_OBJECT_NAMECHANGE, EVENT_OBJECT_NAMECHANGE,
        0, proc, 0, 0, WINEVENT_OUTOFCONTEXT
    )
    
    if not hook_create or not hook_name:
        print("[ERROR] Failed to set WinEventHook")
        return

    # Message loop is required for the hook to work
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
        user32.TranslateMessageW(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    user32.UnhookWinEvent(hook_create)
    user32.UnhookWinEvent(hook_name)
    ole32.CoUninitialize()

try:
    from PIL import Image, ImageDraw
    import pystray
except ImportError:
    print("Critical dependencies missing. Please install pystray and Pillow.")
    # We'll continue and see if we can still run the main logic without tray
    pystray = None

# Import win32 modules
try:
    import win32gui
    import win32con
    import win32api
    import win32process
except ImportError:
    print("Win32 modules not available. Please ensure pywin32 is properly installed.")
    sys.exit(1)

# --- Constants & Paths ---
APP_NAME = "ROHTML - App Icon Replacer"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)

CONFIG_PATH = os.path.join(BASE_DIR, 'rohtmlconfig.json')
ICONS_DIR = os.path.join(BASE_DIR, 'icons')

# --- Memory Optimization: Global Cache ---
_cache = {
    "config": None,
    "last_config_mtime": 0,
    "icon_paths": {},
    "roblox_pids": set() # Cache Roblox PIDs to avoid repeated process lookups
}

def get_config_optimized():
    """Reads the configuration file only if it has changed on disk."""
    if not os.path.exists(CONFIG_PATH):
        return None
    
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime > _cache["last_config_mtime"]:
            with open(CONFIG_PATH, 'r') as f:
                _cache["config"] = json.load(f)
                _cache["last_config_mtime"] = mtime
        return _cache["config"]
    except Exception as e:
        print(f"[ERROR] Error reading config: {e}")
        return None

def is_roblox_process(pid):
    """Check if a PID belongs to RobloxPlayerBeta.exe efficiently."""
    try:
        if pid in _cache["roblox_pids"]:
            return True
        proc = psutil.Process(pid)
        if proc.name().lower() == 'robloxplayerbeta.exe':
            _cache["roblox_pids"].add(pid)
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return False

def find_roblox_windows_optimized():
    """Finds all window handles (HWNDs) associated with RobloxPlayerBeta.exe efficiently."""
    hwnds = []
    
    # 1. Fast check: Find window by class name if possible (Roblox uses "WindowsPlayer")
    # This works regardless of the window title
    hwnd_fast = win32gui.FindWindow("WindowsPlayer", None)
    if hwnd_fast and win32gui.IsWindowVisible(hwnd_fast):
        _, pid = win32process.GetWindowThreadProcessId(hwnd_fast)
        if is_roblox_process(pid):
            hwnds.append(hwnd_fast)
    
    # 2. If not found via class, or to find multiple instances, fallback to enumeration
    # CRITICAL: We remove the title-based filtering because the user might have renamed the window
    if not hwnds:
        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                # We check the process ID directly for visible windows
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if is_roblox_process(pid):
                    hwnds.append(hwnd)
            return True
        
        try:
            win32gui.EnumWindows(enum_windows_callback, None)
        except Exception as e:
            print(f"[ERROR] Error enumerating windows: {e}")
    
    return hwnds

def update_window_properties(hwnd, title, icon_path):
    """Changes the title and icon of a specific window."""
    try:
        current_title = win32gui.GetWindowText(hwnd)
        
        # 1. Update Title
        if current_title != title:
            win32gui.SetWindowText(hwnd, title)
            print(f"[INFO] Window title changed: '{current_title}' -> '{title}'")
        
        # 2. Update Icon
        if os.path.exists(icon_path):
            hicon = win32gui.LoadImage(
                None, 
                icon_path, 
                win32con.IMAGE_ICON, 
                0, 0, 
                win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            )
            
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon)
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, hicon)
            
            print(f"[INFO] Window icon applied: '{os.path.basename(icon_path)}' to window '{win32gui.GetWindowText(hwnd)}'")
            return True
        else:
            print(f"[ERROR] Icon file not found: {icon_path}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to update window properties: {e}")
        return False

# --- System Tray Functions ---
def create_image():
    """Create or load the icon for the system tray"""
    if pystray is None:
        return None
        
    try:
        config = get_config_optimized()
        if config and 'window' in config:
            icon_filename = config['window'].get('icon', 'roblox2016.ico')
            icon_path = os.path.join(ICONS_DIR, icon_filename)
            if os.path.exists(icon_path):
                return Image.open(icon_path).resize((64, 64), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"[DEBUG] Tray icon creation failed: {e}")
    
    # Fallback icon
    try:
        image = Image.new('RGB', (64, 64), color=(0, 100, 200))
        dc = ImageDraw.Draw(image)
        dc.text((15, 20), "RO", fill='white')
        return image
    except Exception:
        return None

def update_tray_icon(icon):
    """Update the tray icon to match current config"""
    if icon:
        new_img = create_image()
        if new_img:
            icon.icon = new_img

def on_quit(icon, item):
    print(f"Quitting {APP_NAME}...")
    if icon:
        icon.stop()
    os._exit(0)

def setup_tray():
    if pystray is None:
        return None
    try:
        menu = pystray.Menu(pystray.MenuItem("Quit", on_quit))
        icon_img = create_image()
        if icon_img:
            icon = pystray.Icon(APP_NAME, icon_img, APP_NAME, menu)
            return icon
    except Exception as e:
        print(f"[ERROR] Failed to setup tray: {e}")
    return None

def main(tray_icon=None):
    print(f"{APP_NAME} Monitoring Started")
    
    last_full_scan = 0
    was_roblox_running = False
    
    # Timing
    POLL_INTERVAL = 0.05      # 50ms loop
    FULL_SCAN_INTERVAL = 2.0  # 2s background scan
    
    gc.collect()
    
    try:
        while True:
            current_time = time.time()
            force_update = False
            
            # Periodically clean up stale PIDs from cache (once per minute)
            if current_time % 60 < 0.1:
                try:
                    active_pids = {p.pid for p in psutil.process_iter(['pid'])}
                    _cache["roblox_pids"] = {pid for pid in _cache["roblox_pids"] if pid in active_pids}
                except Exception:
                    pass

            # 1. Instant Event Check (from WinEventHook)
            if _instant_update_requested.is_set():
                _instant_update_requested.clear()
                print("[EVENT] Roblox launch/activity detected - Updating properties.")
                force_update = True

            # 2. Fast Config Check (via Event from watch_thread)
            if _config_update_requested.is_set():
                _config_update_requested.clear()
                print("[EVENT] Configuration changed - Applying to all windows.")
                get_config_optimized() # Force refresh cache
                force_update = True
                if tray_icon:
                    update_tray_icon(tray_icon)

            # 3. Window Detection
            if force_update or (current_time - last_full_scan >= FULL_SCAN_INTERVAL):
                hwnds = find_roblox_windows_optimized()
                last_full_scan = current_time
                
                if hwnds:
                    if not was_roblox_running:
                        print(f"[EVENT] Roblox detected ({len(hwnds)} windows) - Updating properties ASAP.")
                    
                    # Ensure we have the latest config if force_update is set
                    config = get_config_optimized() if force_update else (_cache["config"] or get_config_optimized())
                    
                    if config and 'window' in config:
                        target_title = config['window'].get('title', 'ROBLOX')
                        icon_filename = config['window'].get('icon', 'roblox2016.ico')
                        icon_path = os.path.join(ICONS_DIR, icon_filename)
                        
                        for hwnd in hwnds:
                            # Update if:
                            # 1. Force update (config changed or launch event)
                            # 2. First detection of Roblox
                            # 3. Current title doesn't match target title
                            # 4. Current title has reverted to "Roblox" (and our target isn't "Roblox")
                            current_title = win32gui.GetWindowText(hwnd)
                            if force_update or not was_roblox_running or current_title != target_title or (current_title == "Roblox" and target_title != "Roblox"):
                                update_window_properties(hwnd, target_title, icon_path)
                    
                    was_roblox_running = True
                else:
                    if was_roblox_running:
                        print("[EVENT] Roblox closed.")
                        was_roblox_running = False
                        gc.collect()

            time.sleep(POLL_INTERVAL)
    except Exception as e:
        print(f"\n[CRITICAL] Main loop error: {e}")

def check_single_instance():
    """Check if another instance is already running using a Windows Mutex"""
    if sys.platform != "win32":
        return None
    
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mutex_name = "Global\\ROHTML_AppIconReplacer_Mutex"
    
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    
    if last_error == 183: # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(mutex)
        return None
    return mutex

if __name__ == "__main__":
    # Singleton Check
    mutex = check_single_instance()
    if not mutex:
        print("[DEBUG] Another instance is already running. Exiting.")
        sys.exit(0)
        
    # Hide console ONLY if running as EXE
    if getattr(sys, 'frozen', False) and sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    
    # Start the WinEventHook in a separate thread for instant detection
    hook_thread = threading.Thread(target=start_win_event_hook, daemon=True)
    hook_thread.start()
    
    # Start config watcher thread
    watch_thread = threading.Thread(target=watch_config_file, daemon=True)
    watch_thread.start()
    
    icon = setup_tray()
    try:
        if icon:
            thread = threading.Thread(target=main, args=(icon,), daemon=True)
            thread.start()
            print("Starting System Tray...")
            icon.run()
        else:
            print("Running without System Tray...")
            main()
    finally:
        # Release the mutex if we have it
        if mutex and sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.CloseHandle(mutex)
