import tkinter as tk
from tkinter import messagebox, simpledialog
import platform
import socket
import uuid
import json
import urllib.request
import urllib.error
import subprocess
import psutil
import os
import threading
import time
import sys
import re
import logging
import traceback
import base64
import random
from datetime import datetime
import ssl
import queue

# --- MACOS SSL CERTIFICATE FIX ---
if getattr(ssl, '_create_unverified_context', None):
    ssl._create_default_https_context = ssl._create_unverified_context

SYS_OS = platform.system()

# --- OS SPECIFIC IMPORTS ---
if SYS_OS == "Darwin":
    try:
        from tkmacosx import Button as TkButton
    except ImportError:
        TkButton = tk.Button
else:
    TkButton = tk.Button
    import winreg as reg
    import pystray
    from pystray import MenuItem as item

from PIL import Image, ImageDraw, ImageGrab

# --- CONFIGURATION ---
AGENT_VERSION = "3.0.0"
ADMIN_PASSWORD = "1886wysiwyG"     

# --- ANTI-CLOUDFLARE HEADERS ---
STD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, */*'
}

# --- STYLING (MODERN DASHBOARD) ---
BG_MAIN = "#1e1e24"        
BG_CARD = "#2b2d35"        
BG_SCREEN = "#050505"
BG_BTN = "#38bdf8"         
BG_BTN_DARK = "#334155"    
BG_BTN_DANGER = "#ef4444"
FG_CYAN = "#38bdf8"        
FG_WHITE = "#ffffff"       
FG_MUTED = "#94a3b8"       
FG_GREEN = "#34d399"       
FG_DANGER = "#ef4444"
BG_GREEN = "#34d399"       
BG_BTN_EDIT = "#eab308"    
FG_WARN = "#fbbf24"

FONT_MONO = ("Consolas", 10)
FONT_MONO_BOLD = ("Consolas", 10, "bold")
FONT_TITLE = ("Helvetica Neue", 18, "bold")
FONT_SUB = ("Helvetica Neue", 11)
FONT_CARD_TITLE = ("Helvetica Neue", 12, "bold")

# ==========================================
# UNIFIED PERSISTENT CONFIGURATION & LOGGING
# ==========================================
if SYS_OS == "Darwin":
    AGENT_CONFIG_DIR = os.path.join(os.path.expanduser('~'), "Library", "Application Support", "Techtix", "OmniDeployAgent")
else:
    AGENT_CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "Techtix", "OmniDeployAgent")

os.makedirs(AGENT_CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(AGENT_CONFIG_DIR, "agent_config.json")
LOG_FILE = os.path.join(AGENT_CONFIG_DIR, "omnideploy-logs.txt")

logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def upload_logs_to_server():
    try:
        if not SERVER_URL or not ASSET_TAG or not AGENT_API_KEY: return
        if not os.path.exists(LOG_FILE): return
        with open(LOG_FILE, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode('utf-8')
        payload = {"api_key": AGENT_API_KEY, "asset_tag": ASSET_TAG, "file_name": f"CRASH_LOG_{datetime.now().strftime('%H%M%S')}.txt", "file_data": b64_data}
        headers = STD_HEADERS.copy()
        headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(f"{SERVER_URL}/api/upload", data=json.dumps(payload).encode('utf-8'), headers=headers)
        urllib.request.urlopen(req, timeout=5)
    except Exception: pass

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("UNCAUGHT FATAL EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))
    threading.Thread(target=upload_logs_to_server, daemon=True).start()
    time.sleep(2) 

sys.excepthook = global_exception_handler
logging.info(f"=== OmniDeploy Agent v{AGENT_VERSION} Booting ===")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {}

def save_config(data):
    cfg = load_config()
    cfg.update(data)
    with open(CONFIG_FILE, 'w') as f: json.dump(cfg, f)

def init_agent_identity():
    cfg = load_config()
    updated = False
    
    def ensure_focus():
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        if SYS_OS == "Darwin": os.system(f'''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of every process whose unix id is {os.getpid()} to true' ''')
        return root

    server_url = cfg.get("server_url")
    if not server_url:
        root = ensure_focus()
        url = simpledialog.askstring("OmniDeploy Setup", "1/3: Enter Server URL\n(e.g. http://10.54.22.15:8080):")
        root.destroy()
        if not url: sys.exit(0)
        server_url = url.strip().rstrip('/')
        if not server_url.startswith("http"): server_url = "http://" + server_url
        cfg["server_url"] = server_url
        updated = True

    api_key = cfg.get("api_key")
    if not api_key:
        root = ensure_focus()
        api_key = simpledialog.askstring("OmniDeploy Setup", "2/3: Enter Agent API Key\n(e.g., TTX-...):")
        root.destroy()
        if not api_key: sys.exit(0)
        cfg["api_key"] = api_key.strip()
        updated = True

    asset_tag = cfg.get("asset_tag")
    if SYS_OS == "Windows":
        if not asset_tag:
            asset_tag = socket.gethostname().upper()
            cfg["asset_tag"] = asset_tag
            updated = True
    elif not asset_tag:
        root = ensure_focus()
        tag = simpledialog.askstring("OmniDeploy Setup", "3/3: Enter Asset Tag for this Mac\n(e.g. MAC.OFFICE):")
        root.destroy()
        asset_tag = tag.strip().upper() if tag else socket.gethostname().upper()
        cfg["asset_tag"] = asset_tag
        updated = True

    if updated: save_config(cfg)
    return cfg["server_url"], cfg["api_key"], cfg["asset_tag"]

SERVER_URL, AGENT_API_KEY, ASSET_TAG = init_agent_identity()
logging.info(f"Identity Configured. URL: {SERVER_URL} | Asset: {ASSET_TAG}")

SAFE_ACTIONS = {
    "Windows": {
        "FLUSH_DNS": "ipconfig /flushdns",
        "CLEAR_TEMP": r"powershell.exe -Command Remove-Item -Path $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue",
        "RESTART_SPOOLER": "net stop spooler & net start spooler",
        "UPDATE_GP": "gpupdate /force",
        "UPDATE_WINDOWS": "UsoClient.exe ScanInstallWait"
    },
    "Darwin": {
        "FLUSH_DNS": "sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder",
        "CLEAR_TEMP": "rm -rf ~/Library/Caches/* ~/.Trash/*",
        "RESTART_SPOOLER": "sudo launchctl stop org.cups.cupsd && sudo launchctl start org.cups.cupsd",
        "UPDATE_GP": "echo 'No Group Policy on macOS'",
        "UPDATE_WINDOWS": "softwareupdate -i -a"
    }
}

AGENT_CACHE = {}
ACTIVE_MINUTES_TODAY = 0

def execute_cmd(cmd):
    try:
        if SYS_OS == "Windows":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.check_output(f'powershell.exe -Command "{cmd}"', shell=True, stderr=subprocess.DEVNULL, startupinfo=si).decode('utf-8', errors='ignore').strip()
        else: return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
    except Exception: return ""

def get_size(bytes_val):
    factor = 1024
    for unit in ["", "KB", "MB", "GB", "TB"]:
        if bytes_val < factor: return f"{bytes_val:.2f} {unit}"
        bytes_val /= factor
    return f"{bytes_val:.2f} PB"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception: return "127.0.0.1"

def initialize_cache():
    logging.info("Initializing hardware cache...")
    global AGENT_CACHE
    if SYS_OS == "Windows":
        AGENT_CACHE['make'] = execute_cmd("(Get-CimInstance Win32_ComputerSystem).Manufacturer")
        AGENT_CACHE['model'] = execute_cmd("(Get-CimInstance Win32_ComputerSystem).Model")
        AGENT_CACHE['serial'] = execute_cmd("(Get-CimInstance Win32_BIOS).SerialNumber")
        AGENT_CACHE['purchase_date'] = execute_cmd("(Get-CimInstance Win32_BIOS).ReleaseDate.ToString('yyyy-MM-dd')")
        dn = execute_cmd("$s = New-Object -ComObject 'ADSystemInfo'; $s.ComputerName")
        AGENT_CACHE['domain_location'] = dn if dn else "WORKGROUP"
        gpu = execute_cmd("(Get-CimInstance Win32_VideoController).Name")
        AGENT_CACHE['gpu'] = gpu if gpu else "Unknown GPU"
        sw_output = execute_cmd("Get-ItemProperty HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName | Where-Object {$_.DisplayName -ne $null} | Sort-Object -Unique DisplayName")
        AGENT_CACHE['software'] = " | ".join([line.strip() for line in sw_output.split('\n')[2:] if line.strip()])
        ad_id = execute_cmd(r'& "C:\Program Files (x86)\AnyDesk\AnyDesk.exe" --get-id')
        AGENT_CACHE['anydesk'] = ad_id if ad_id else "NOT INSTALLED"
    elif SYS_OS == "Darwin":
        AGENT_CACHE['make'] = "Apple"
        AGENT_CACHE['model'] = execute_cmd("sysctl -n hw.model")
        AGENT_CACHE['serial'] = execute_cmd("ioreg -l | grep IOPlatformSerialNumber | awk '{print $4}' | tr -d '\"'")
        AGENT_CACHE['purchase_date'] = "Unknown"
        AGENT_CACHE['domain_location'] = "Local Mac"
        AGENT_CACHE['gpu'] = execute_cmd("system_profiler SPDisplaysDataType | awk -F': ' '/Chipset Model/ {print $2}'")
        sw_output = execute_cmd("ls /Applications | grep '\\.app$' | sed 's/.app//g'")
        AGENT_CACHE['software'] = " | ".join(sw_output.split('\n')) if sw_output else "N/A"
        ad_id = execute_cmd("/Applications/AnyDesk.app/Contents/MacOS/AnyDesk --get-id")
        AGENT_CACHE['anydesk'] = ad_id if ad_id else "NOT INSTALLED"
    else:
        for k in ['make', 'model', 'serial', 'purchase_date', 'domain_location', 'gpu', 'software', 'anydesk']: AGENT_CACHE[k] = "Unknown OS"
    logging.info("Hardware cache initialized.")

def gather_telemetry():
    # CRASH FIX: Ensure process memory isolation doesn't push empty cache
    if not AGENT_CACHE:
        initialize_cache()

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = f"{(datetime.now() - boot_time).days} Days"
    try: current_user = psutil.users()[0].name if psutil.users() else "UNKNOWN"
    except Exception: current_user = "SYSTEM"
    try: 
        req = urllib.request.Request('https://api.ipify.org', headers=STD_HEADERS)
        pub_ip = urllib.request.urlopen(req, timeout=3).read().decode('utf8')
    except Exception: pub_ip = "UNAVAILABLE"
    
    if SYS_OS == "Windows": bitlocker = execute_cmd("(Get-BitLockerVolume -MountPoint C:).ProtectionStatus")
    elif SYS_OS == "Darwin": bitlocker = "ON" if "FileVault is On" in execute_cmd("fdesetup status") else "OFF"
    else: bitlocker = "UNVERIFIED"

    disks, disk_warning = [], False
    try:
        for p in psutil.disk_partitions():
            if 'cdrom' not in p.opts and p.fstype != '':
                usage = psutil.disk_usage(p.mountpoint)
                disks.append(f"{p.device} {get_size(usage.total)}")
                if (p.device.startswith("C:") or p.device == "/") and usage.percent > 90: disk_warning = True
    except: pass

    battery = "N/A"
    try:
        bat = psutil.sensors_battery()
        if bat: battery = f"{bat.percent}% {'(Plugged In)' if bat.power_plugged else '(Discharging)'}"
    except Exception: pass
        
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1]).upper()
    return {
        "api_key": AGENT_API_KEY, "asset_tag": ASSET_TAG, "make": AGENT_CACHE.get('make', 'Unknown'), "model": AGENT_CACHE.get('model', 'Unknown'), 
        "serial": AGENT_CACHE.get('serial', 'Unknown'), "os": f"{platform.system()} {platform.release()}", "cpu": platform.processor() or "Apple Silicon", 
        "ram": get_size(psutil.virtual_memory().total), "storage": " | ".join(disks), "gpu": AGENT_CACHE.get('gpu', 'Unknown'), 
        "ip_address": get_local_ip(), "public_ip": pub_ip, "mac_address": mac, "current_user": current_user, "uptime": uptime, 
        "bitlocker": bitlocker or "UNVERIFIED", "domain_location": AGENT_CACHE.get('domain_location', 'Unknown'), 
        "purchase_date": AGENT_CACHE.get('purchase_date', 'Unknown'), "software_installed": AGENT_CACHE.get('software', 'Unknown'), 
        "agent_version": AGENT_VERSION, "anydesk_id": AGENT_CACHE.get('anydesk', 'Unknown'), "battery": battery, 
        "disk_warning": disk_warning, "active_minutes": ACTIVE_MINUTES_TODAY
    }

# ==========================================
# UI SPWNER & DOCK FIX
# ==========================================
def spawn_ui(flag):
    logging.info(f"Spawning UI Window with flag: {flag}")
    if getattr(sys, 'frozen', False):
        exe_path = os.path.abspath(sys.executable)
        if SYS_OS == "Darwin" and ".app/Contents/MacOS" in exe_path:
            app_path = exe_path.split(".app/Contents/MacOS")[0] + ".app"
            subprocess.Popen(["open", "-n", "-a", app_path, "--args", flag])
        else: subprocess.Popen([exe_path, flag])
    else: subprocess.Popen([sys.executable, sys.argv[0], flag])

def show_dock_icon():
    if SYS_OS == "Darwin":
        try:
            from AppKit import NSApplication
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(0)
            app.activateIgnoringOtherApps_(True)
        except Exception: pass

# ==========================================
# MODERN SYSTEM DASHBOARD
# ==========================================
def draw_arc_meter(canvas, x, y, radius, percentage, color, title, value_text):
    canvas.create_arc(x-radius, y-radius, x+radius, y+radius, start=180, extent=-180, style=tk.ARC, outline="#475569", width=10)
    extent = -180 * (percentage / 100)
    canvas.create_arc(x-radius, y-radius, x+radius, y+radius, start=180, extent=extent, style=tk.ARC, outline=color, width=10)
    canvas.create_text(x, y-radius-18, text=title, fill=FG_WHITE, font=("Helvetica Neue", 10))
    canvas.create_text(x, y-10, text=value_text, fill=FG_WHITE, font=("Helvetica Neue", 12, "bold"))

def run_info_ui():
    root = tk.Tk()
    root.report_callback_exception = global_exception_handler
    show_dock_icon()
    root.title("System Monitor")
    root.configure(bg=BG_MAIN)
    root.resizable(False, False)
    
    ui_queue = queue.Queue()
    def process_queue():
        try:
            while True: ui_queue.get_nowait()()
        except queue.Empty: pass
        root.after(100, process_queue)
    process_queue()

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"850x620+{(sw-850)//2}+{(sh-620)//2}")
    
    header = tk.Frame(root, bg=BG_MAIN, pady=15, padx=25)
    header.pack(fill='x')
    tk.Label(header, text="System Monitor", fg=FG_WHITE, bg=BG_MAIN, font=FONT_TITLE).pack(side='left')
    lbl_comp_header = tk.Label(header, text=" | Loading...", fg=FG_MUTED, bg=BG_MAIN, font=("Helvetica Neue", 14))
    lbl_comp_header.pack(side='left', padx=5, pady=(2,0))
    
    status_frame = tk.Frame(header, bg=BG_MAIN)
    status_frame.pack(side='right')
    tk.Label(status_frame, text=f"v{AGENT_VERSION}   Status: ", fg=FG_WHITE, bg=BG_MAIN, font=FONT_SUB).pack(side='left')
    lbl_net_status = tk.Label(status_frame, text="CHECKING...", fg=FG_MUTED, bg=BG_MAIN, font=("Helvetica Neue", 11, "bold"))
    lbl_net_status.pack(side='left')

    content = tk.Frame(root, bg=BG_MAIN, padx=20)
    content.pack(fill='both', expand=True)
    
    card1 = tk.Frame(content, bg=BG_CARD, highlightbackground="#334155", highlightthickness=1)
    card1.place(x=0, y=0, width=250, height=240)
    tk.Label(card1, text="Client Identification", fg=FG_WHITE, bg=BG_CARD, font=FONT_CARD_TITLE).place(x=15, y=15)
    tk.Label(card1, text="Client Name:", fg=FG_MUTED, bg=BG_CARD, font=FONT_SUB).place(x=15, y=50)
    tk.Label(card1, text=ASSET_TAG, fg=FG_WHITE, bg=BG_CARD, font=FONT_SUB).place(x=105, y=50)
    tk.Label(card1, text="Company:", fg=FG_MUTED, bg=BG_CARD, font=FONT_SUB).place(x=15, y=80)
    lbl_comp = tk.Label(card1, text="Fetching...", fg=FG_WHITE, bg=BG_CARD, font=FONT_SUB)
    lbl_comp.place(x=105, y=80)

    reg_date = AGENT_CACHE.get('purchase_date', datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
    tk.Label(card1, text=f"Registration Date:\n{reg_date}", fg=FG_MUTED, bg=BG_CARD, font=("Helvetica Neue", 10)).place(x=15, y=130)
    TkButton(card1, text="Software Center", bg=BG_BTN, fg=FG_WHITE, font=("Helvetica Neue", 10, "bold"), relief='flat', command=lambda: [root.destroy(), spawn_ui('--ui-store')]).place(x=15, y=195, width=220, height=30)

    card2 = tk.Frame(content, bg=BG_CARD, highlightbackground="#334155", highlightthickness=1)
    card2.place(x=265, y=0, width=320, height=240)
    tk.Label(card2, text="System Performance", fg=FG_WHITE, bg=BG_CARD, font=FONT_CARD_TITLE).place(x=15, y=15)
    meter_canvas = tk.Canvas(card2, width=310, height=100, bg=BG_CARD, highlightthickness=0)
    meter_canvas.place(x=5, y=50)
    tk.Label(card2, text=f"OS: {platform.system()} ({platform.release()})", fg=FG_WHITE, bg=BG_CARD, font=FONT_SUB).place(x=15, y=160)
    lbl_uptime = tk.Label(card2, text="Uptime: Calculating...", fg=FG_WHITE, bg=BG_CARD, font=FONT_SUB)
    lbl_uptime.place(x=15, y=190)

    card3 = tk.Frame(content, bg=BG_CARD, highlightbackground="#334155", highlightthickness=1)
    card3.place(x=600, y=0, width=210, height=240)
    tk.Label(card3, text="Network Details", fg=FG_WHITE, bg=BG_CARD, font=FONT_CARD_TITLE).place(x=15, y=15)
    
    net_labels = [("Local IP:", get_local_ip()), ("Public IP:", "Fetching..."), ("MAC:", ASSET_TAG)] 
    y_offset = 50
    net_val_labels = []
    for title, val in net_labels:
        tk.Label(card3, text=title, fg=FG_MUTED, bg=BG_CARD, font=("Helvetica Neue", 10)).place(x=15, y=y_offset)
        v_lbl = tk.Label(card3, text=val, fg=FG_WHITE, bg=BG_CARD, font=("Helvetica Neue", 10))
        v_lbl.place(x=80, y=y_offset)
        net_val_labels.append(v_lbl)
        y_offset += 35
    tk.Label(card3, text="● 1 Gbps | Stable", fg=FG_GREEN, bg=BG_CARD, font=("Helvetica Neue", 11, "bold")).place(x=40, y=200)

    card4 = tk.Frame(content, bg=BG_CARD, highlightbackground="#334155", highlightthickness=1)
    card4.place(x=0, y=255, width=810, height=230)
    tk.Label(card4, text="Drive Summary", fg=FG_WHITE, bg=BG_CARD, font=FONT_CARD_TITLE).place(x=15, y=15)
    drive_canvas = tk.Canvas(card4, width=780, height=180, bg=BG_CARD, highlightthickness=0)
    drive_canvas.place(x=15, y=45)

    y_pos = 10
    try:
        for i, p in enumerate(psutil.disk_partitions()):
            if i > 4: break 
            if 'cdrom' in p.opts or p.fstype == '': continue
            try:
                usage = psutil.disk_usage(p.mountpoint)
                pct = usage.percent
                drive_canvas.create_text(0, y_pos, anchor="w", text=f"{p.device}", fill=FG_WHITE, font=FONT_SUB)
                drive_canvas.create_rectangle(0, y_pos+15, 780, y_pos+23, fill="#334155", outline="")
                drive_canvas.create_rectangle(0, y_pos+15, int(max(1, 780*(pct/100))), y_pos+23, fill=FG_DANGER if pct > 90 else FG_CYAN, outline="")
                drive_canvas.create_text(780, y_pos, anchor="e", text=f"{get_size(usage.total)} Total | {get_size(usage.free)} Free ({pct}% used)", fill=FG_MUTED, font=("Helvetica Neue", 10))
                y_pos += 35
            except: continue
    except: pass

    footer = tk.Frame(root, bg=BG_MAIN, pady=10, padx=20)
    footer.pack(side='bottom', fill='x')
    TkButton(footer, text="Report Issue", bg=BG_BTN_DANGER, fg=FG_WHITE, font=("Helvetica Neue", 10, "bold"), relief='flat', command=lambda: [root.destroy(), spawn_ui('--ui-ticket')]).pack(side='right', padx=5, ipadx=10, ipady=4)

    def fetch_async():
        try:
            req = urllib.request.Request(f"{SERVER_URL}/status", headers=STD_HEADERS)
            html = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
            match = re.search(r'alt="([^"]+)"|<h1>([^<]+)</h1>', html)
            if match:
                comp = match.group(1) or match.group(2)
                ui_queue.put(lambda: lbl_comp.config(text=comp))
                ui_queue.put(lambda: lbl_comp_header.config(text=f" | {comp}"))
            ui_queue.put(lambda: lbl_net_status.config(text="ONLINE", fg=FG_GREEN))
        except: ui_queue.put(lambda: lbl_net_status.config(text="OFFLINE", fg=FG_DANGER))
        try:
            req2 = urllib.request.Request('https://api.ipify.org', headers=STD_HEADERS)
            pub_ip = urllib.request.urlopen(req2, timeout=3).read().decode('utf8')
            ui_queue.put(lambda: net_val_labels[1].config(text=pub_ip))
        except: pass

    threading.Thread(target=fetch_async, daemon=True).start()

    def update_metrics():
        try:
            meter_canvas.delete("all")
            draw_arc_meter(meter_canvas, 50, 70, 40, psutil.cpu_percent(), FG_CYAN, "CPU Load", f"{psutil.cpu_percent()}%")
            draw_arc_meter(meter_canvas, 155, 70, 40, psutil.virtual_memory().percent, FG_CYAN, "RAM Usage", f"{get_size(psutil.virtual_memory().used)}")
            draw_arc_meter(meter_canvas, 260, 70, 40, min(100, len(psutil.pids())/3), FG_CYAN, "Processes", f"{len(psutil.pids())}")
        except: pass
        root.after(2000, update_metrics)

    update_metrics()
    if SYS_OS == "Darwin": os.system(f'''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of every process whose unix id is {os.getpid()} to true' ''')
    root.mainloop()

# ==========================================
# SOFTWARE CENTER (APP STORE)
# ==========================================
def run_store_ui():
    root = tk.Tk()
    root.report_callback_exception = global_exception_handler
    show_dock_icon()
    root.title(f"Software Center - {ASSET_TAG}")
    root.geometry("600x500")
    root.configure(bg=BG_MAIN)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw-600)//2}+{(sh-500)//2}")
    
    ui_queue = queue.Queue()
    def process_queue():
        try:
            while True: ui_queue.get_nowait()()
        except queue.Empty: pass
        root.after(100, process_queue)
    process_queue()

    tk.Label(root, text="Software Center", fg=FG_CYAN, bg=BG_MAIN, font=FONT_TITLE).pack(pady=10)
    tk.Label(root, text="Select an application below to securely install it.", fg=FG_MUTED, bg=BG_MAIN, font=FONT_SUB).pack()

    listbox = tk.Listbox(root, bg=BG_SCREEN, fg=FG_WHITE, font=FONT_MONO, height=12)
    listbox.pack(fill='both', expand=True, padx=20, pady=10)

    catalog = []
    
    def _log(msg):
        ui_queue.put(lambda: lbl_status.config(text=msg))

    lbl_status = tk.Label(root, text="Loading Approved Software...", fg=FG_WHITE, bg=BG_MAIN, font=FONT_MONO)
    lbl_status.pack(pady=5)

    def load_software():
        try:
            nonlocal catalog
            headers = STD_HEADERS.copy()
            headers['Authorization'] = f'Bearer {AGENT_API_KEY}'
            req = urllib.request.Request(f"{SERVER_URL}/api/software", headers=headers)
            raw_catalog = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))
            my_os = "macOS" if SYS_OS == "Darwin" else "Windows"
            catalog = [p for p in raw_catalog if p.get('os', 'Both') in [my_os, 'Both']]
            ui_queue.put(lambda: [listbox.insert(tk.END, p['name']) for p in catalog])
            _log(f"Found {len(catalog)} available applications.")
        except Exception as e: _log(f"Error fetching catalog: {e}")

    threading.Thread(target=load_software, daemon=True).start()

    def start_install():
        sel = listbox.curselection()
        if not sel: return
        pkg = catalog[sel[0]]
        
        def _deploy():
            _log(f"Downloading {pkg['name']}...")
            url_lower = pkg['url'].lower()
            ext = ".msi" if url_lower.endswith(".msi") else ".exe" if SYS_OS == "Windows" else ".dmg" if ".dmg" in url_lower else ".zip" if ".zip" in url_lower else ".pkg"
            dp = os.path.join(os.environ.get('TEMP', '/tmp'), f"agent_temp_install{ext}")
            try:
                req = urllib.request.Request(pkg['url'], headers=STD_HEADERS)
                with urllib.request.urlopen(req) as response, open(dp, 'wb') as out_file: out_file.write(response.read())
            except Exception as e:
                _log(f"Download failed: {e}")
                return
                
            _log(f"Installing {pkg['name']} silently in background...")
            try:
                if SYS_OS == "Windows":
                    cmd = f'msiexec.exe /i "{dp}" {pkg["args"]}' if ext == ".msi" else f'"{dp}" {pkg["args"]}'
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.run(cmd, shell=True, check=True, startupinfo=si)
                elif SYS_OS == "Darwin":
                    if ext == ".pkg": subprocess.run(f'sudo installer -pkg "{dp}" -target /', shell=True, check=True) 
                    elif ext == ".zip": subprocess.run(f'unzip -q -o "{dp}" -d /Applications/', shell=True, check=True)
                    elif ext == ".dmg":
                        mnt = "/Volumes/OmniDeployTemp"
                        subprocess.run(f'hdiutil attach "{dp}" -mountpoint "{mnt}" -nobrowse -quiet', shell=True, check=True)
                        subprocess.run(f'cp -R "{mnt}"/*.app /Applications/ 2>/dev/null || true', shell=True, check=True)
                        subprocess.run(f'hdiutil detach "{mnt}" -quiet', shell=True, check=True)
                _log(f"{pkg['name']} successfully installed!")
                ui_queue.put(lambda: messagebox.showinfo("Success", f"{pkg['name']} has been installed.", parent=root))
            except Exception as e: _log(f"Install Failed: {e}")
            finally:
                if os.path.exists(dp):
                    try: os.remove(dp)
                    except: pass

        threading.Thread(target=_deploy, daemon=True).start()

    btn_frame = tk.Frame(root, bg=BG_MAIN)
    btn_frame.pack(pady=10)
    TkButton(btn_frame, text="INSTALL", bg=BG_GREEN, fg="#000000", font=FONT_MONO_BOLD, command=start_install).pack(side='left', padx=10)
    TkButton(btn_frame, text="CANCEL", bg=BG_BTN_DARK, fg=FG_WHITE, font=FONT_MONO_BOLD, command=root.destroy).pack(side='left', padx=10)

    if SYS_OS == "Darwin": os.system(f'''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of every process whose unix id is {os.getpid()} to true' ''')
    root.mainloop()

# ==========================================
# TICKET UI (WITH AUTO-SCREENSHOT)
# ==========================================
def run_ticket_ui():
    logging.info("Building Ticket UI...")
    root = tk.Tk()
    root.report_callback_exception = global_exception_handler
    
    show_dock_icon()
    root.title("Submit IT Ticket")
    root.geometry("450x420")
    root.configure(bg=BG_MAIN)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw-450)//2}+{(sh-420)//2}")
    root.attributes('-topmost', True)
    
    tk.Label(root, text="REQUEST IT SUPPORT", fg=FG_CYAN, bg=BG_MAIN, font=FONT_TITLE).pack(pady=10)
    tk.Label(root, text="Subject:", fg=FG_WHITE, bg=BG_MAIN, font=FONT_MONO).pack(anchor='w', padx=20)
    subj = tk.Entry(root, bg="#1e293b", fg=FG_WHITE, font=FONT_MONO, insertbackground=FG_WHITE)
    subj.pack(fill='x', padx=20, pady=5, ipady=4)
    
    tk.Label(root, text="Describe the issue:", fg=FG_WHITE, bg=BG_MAIN, font=FONT_MONO).pack(anchor='w', padx=20, pady=(10,0))
    desc = tk.Text(root, bg="#1e293b", fg=FG_WHITE, font=FONT_MONO, height=8, insertbackground=FG_WHITE)
    desc.pack(fill='x', padx=20, pady=5)
    
    tk.Label(root, text="* A screenshot of your current screen will be attached automatically.", fg=FG_MUTED, bg=BG_MAIN, font=("Helvetica Neue", 8, "italic")).pack(anchor='w', padx=20)

    def send_ticket():
        logging.info("Capturing screenshot and submitting ticket...")
        if not SERVER_URL: return messagebox.showerror("Error", "No Server URL configured.", parent=root)
        
        subject_text, desc_text = subj.get().strip(), desc.get("1.0", tk.END).strip()
        if not subject_text or not desc_text: return messagebox.showwarning("Error", "Subject and Description are required.", parent=root)

        # Feature 1: Auto-Screenshot Capture
        try:
            ss = ImageGrab.grab()
            ss_path = os.path.join(os.environ.get('TEMP', '/tmp'), "ticket_ss.png")
            ss.save(ss_path, format="PNG")
            with open(ss_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode('utf-8')
            
            ss_payload = {
                "api_key": AGENT_API_KEY, "asset_tag": ASSET_TAG,
                "file_name": f"SCREENSHOT_{datetime.now().strftime('%H%M%S')}.png",
                "file_data": b64_img
            }
            sheaders = STD_HEADERS.copy()
            sheaders['Content-Type'] = 'application/json'
            urllib.request.urlopen(urllib.request.Request(f"{SERVER_URL}/api/upload", data=json.dumps(ss_payload).encode('utf-8'), headers=sheaders), timeout=5)
        except Exception as e: logging.error(f"Auto-Screenshot failed: {e}")

        try: req_name = psutil.users()[0].name if psutil.users() else "User"
        except: req_name = "User"
            
        payload = {
            "api_key": AGENT_API_KEY, "requester_name": req_name, "asset_tag": ASSET_TAG, 
            "category": "Self-Service", "priority": "Normal", "subject": subject_text, "description": desc_text
        }
        
        try:
            headers = STD_HEADERS.copy()
            headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(f"{SERVER_URL}/api/tickets", data=json.dumps(payload).encode('utf-8'), headers=headers)
            urllib.request.urlopen(req, timeout=5)
            messagebox.showinfo("Success", "Ticket submitted to IT.", parent=root)
            root.destroy()
        except Exception as e: messagebox.showerror("Error", f"Failed: {e}", parent=root)
            
    TkButton(root, text="SUBMIT TICKET", bg=BG_BTN, fg=FG_WHITE, font=FONT_MONO_BOLD, command=send_ticket, relief='flat').pack(pady=15)
    if SYS_OS == "Darwin": os.system(f'''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of every process whose unix id is {os.getpid()} to true' ''')
    root.mainloop()

def run_admin_auth_ui():
    root = tk.Tk()
    root.report_callback_exception = global_exception_handler
    show_dock_icon()
    root.title("Admin Auth")
    root.geometry("250x120")
    root.configure(bg=BG_MAIN)
    root.attributes('-topmost', True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"250x120+{(sw-250)//2}+{(sh-120)//2}")
    
    tk.Label(root, text="Enter Admin Password:", bg=BG_MAIN, fg=FG_CYAN, font=FONT_MONO).pack(pady=10)
    ent = tk.Entry(root, show='*', bg="#1e293b", fg=FG_WHITE, font=FONT_MONO, justify='center', insertbackground=FG_WHITE)
    ent.pack(pady=5, padx=20, fill='x')
    ent.focus_set()
    
    def on_submit(event=None):
        if ent.get() == ADMIN_PASSWORD:
            root.destroy()
            run_admin_dashboard()
        else: messagebox.showerror("Error", "Access Denied.")
            
    ent.bind('<Return>', on_submit)
    TkButton(root, text="LOGIN", bg=BG_BTN, fg=FG_WHITE, font=FONT_MONO_BOLD, command=on_submit, relief='flat').pack(pady=5)
    if SYS_OS == "Darwin": os.system(f'''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of every process whose unix id is {os.getpid()} to true' ''')
    root.mainloop()

def run_admin_dashboard():
    root = tk.Tk()
    root.report_callback_exception = global_exception_handler
    show_dock_icon()
    root.title(f"OMNIDEPLOY IT AGENT v{AGENT_VERSION}")
    root.geometry("700x700")
    root.configure(bg=BG_MAIN)

    ui_queue = queue.Queue()
    def process_queue():
        try:
            while True: ui_queue.get_nowait()()
        except queue.Empty: pass
        root.after(100, process_queue)
    process_queue()
    
    catalog = []
    top_frame = tk.Frame(root, bg=BG_MAIN, pady=10)
    top_frame.pack(fill='x', padx=20)
    tk.Label(top_frame, text=f"OMNIDEPLOY IT AGENT", fg=FG_CYAN, bg=BG_MAIN, font=FONT_TITLE).pack(side='left')

    def _log(msg): ui_queue.put(lambda: console.insert(tk.END, msg + "\n") or console.see(tk.END))

    def sync_hw():
        _log("\n[*] Updating Master IT Suite...")
        try:
            headers = STD_HEADERS.copy()
            headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(f"{SERVER_URL}/api/checkin", data=json.dumps(gather_telemetry()).encode('utf-8'), headers=headers)
            urllib.request.urlopen(req, timeout=10)
            _log("[+] SUCCESS.")
        except Exception as e: _log(f"[-] ERROR: {e}")

    def load_software():
        _log("\n[*] Requesting catalog...")
        try:
            nonlocal catalog
            headers = STD_HEADERS.copy()
            headers['Authorization'] = f'Bearer {AGENT_API_KEY}'
            req = urllib.request.Request(f"{SERVER_URL}/api/software", headers=headers)
            raw_catalog = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))
            my_os = "macOS" if SYS_OS == "Darwin" else "Windows"
            catalog = [p for p in raw_catalog if p.get('os', 'Both') in [my_os, 'Both']]
            _log(f"[+] Found {len(catalog)} packages built for {my_os}.")
            ui_queue.put(render_list)
        except Exception as e: _log(f"[-] ERROR fetching catalog: {e}")

    ctrl_frame = tk.Frame(root, bg=BG_MAIN, pady=10)
    ctrl_frame.pack(fill='x', padx=20)
    TkButton(ctrl_frame, text="1. SYNC HW", bg=BG_BTN, fg=FG_WHITE, font=FONT_MONO, command=lambda: threading.Thread(target=sync_hw, daemon=True).start()).pack(side='left', padx=5)
    TkButton(ctrl_frame, text="2. LOAD SOFTWARE", bg=BG_BTN, fg=FG_WHITE, font=FONT_MONO, command=lambda: threading.Thread(target=load_software, daemon=True).start()).pack(side='left', padx=5)

    deploy_frame = tk.Frame(root, bg="#1e293b", pady=10, padx=10)
    deploy_frame.pack(fill='x', padx=20, pady=10)
    deploy_mode = tk.StringVar(value="INDIVIDUAL")
    tk.Radiobutton(deploy_frame, text="Individual Packages", variable=deploy_mode, value="INDIVIDUAL", bg="#1e293b", fg=FG_CYAN, selectcolor=BG_MAIN, command=lambda: render_list()).pack(side='top', anchor='w')
    tk.Radiobutton(deploy_frame, text="Bulk Group Deployment", variable=deploy_mode, value="GROUP", bg="#1e293b", fg=FG_CYAN, selectcolor=BG_MAIN, command=lambda: render_list()).pack(side='top', anchor='w')
    
    listbox = tk.Listbox(deploy_frame, bg=BG_SCREEN, fg=FG_WHITE, font=FONT_MONO, height=8)
    listbox.pack(fill='x', pady=10)
    
    def render_list():
        listbox.delete(0, tk.END)
        if deploy_mode.get() == "INDIVIDUAL":
            for pkg in catalog: listbox.insert(tk.END, pkg['name'])
        else:
            groups = set()
            for pkg in catalog:
                raw = pkg.get('groups', '')
                for g in str(raw if raw else "UNGROUPED").split(','):
                    if g.strip(): groups.add(g.strip())
            for g in sorted(list(groups)): listbox.insert(tk.END, f"GROUP: {g}")

    def start_deploy():
        sel = listbox.curselection()
        if not sel: return
        item = listbox.get(sel[0])
        pkgs = [p for p in catalog if p['name'] == item] if deploy_mode.get() == "INDIVIDUAL" else [p for p in catalog if item.replace("GROUP: ", "").strip() in [g.strip() for g in str(p.get('groups', 'UNGROUPED')).split(',')]]
        
        def _deploy():
            for pkg in pkgs:
                _log(f"--- {pkg['name']} ---")
                url_lower = pkg['url'].lower()
                ext = ".msi" if url_lower.endswith(".msi") else ".exe" if SYS_OS == "Windows" else ".dmg" if ".dmg" in url_lower else ".zip" if ".zip" in url_lower else ".pkg"
                dp = os.path.join(os.environ.get('TEMP', '/tmp'), f"agent_temp_install{ext}")
                try: 
                    req = urllib.request.Request(pkg['url'], headers=STD_HEADERS)
                    with urllib.request.urlopen(req) as response, open(dp, 'wb') as out_file: out_file.write(response.read())
                except Exception as e: 
                    _log(f"[-] Download failed: {e}"); continue
                    
                try:
                    if SYS_OS == "Windows":
                        cmd = f'msiexec.exe /i "{dp}" {pkg["args"]}' if ext == ".msi" else f'"{dp}" {pkg["args"]}'
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        subprocess.run(cmd, shell=True, check=True, startupinfo=si)
                    elif SYS_OS == "Darwin":
                        if ext == ".pkg": subprocess.run(f'sudo installer -pkg "{dp}" -target /', shell=True, check=True) 
                        elif ext == ".zip": subprocess.run(f'unzip -q -o "{dp}" -d /Applications/', shell=True, check=True)
                        elif ext == ".dmg":
                            mnt = "/Volumes/OmniDeployTemp"
                            subprocess.run(f'hdiutil attach "{dp}" -mountpoint "{mnt}" -nobrowse -quiet', shell=True, check=True)
                            subprocess.run(f'cp -R "{mnt}"/*.app /Applications/ 2>/dev/null || true', shell=True, check=True)
                            subprocess.run(f'hdiutil detach "{mnt}" -quiet', shell=True, check=True)
                    _log("[+] Installed.")
                except Exception as e: _log(f"[-] Failed: {e}")
                finally:
                    if os.path.exists(dp): 
                        try: os.remove(dp)
                        except: pass
            sync_hw()
            
        if pkgs: threading.Thread(target=_deploy, daemon=True).start()

    TkButton(deploy_frame, text="DEPLOY SELECTED", bg="#008800", fg=FG_WHITE, font=FONT_MONO, command=start_deploy).pack(anchor='e')
    tk.Label(root, text="AGENT TERMINAL:", fg=FG_CYAN, bg=BG_MAIN, font=FONT_MONO).pack(anchor='w', padx=20)
    console = tk.Text(root, bg=BG_SCREEN, fg=FG_GREEN, font=FONT_MONO, height=12)
    console.pack(fill='both', expand=True, padx=20, pady=(0,20))
    root.mainloop()

# ==========================================
# BACKGROUND DAEMON & WATCHDOGS
# ==========================================
def idle_tracker():
    """Feature 4: Tracks actual active keyboard/mouse minutes"""
    global ACTIVE_MINUTES_TODAY
    while True:
        time.sleep(60)
        idle_sec = 0
        try:
            if SYS_OS == "Windows":
                import ctypes
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]
                lii = LASTINPUTINFO()
                lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
                ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
                idle_sec = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0
            elif SYS_OS == "Darwin":
                out = subprocess.check_output("ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print $NF/1000000000; exit}'", shell=True)
                idle_sec = float(out.strip())
        except: pass
        if idle_sec < 300: ACTIVE_MINUTES_TODAY += 1 # Under 5 mins idle = Active Minute

def agent_daemon():
    logging.info("Starting Background Daemon loop...")
    def create_image():
        image = Image.new('RGB', (64, 64), color=(0, 68, 204))
        ImageDraw.Draw(image).ellipse((16, 16, 48, 48), fill=(0, 213, 255))
        return image
        
    def ensure_startup():
        if getattr(sys, 'frozen', False):
            exe_path = os.path.realpath(sys.executable)
            if SYS_OS == "Windows":
                try:
                    key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, reg.KEY_SET_VALUE)
                    reg.SetValueEx(key, "OmniDeployAgent", 0, reg.REG_SZ, f'"{exe_path}"')
                    reg.CloseKey(key)
                except: pass
            elif SYS_OS == "Darwin":
                try:
                    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
                    os.makedirs(plist_dir, exist_ok=True)
                    plist_path = os.path.join(plist_dir, "com.omnideploy.agent.plist")
                    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.omnideploy.agent</string><key>ProgramArguments</key><array><string>{exe_path}</string></array><key>RunAtLoad</key><true/></dict></plist>"""
                    with open(plist_path, 'w') as f: f.write(plist_content)
                except: pass
                
    def trigger_self_update(url):
        if not getattr(sys, 'frozen', False): return
        logging.info("Initiating Self Update...")
        try:
            temp_exe = os.path.join(os.environ.get('TEMP', '/tmp'), "OmniDeployAgent_Update_Temp")
            req = urllib.request.Request(url, headers=STD_HEADERS)
            with urllib.request.urlopen(req) as response, open(temp_exe, 'wb') as out_file: out_file.write(response.read())
            current_exe = os.path.realpath(sys.executable)
            exe_name = os.path.basename(current_exe)
            if SYS_OS == "Windows":
                bat_path = os.path.join(os.environ['TEMP'], "update_agent.bat")
                bat_content = f"""@echo off\nset _MEIPASS2=\nset _MEIPASS=\ntimeout /t 3 /nobreak\ntaskkill /f /im "{exe_name}"\nmove /y "{temp_exe}" "{current_exe}"\nstart "" "{current_exe}"\ndel "%~f0"\n"""
                with open(bat_path, "w") as f: f.write(bat_content)
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                clean_env = os.environ.copy()
                clean_env.pop('_MEIPASS2', None)
                clean_env.pop('_MEIPASS', None)
                subprocess.Popen(["cmd.exe", "/c", bat_path], startupinfo=si, env=clean_env, creationflags=0x08000000)
            elif SYS_OS == "Darwin":
                sh_path = os.path.join('/tmp', "update_agent.sh")
                sh_content = f"""#!/bin/bash\nsleep 3\nkillall "{exe_name}"\nmv -f "{temp_exe}" "{current_exe}"\nchmod +x "{current_exe}"\nopen "{current_exe}"\nrm "$0"\n"""
                with open(sh_path, "w") as f: f.write(sh_content)
                os.chmod(sh_path, 0o755)
                subprocess.Popen(["/bin/bash", sh_path], start_new_session=True)
            os._exit(0)
        except Exception as e: logging.error(f"Self-Update failed: {e}")

    def show_notification(message, priority, comp_name):
        script = f"""
import tkinter as tk
import platform, os, subprocess
SYS_OS = platform.system()
if SYS_OS == "Darwin":
    try: from tkmacosx import Button as TkButton
    except: TkButton = tk.Button
else: TkButton = tk.Button
root = tk.Tk()
root.withdraw()
root.overrideredirect(True)
root.attributes('-topmost', True)
bg_color = '{BG_BTN_EDIT}' if '{priority}' == 'MEDIUM' else '{BG_BTN_DANGER}' if '{priority}' in ['HIGH', 'RESTART'] else '{BG_BTN}'
root.configure(bg=bg_color)
def force_front():
    root.deiconify(); root.lift(); root.attributes('-topmost', True)
    if SYS_OS == "Darwin": os.system('''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of every process whose unix id is ''' + str(os.getpid()) + ''' to true' ''')
if '{priority}' in ['LOW', 'MEDIUM']:
    w, h = 350, 120
    root.geometry(f"{{w}}x{{h}}+{{root.winfo_screenwidth() - w - 20}}+{{root.winfo_screenheight() - h - 60}}")
    tk.Label(root, text="{comp_name} IT ALERT", fg="{FG_WHITE}", bg=bg_color, font={FONT_MONO_BOLD}).pack(pady=(10, 5))
    tk.Label(root, text="{message}", fg="{FG_WHITE}", bg=bg_color, font={FONT_MONO}, wraplength=330).pack()
    root.after(10000, root.destroy)
else:
    w, h = 600, 300
    root.geometry(f"{{w}}x{{h}}+{{(root.winfo_screenwidth() - w) // 2}}+{{(root.winfo_screenheight() - h) // 2}}")
    tk.Label(root, text="{comp_name} IT ALERT", fg="{FG_WARN}", bg=bg_color, font=("Consolas", 20, "bold")).pack(pady=(30, 10))
    tk.Label(root, text="{message}", fg="{FG_WHITE}", bg=bg_color, font=("Consolas", 12), wraplength=560, justify="center").pack(pady=20)
    btn_frame = tk.Frame(root, bg=bg_color)
    btn_frame.pack(side='bottom', pady=30)
    if '{priority}' == 'RESTART':
        cmd = "shutdown /r /t 5" if SYS_OS == "Windows" else "osascript -e 'tell app \\"System Events\\" to restart'"
        TkButton(btn_frame, text="RESTART NOW", bg="#111111", fg="{FG_WHITE}", font={FONT_MONO_BOLD}, command=lambda: [subprocess.run(cmd, shell=True), root.destroy()], relief='flat').pack(side='left', padx=10)
        TkButton(btn_frame, text="SNOOZE", bg="#111111", fg="{FG_WHITE}", font={FONT_MONO_BOLD}, command=root.destroy, relief='flat').pack(side='left', padx=10)
    else: TkButton(btn_frame, text="ACKNOWLEDGE", bg="#111111", fg="{FG_WHITE}", font={FONT_MONO_BOLD}, command=root.destroy, relief='flat').pack()
root.after(100, force_front)
root.mainloop()"""
        subprocess.Popen([sys.executable, "-c", script])

    def poll_loop():
        first_run = True
        last_notif_id = -1
        last_disk_alert = 0
        loop_counter = 0
        
        while True:
            # 1. MAIN TELEMETRY CHECK-IN
            try:
                payload = gather_telemetry()
                headers = STD_HEADERS.copy()
                headers['Content-Type'] = 'application/json'
                req = urllib.request.Request(f"{SERVER_URL}/api/checkin", data=json.dumps(payload).encode('utf-8'), headers=headers)
                resp_data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())

                if payload["disk_warning"] and time.time() - last_disk_alert > 86400:
                    last_disk_alert = time.time()
                    alert = {"api_key": AGENT_API_KEY, "requester_name": "SYSTEM", "asset_tag": ASSET_TAG, "category": "Hardware", "priority": "High", "subject": "AUTO-ALERT: Low Disk Space", "description": f"Main Drive is over 90% full on {ASSET_TAG}."}
                    treq = urllib.request.Request(f"{SERVER_URL}/api/tickets", data=json.dumps(alert).encode('utf-8'), headers=headers)
                    urllib.request.urlopen(treq, timeout=5)

                if resp_data.get("update_url"): trigger_self_update(resp_data["update_url"])
            except Exception as e: logging.warning(f"Poll checkin failed: {e}")

            # 2. FEATURE 5: ROGUE PROCESS WATCHDOG (Runs every 5 loops / 5 minutes)
            if loop_counter % 5 == 0:
                try:
                    critical = ["AnyDesk.exe"] if SYS_OS == "Windows" else ["AnyDesk"]
                    running = [p.info['name'] for p in psutil.process_iter(['name'])]
                    for proc in critical:
                        if proc not in running and AGENT_CACHE.get('anydesk') != "NOT INSTALLED" and not first_run:
                            w_alert = {"api_key": AGENT_API_KEY, "requester_name": "WATCHDOG", "asset_tag": ASSET_TAG, "category": "Security", "priority": "High", "subject": f"WATCHDOG ALERT: {proc} Terminated", "description": f"Critical security process {proc} was terminated on {ASSET_TAG}."}
                            theaders = STD_HEADERS.copy()
                            theaders['Content-Type'] = 'application/json'
                            urllib.request.urlopen(urllib.request.Request(f"{SERVER_URL}/api/tickets", data=json.dumps(w_alert).encode('utf-8'), headers=theaders), timeout=5)
                except Exception as e: logging.warning(f"Watchdog scan failed: {e}")

            # 3. NOTIFICATIONS FETCH
            try:
                headers = STD_HEADERS.copy()
                headers['Authorization'] = f'Bearer {AGENT_API_KEY}'
                req = urllib.request.Request(f"{SERVER_URL}/api/notifications?tag={ASSET_TAG}", headers=headers)
                resp = urllib.request.urlopen(req, timeout=5)
                for n in json.loads(resp.read().decode('utf-8')):
                    if n['id'] > last_notif_id:
                        if first_run: last_notif_id = max(last_notif_id, n['id'])
                        else:
                            last_notif_id = n['id']
                            show_notification(n['message'], n['priority'], n['company_name'])
            except Exception: pass

            # 4. REMOTE ACTIONS EXECUTION
            try:
                headers = STD_HEADERS.copy()
                headers['Authorization'] = f'Bearer {AGENT_API_KEY}'
                req = urllib.request.Request(f"{SERVER_URL}/api/actions?tag={ASSET_TAG}", headers=headers)
                actions_list = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))
                for a in actions_list:
                    action_type = a.get('action_type')
                    cmd = a.get('payload', '') if action_type == 'CUSTOM_SCRIPT' else SAFE_ACTIONS.get(SYS_OS, {}).get(action_type)
                    output = "Command not recognized or OS unsupported."
                    if cmd:
                        try:
                            if SYS_OS == "Windows":
                                si = subprocess.STARTUPINFO()
                                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                process = subprocess.run(f'powershell.exe -Command "{cmd}"', shell=True, capture_output=True, text=True, startupinfo=si, timeout=300)
                            else: process = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                            output = (process.stdout + "\n" + process.stderr).strip() or "Command completed successfully."
                        except subprocess.TimeoutExpired: output = "Error: Command timed out after 5 minutes."
                        except Exception as e: output = f"Execution Error: {str(e)}"
                            
                    cheaders = STD_HEADERS.copy()
                    cheaders['Content-Type'] = 'application/json'
                    creq = urllib.request.Request(f"{SERVER_URL}/api/actions/complete", data=json.dumps({"api_key": AGENT_API_KEY, "id": a.get('id'), "result": output}).encode('utf-8'), headers=cheaders)
                    urllib.request.urlopen(creq, timeout=5)
            except Exception: pass
            
            first_run = False
            loop_counter += 1
            time.sleep(60)

    threading.Thread(target=initialize_cache, daemon=True).start()
    threading.Thread(target=idle_tracker, daemon=True).start()
    threading.Thread(target=poll_loop, daemon=True).start()
    ensure_startup()
    
    if SYS_OS == "Windows":
        menu = pystray.Menu(
            item('System Monitor', lambda: spawn_ui('--ui-info')),
            item('Software Center', lambda: spawn_ui('--ui-store')),
            item('Submit IT Ticket', lambda: spawn_ui('--ui-ticket')),
            pystray.Menu.SEPARATOR,
            item('Admin Dashboard', lambda: spawn_ui('--ui-admin')),
            item('Exit Agent', lambda icon, item: icon.stop() or os._exit(0))
        )
        icon = pystray.Icon("OmniDeploy", create_image(), "OmniDeploy IT Agent", menu)
        icon.run()
    else:
        import rumps
        app = rumps.App("OmniDeploy", title="🚀")
        app.menu = [
            rumps.MenuItem("System Monitor", callback=lambda _: spawn_ui('--ui-info')),
            rumps.MenuItem("Software Center", callback=lambda _: spawn_ui('--ui-store')),
            rumps.MenuItem("Submit IT Ticket", callback=lambda _: spawn_ui('--ui-ticket')),
            None,
            rumps.MenuItem("Admin Dashboard", callback=lambda _: spawn_ui('--ui-admin'))
        ]
        app.run()

if __name__ == "__main__":
    if "--ui-info" in sys.argv: run_info_ui()
    elif "--ui-ticket" in sys.argv: run_ticket_ui()
    elif "--ui-admin" in sys.argv: run_admin_auth_ui()
    elif "--ui-store" in sys.argv: run_store_ui()
    else: agent_daemon()