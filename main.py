"""
Qoder Automation - FULL AUTOMATION WITH UI INTERACTION
Auto-claim Pro Trial + 300 Credits
Version: 5.0.0
Mendukung: macOS, Windows, Linux
Dengan otomatisasi klik tombol Sign In
Menggunakan Playwright dengan stealth
"""

import asyncio
import json
import re
import time
import random
import os
import subprocess
import sys
import shutil
import platform
import errno
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from pathlib import Path

# Auto-register via invite path (qoder_register.py)
try:
    from qoder_register import (auto_register, register_menu, DEFAULT_REFERRAL_CODE,
                                REGISTERED_FILE, REGISTER_FAILED_FILE)
    REGISTER_OK = True
except ImportError as _reg_err:      # numpy / pillow / requests missing
    REGISTER_OK = False
    REGISTER_ERR = str(_reg_err)

# Pro Trial claim via the account path (qoder_claim.py)
try:
    from qoder_claim import claim_pro_trial, claim_menu, CLAIM_RESULT
    CLAIM_OK = True
except ImportError as _claim_err:    # requests / cryptography missing
    CLAIM_OK = False
    CLAIM_ERR = str(_claim_err)

# ================= ANSI COLORS =================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[95m'

def print_color(text, color=Colors.RESET):
    print(f"{color}{text}{Colors.RESET}")

def banner():
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════╗
║     Qoder Automation - FULL AUTOMATION                       ║
║     Auto-claim Pro Trial + 300 Credits                      ║
║     Version: 5.0.0                                           ║
║     Support: macOS | Windows | Linux                        ║
║     With Stealth + Playwright                               ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")

# ================= PLATFORM DETECTION =================
SYSTEM = platform.system()
IS_MAC = SYSTEM == "Darwin"
IS_WINDOWS = SYSTEM == "Windows"
IS_LINUX = SYSTEM == "Linux"

# ================= KONFIGURASI PER PLATFORM =================
def get_platform_config(platform_type: str = None):
    """
    Mendapatkan konfigurasi untuk platform tertentu
    """
    if platform_type is None:
        platform_type = SYSTEM
    
    configs = {
        "Darwin": {
            "name": "macOS",
            "app_path": "/Applications/Qoder.app",
            "binary_name": "Electron",
            "data_dir": Path.home() / "Library" / "Application Support" / "Qoder",
            "user_dir": Path.home() / ".qoder",
            "cache_dir": Path.home() / "Library" / "Caches" / "Qoder",
            "preferences": Path.home() / "Library" / "Preferences" / "com.qoder.Qoder.plist",
            "saved_state": Path.home() / "Library" / "Saved Application State" / "com.qoder.Qoder.savedState",
            "launch_cmd": "open",
            "launch_args": ["-a", "/Applications/Qoder.app"]
        },
        "Windows": {
            "name": "Windows",
            "app_path_system": "C:/Program Files/Qoder/Qoder.exe",
            "app_path_user": os.path.expandvars("%LOCALAPPDATA%/Qoder/Qoder.exe"),
            "binary_name": "Qoder.exe",
            "data_dir": Path(os.path.expandvars("%APPDATA%/Qoder")),
            "user_dir": Path.home() / ".qoder",
            "cache_dir": Path(os.path.expandvars("%LOCALAPPDATA%/Qoder/Cache")),
            "preferences": Path(os.path.expandvars("%APPDATA%/Qoder/Preferences")),
            "saved_state": None,
            "launch_cmd": "start",
            "launch_args": ["", ""]
        },
        "Linux": {
            "name": "Linux",
            "app_path": "/usr/bin/qoder",
            "app_path_local": "/usr/local/bin/qoder",
            "binary_name": "qoder",
            "data_dir": Path.home() / ".config" / "Qoder",
            "user_dir": Path.home() / ".qoder",
            "cache_dir": Path.home() / ".cache" / "Qoder",
            "preferences": Path.home() / ".config" / "Qoder" / "preferences",
            "saved_state": None,
            "launch_cmd": "qoder",
            "launch_args": []
        }
    }
    
    return configs.get(platform_type, configs.get("Darwin"))

# ================= FILE PATHS =================
QODER_APP_PATH = None
QODER_DATA_DIR = None
QODER_USER_DIR = None
QODER_CACHE_DIR = None
QODER_PREFERENCES = None
QODER_SAVED_STATE = None
QODER_BINARY = None
LAUNCH_CMD = None
LAUNCH_ARGS = []
PLATFORM_NAME = ""
SELECTED_PLATFORM = SYSTEM

def init_platform(platform_type: str):
    """Inisialisasi path berdasarkan platform yang dipilih"""
    global QODER_APP_PATH, QODER_DATA_DIR, QODER_USER_DIR, QODER_BINARY
    global LAUNCH_CMD, LAUNCH_ARGS, PLATFORM_NAME, QODER_CACHE_DIR
    global QODER_PREFERENCES, QODER_SAVED_STATE
    
    config = get_platform_config(platform_type)
    PLATFORM_NAME = config.get("name", "Unknown")
    
    if platform_type == "Darwin":
        QODER_APP_PATH = config.get("app_path")
        QODER_BINARY = Path(QODER_APP_PATH) / "Contents" / "MacOS" / config.get("binary_name")
        QODER_DATA_DIR = config.get("data_dir")
        QODER_USER_DIR = config.get("user_dir")
        QODER_CACHE_DIR = config.get("cache_dir")
        QODER_PREFERENCES = config.get("preferences")
        QODER_SAVED_STATE = config.get("saved_state")
        LAUNCH_CMD = config.get("launch_cmd")
        LAUNCH_ARGS = config.get("launch_args", [])
        
    elif platform_type == "Windows":
        system_path = config.get("app_path_system")
        user_path = config.get("app_path_user")
        
        if os.path.exists(system_path):
            QODER_APP_PATH = system_path
        elif os.path.exists(user_path):
            QODER_APP_PATH = user_path
        else:
            QODER_APP_PATH = None
        
        QODER_BINARY = QODER_APP_PATH if QODER_APP_PATH else None
        QODER_DATA_DIR = config.get("data_dir")
        QODER_USER_DIR = config.get("user_dir")
        QODER_CACHE_DIR = config.get("cache_dir")
        QODER_PREFERENCES = config.get("preferences")
        QODER_SAVED_STATE = config.get("saved_state")
        LAUNCH_CMD = config.get("launch_cmd")
        LAUNCH_ARGS = config.get("launch_args", [])
        
    elif platform_type == "Linux":
        if os.path.exists(config.get("app_path")):
            QODER_APP_PATH = config.get("app_path")
        elif os.path.exists(config.get("app_path_local")):
            QODER_APP_PATH = config.get("app_path_local")
        else:
            QODER_APP_PATH = None
        
        QODER_BINARY = QODER_APP_PATH
        QODER_DATA_DIR = config.get("data_dir")
        QODER_USER_DIR = config.get("user_dir")
        QODER_CACHE_DIR = config.get("cache_dir")
        QODER_PREFERENCES = config.get("preferences")
        QODER_SAVED_STATE = config.get("saved_state")
        LAUNCH_CMD = config.get("launch_cmd")
        LAUNCH_ARGS = config.get("launch_args", [])
    
    print_color(f"  [*] Platform: {PLATFORM_NAME}", Colors.CYAN)
    if QODER_BINARY:
        print_color(f"  [*] Binary path: {QODER_BINARY}", Colors.CYAN)
    else:
        print_color(f"  [!] Qoder binary not found!", Colors.RED)

# ================= FILE PATHS =================
SUCCESS_FILE = "qoder_sukses.txt"
AKUN_FILE = "qoder_akun.txt"
API_KEY_FILE = "qoder_api_keys.txt"
FAILED_FILE = "qoder_failed.txt"
LOG_FILE = "qoder_log.txt"

# ================= UTILITY FUNCTIONS =================

def setup_logging():
    """Setup logging configuration"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write(f"# Qoder Automation Log - {datetime.now(timezone.utc).isoformat()}\n")

def write_log(message: str, level: str = "INFO"):
    """Write log message to file"""
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")

def load_accounts():
    """Load accounts from file.

    Format: EMAIL|PASSWORD[|ACCOUNT_PATH]
    ACCOUNT_PATH opsional = path akun Qoder (PAT, `pt-…`) yang dipakai untuk
    claim Pro Trial lewat API; kalau kosong, claim diverifikasi lewat desktop.
    """
    try:
        with open(AKUN_FILE) as f:
            out = []
            for l in f:
                parts = [p.strip() for p in l.split("|")]
                if len(parts) >= 2 and parts[0]:
                    out.append({
                        "email": parts[0],
                        "password": parts[1],
                        "path": parts[2] if len(parts) >= 3 and parts[2] else "",
                    })
            return out
    except FileNotFoundError:
        write_log(f"File {AKUN_FILE} tidak ditemukan", "ERROR")
        return []

def save_success(email, data):
    """Save successful login"""
    with open(SUCCESS_FILE, "a") as f:
        f.write(f"{email}|{json.dumps(data)}|{datetime.now(timezone.utc).isoformat()}\n")
    write_log(f"Success: {email} - Credits: {data.get('credits', 0)}", "SUCCESS")

def save_failed(email, error_msg):
    """Save failed login attempt"""
    with open(FAILED_FILE, "a") as f:
        f.write(f"{email}|{error_msg}|{datetime.now(timezone.utc).isoformat()}\n")
    write_log(f"Failed: {email} - {error_msg}", "ERROR")

def remove_account(email):
    """Remove account from list after successful processing"""
    accs = load_accounts()
    with open(AKUN_FILE, "w") as f:
        for a in accs:
            if a["email"] != email:
                row = f"{a['email']}|{a['password']}"
            if a.get("path"):
                row += f"|{a['path']}"
            f.write(row + "\n")

def load_processed_emails():
    """Load emails that have been processed successfully"""
    try:
        with open(SUCCESS_FILE, 'r') as f:
            return [line.split('|')[0] for line in f if '|' in line]
    except FileNotFoundError:
        return []

# ================= PLAYWRIGHT HELPER =================

def ensure_playwright_browsers():
    """Pastikan browser Playwright dan Google Chrome terinstall"""
    try:
        import playwright
        from playwright._impl._api_structures import BrowserType
        
        # Cek apakah Google Chrome terinstall (PRIORITAS)
        chrome_paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            'C:/Program Files/Google/Chrome/Application/chrome.exe',
            'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
        ]
        
        chrome_installed = False
        for cp in chrome_paths:
            if os.path.exists(cp):
                chrome_installed = True
                print_color(f"  ✅ Google Chrome found at: {cp}", Colors.GREEN)
                break
        
        if not chrome_installed:
            print_color("  ⚠️ Google Chrome TIDAK ditemukan!", Colors.YELLOW)
            print_color("  ℹ️ Google Chrome diperlukan untuk login Google yang aman", Colors.YELLOW)
            print_color("  ℹ️ Download: https://www.google.com/chrome/", Colors.CYAN)
        
        # Cek apakah chromium sudah terinstall (sebagai fallback)
        cache_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
        
        chromium_installed = False
        if cache_dir.exists():
            for item in cache_dir.iterdir():
                if "chromium" in str(item).lower() and item.is_dir():
                    chromium_installed = True
                    break
        
        if not chromium_installed:
            print_color("  [*] Playwright Chromium belum terinstall. Menginstall sebagai fallback...", Colors.YELLOW)
            print_color("  [*] Ini mungkin memakan waktu beberapa menit...", Colors.YELLOW)
            
            # Install chromium dengan output
            process = subprocess.Popen(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Tampilkan progress
            for line in process.stdout:
                print(f"    {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                print_color("  ✅ Playwright Chromium berhasil diinstall!", Colors.GREEN)
                write_log("Playwright Chromium installed", "INFO")
            else:
                print_color(f"  ❌ Gagal install Chromium. Silakan install manual:", Colors.RED)
                print_color(f"  {sys.executable} -m playwright install chromium", Colors.YELLOW)
                write_log(f"Failed to install Chromium", "ERROR")
        else:
            print_color("  ✅ Playwright Chromium sudah terinstall (fallback)", Colors.GREEN)
        
        return chrome_installed or chromium_installed
            
    except ImportError:
        print_color("  [!] Playwright tidak terinstall. Menginstall...", Colors.YELLOW)
        
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "playwright"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in process.stdout:
            print(f"    {line.strip()}")
        
        process.wait()
        
        if process.returncode == 0:
            print_color("  ✅ Playwright berhasil diinstall!", Colors.GREEN)
            # Install browser
            print_color("  [*] Menginstall browser Chromium...", Colors.YELLOW)
            process = subprocess.Popen(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                print(f"    {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                print_color("  ✅ Browser berhasil diinstall!", Colors.GREEN)
                return True
            else:
                print_color(f"  ❌ Gagal install browser.", Colors.RED)
                return False
        else:
            print_color(f"  ❌ Gagal install playwright.", Colors.RED)
            return False

# ================= QODER PATCHER =================

class QoderPatcher:
    """Handle Qoder app patching for multiple platforms"""
    
    def __init__(self, platform_type: str = None):
        if platform_type is None:
            platform_type = SYSTEM
        self.platform = platform_type
        self.config = get_platform_config(platform_type)
        self.mac_address = None
        self.machine_id = None
        self.ms_deviceid = None
        self.umid = None
        self.is_patched = False
        
    def generate_fake_mac(self):
        """Generate fake MAC address (for macOS)"""
        mac = ':'.join(['{:02x}'.format(random.randint(0x00, 0xff)) for _ in range(6)])
        self.mac_address = mac
        write_log(f"Generated fake MAC: {mac}", "INFO")
        return mac
    
    def generate_machine_id(self):
        """Generate fake machine ID"""
        import hashlib
        machine_id = hashlib.md5(str(random.randint(1000000, 9999999)).encode()).hexdigest()[:32]
        self.machine_id = machine_id
        write_log(f"Generated machine ID: {machine_id}", "INFO")
        return machine_id
    
    def generate_ms_deviceid(self):
        """Generate fake Microsoft device ID"""
        import uuid
        device_id = str(uuid.uuid4())
        self.ms_deviceid = device_id
        write_log(f"Generated MS device ID: {device_id}", "INFO")
        return device_id
    
    def generate_umid(self):
        """Generate fake UMID"""
        import uuid
        umid = str(uuid.uuid4())
        self.umid = umid
        write_log(f"Generated UMID: {umid}", "INFO")
        return umid
    
    def generate_pkce(self):
        """Generate PKCE code_verifier and code_challenge (S256) for device auth"""
        import hashlib
        import base64
        
        # Generate code_verifier: 32 random bytes, base64url encoded
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('ascii')
        
        # Generate code_challenge: SHA256 of code_verifier, base64url encoded
        digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
        
        self.code_verifier = code_verifier
        self.code_challenge = code_challenge
        
        write_log(f"Generated PKCE challenge (S256)", "INFO")
        return code_verifier, code_challenge
    
    def generate_nonce(self):
        """Generate random nonce for OAuth device auth"""
        import uuid
        nonce = uuid.uuid4().hex
        self.nonce = nonce
        write_log(f"Generated nonce: {nonce[:8]}...", "INFO")
        return nonce
    
    def patch_qoder_data(self):
        """Patch Qoder data directory with fake identifiers"""
        global QODER_DATA_DIR, QODER_USER_DIR
        
        print_color("  [*] Patching Qoder data...", Colors.YELLOW)
        write_log("Starting Qoder data patch", "INFO")
        
        try:
            # Generate fake identifiers
            if self.platform == "Darwin":
                self.generate_fake_mac()
                self.generate_machine_id()
                self.generate_ms_deviceid()
                self.generate_umid()
            else:
                self.generate_machine_id()
                self.generate_ms_deviceid()
            
            # Clear and recreate state files
            if QODER_DATA_DIR and QODER_DATA_DIR.exists():
                # Backup existing data (skip socket files)
                backup_dir = QODER_DATA_DIR.parent / "Qoder_backup"
                if not backup_dir.exists():
                    # Copy only regular files, skip sockets
                    for item in QODER_DATA_DIR.rglob('*'):
                        if item.is_file() and not item.is_socket():
                            try:
                                relative_path = item.relative_to(QODER_DATA_DIR)
                                backup_path = backup_dir / relative_path
                                backup_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(item, backup_path)
                            except Exception as e:
                                write_log(f"Skip backup for {item}: {e}", "WARNING")
                    write_log(f"Backup created at {backup_dir}", "INFO")
                    print(f"  [*] Backup created (skipped socket files)")
                
                # Clear state files
                state_files = [
                    QODER_DATA_DIR / "state.vscdb",
                    QODER_DATA_DIR / "machineid",
                    QODER_DATA_DIR / "ms_deviceid",
                    QODER_DATA_DIR / "serviceMachineId"
                ]
                
                for state_file in state_files:
                    if state_file.exists() and state_file.is_file():
                        state_file.unlink()
                        print(f"  [*] Cleared {state_file.name}")
            
            # Create Qoder data directory if it doesn't exist
            if QODER_DATA_DIR:
                QODER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            
            # Create new state files with fake data
            if QODER_DATA_DIR:
                with open(QODER_DATA_DIR / "machineid", 'w') as f:
                    f.write(self.machine_id)
                
                with open(QODER_DATA_DIR / "ms_deviceid", 'w') as f:
                    f.write(self.ms_deviceid)
                
                with open(QODER_DATA_DIR / "serviceMachineId", 'w') as f:
                    f.write(self.machine_id)
            
            # Create/update user data
            if QODER_USER_DIR:
                QODER_USER_DIR.mkdir(parents=True, exist_ok=True)
            
            # Save patch info
            patch_info = {
                "platform": self.platform,
                "machine_id": self.machine_id,
                "ms_deviceid": self.ms_deviceid,
                "patched_at": datetime.now(timezone.utc).isoformat()
            }
            
            if self.platform == "Darwin":
                patch_info["mac_address"] = self.mac_address
                patch_info["umid"] = self.umid
            
            if QODER_DATA_DIR:
                with open(QODER_DATA_DIR / "patch_info.json", 'w') as f:
                    json.dump(patch_info, f, indent=2)
            
            self.is_patched = True
            write_log("Patch completed successfully", "SUCCESS")
            
            print_color("  ✅ Patch + Reset Complete!", Colors.GREEN)
            print_color(f"  Platform: {self.platform}", Colors.CYAN)
            print_color(f"  machineId: {self.machine_id}", Colors.CYAN)
            print_color(f"  ms_deviceid: {self.ms_deviceid}", Colors.CYAN)
            if self.platform == "Darwin":
                print_color(f"  Fake MAC: {self.mac_address}", Colors.CYAN)
                print_color(f"  UMID: {self.umid}", Colors.CYAN)
            
            return True
            
        except Exception as e:
            write_log(f"Patch failed: {e}", "ERROR")
            print_color(f"  [!] Patch failed: {e}", Colors.RED)
            import traceback
            traceback.print_exc()
            return False

# ================= QODER CLIENT AUTOMATION =================

class QoderClientAutomation:
    """Automate Qoder Client for multiple platforms with UI interaction"""
    
    def __init__(self, headless: bool = False, platform_type: str = None, timeout: int = 120000):
        self.headless = headless
        self.timeout = timeout
        self.process = None
        self.email = None
        self.password = None
        self.credits = 0
        self.platform = platform_type or SYSTEM
        self.patcher = QoderPatcher(self.platform)
        self.binary_path = self.get_qoder_binary_path()
        write_log(f"Initialized QoderClientAutomation (platform={self.platform}, headless={headless})", "INFO")
    
    def check_qoder_installed(self) -> bool:
        """Check if Qoder Client is installed"""
        global QODER_BINARY, QODER_APP_PATH
        
        if self.platform == "Darwin":
            if os.path.exists(QODER_APP_PATH):
                print_color(f"  ✅ Qoder Client found at {QODER_APP_PATH}", Colors.GREEN)
                write_log(f"Qoder Client found at {QODER_APP_PATH}", "INFO")
                return True
            else:
                print_color(f"  ❌ Qoder Client not found at {QODER_APP_PATH}", Colors.RED)
                print_color("  Please download from https://qoder.com/download", Colors.YELLOW)
                return False
                
        elif self.platform == "Windows":
            if QODER_BINARY and os.path.exists(QODER_BINARY):
                print_color(f"  ✅ Qoder Client found at {QODER_BINARY}", Colors.GREEN)
                write_log(f"Qoder Client found at {QODER_BINARY}", "INFO")
                return True
            else:
                print_color("  ❌ Qoder Client not found", Colors.RED)
                print_color("  Please download from https://qoder.com/download", Colors.YELLOW)
                return False
                
        elif self.platform == "Linux":
            if QODER_BINARY and os.path.exists(QODER_BINARY):
                print_color(f"  ✅ Qoder Client found at {QODER_BINARY}", Colors.GREEN)
                write_log(f"Qoder Client found at {QODER_BINARY}", "INFO")
                return True
            else:
                print_color("  ❌ Qoder Client not found", Colors.RED)
                print_color("  Please download from https://qoder.com/download", Colors.YELLOW)
                return False
        
        return False
    
    def get_qoder_version(self) -> Optional[str]:
        """Get Qoder Client version"""
        if self.platform == "Darwin":
            try:
                cmd = ["defaults", "read", f"{QODER_APP_PATH}/Contents/Info.plist", "CFBundleShortVersionString"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print_color(f"  [*] Qoder Version: {version}", Colors.CYAN)
                    write_log(f"Qoder version: {version}", "INFO")
                    return version
            except Exception as e:
                write_log(f"Error checking version: {e}", "WARNING")
        elif self.platform == "Windows" or self.platform == "Linux":
            if QODER_BINARY and os.path.exists(QODER_BINARY):
                try:
                    result = subprocess.run([QODER_BINARY, "--version"], capture_output=True, text=True)
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        print_color(f"  [*] Qoder Version: {version}", Colors.CYAN)
                        write_log(f"Qoder version: {version}", "INFO")
                        return version
                except:
                    pass
        return None
    
    def get_qoder_binary_path(self) -> Optional[str]:
        """Get Qoder binary path"""
        global QODER_BINARY
        return QODER_BINARY
    
    def get_qoder_pid(self) -> Optional[int]:
        """Get Qoder process ID"""
        try:
            if self.platform == "Darwin":
                result = subprocess.run(["pgrep", "-f", "Qoder"], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout:
                    return int(result.stdout.strip().split('\n')[0])
            elif self.platform == "Windows":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Qoder.exe"], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if "Qoder.exe" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                return int(parts[1])
            elif self.platform == "Linux":
                result = subprocess.run(["pgrep", "-f", "qoder"], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout:
                    return int(result.stdout.strip().split('\n')[0])
        except Exception:
            pass
        return None
    
    def kill_qoder_process(self):
        """Kill Qoder process"""
        try:
            if self.platform == "Darwin":
                subprocess.run(["pkill", "-f", "Qoder"], capture_output=True)
            elif self.platform == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", "Qoder.exe"], capture_output=True)
            elif self.platform == "Linux":
                subprocess.run(["pkill", "-f", "qoder"], capture_output=True)
            
            write_log("Killed Qoder process", "INFO")
            print("  [*] Killed existing Qoder process")
            time.sleep(2)
        except Exception as e:
            write_log(f"Error killing Qoder: {e}", "WARNING")
    
    def launch_qoder(self) -> bool:
        """Launch Qoder Client"""
        if not self.check_qoder_installed():
            return False
        
        # Kill existing process
        self.kill_qoder_process()
        
        # Apply patch before launch
        self.patcher.patch_qoder_data()
        
        # Detect actual binary
        binary_path = self.binary_path
        if not binary_path:
            print_color("  ❌ Could not find Qoder binary", Colors.RED)
            write_log("Qoder binary not found", "ERROR")
            return False
        
        if not os.path.exists(binary_path):
            print_color(f"  ❌ Binary not found at: {binary_path}", Colors.RED)
            write_log(f"Binary not found: {binary_path}", "ERROR")
            return False
        
        try:
            print_color(f"  [*] Launching Qoder Client from: {binary_path}", Colors.YELLOW)
            write_log(f"Launching Qoder Client: {binary_path}", "INFO")
            
            # Launch Qoder with appropriate command
            if self.platform == "Darwin":
                cmd = [
                    binary_path,
                    "--disable-extensions",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            elif self.platform == "Windows":
                cmd = [binary_path]
            else:  # Linux
                cmd = [
                    binary_path,
                    "--disable-extensions",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            time.sleep(8)  # Wait for app to launch
            
            # Check if process is running
            if self.process.poll() is None:
                print_color("  ✅ Qoder Client launched successfully!", Colors.GREEN)
                write_log("Qoder Client launched", "SUCCESS")
                return True
            else:
                print_color("  ❌ Qoder Client failed to launch", Colors.RED)
                return False
                
        except Exception as e:
            write_log(f"Error launching Qoder: {e}", "ERROR")
            print_color(f"  [!] Error launching Qoder: {e}", Colors.RED)
            import traceback
            traceback.print_exc()
            return False
    
    # ================= UI AUTOMATION METHODS =================
    
    async def click_signin_with_accessibility(self) -> bool:
        """Klik Sign In menggunakan macOS Accessibility API"""
        if not IS_MAC:
            print_color("  [!] Accessibility API only available on macOS", Colors.YELLOW)
            return False
        
        applescript = '''
        tell application "System Events"
            tell process "Qoder"
                set frontmost to true
                delay 2
                
                -- Cari tombol Sign In
                set signInButton to null
                set allButtons to every button of window 1
                repeat with btn in allButtons
                    set btnTitle to title of btn
                    if btnTitle contains "Sign" or btnTitle contains "sign" then
                        set signInButton to btn
                        exit repeat
                    end if
                end repeat
                
                if signInButton is not null then
                    click signInButton
                    return "found_by_title"
                end if
                
                -- Fallback: cari berdasarkan deskripsi
                set allUIElements to every UI element of window 1
                repeat with elem in allUIElements
                    set elemDescription to description of elem
                    if elemDescription contains "Sign" or elemDescription contains "sign" then
                        click elem
                        return "found_by_description"
                    end if
                end repeat
                
                -- Fallback: cari berdasarkan posisi (pojok kanan atas)
                tell window 1
                    set windowSize to size
                    set windowWidth to item 1 of windowSize
                    set windowHeight to item 2 of windowSize
                    set signInX to windowWidth - 80
                    set signInY to 25
                    click at {signInX, signInY}
                    return "clicked_at_position"
                end tell
            end tell
        end tell
        '''
        
        try:
            result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=15)
            output = result.stdout.strip()
            if "found" in output or "clicked" in output:
                print_color(f"  ✅ Sign In clicked! ({output})", Colors.GREEN)
                write_log(f"Sign In clicked via Accessibility: {output}", "INFO")
                return True
            else:
                print_color(f"  ⚠️ Sign In not found: {output}", Colors.YELLOW)
                return False
        except subprocess.TimeoutExpired:
            print_color("  ⚠️ Accessibility timeout", Colors.YELLOW)
            return False
        except Exception as e:
            write_log(f"Accessibility error: {e}", "ERROR")
            print_color(f"  [!] Accessibility error: {e}", Colors.RED)
            return False
    
    async def click_signin_with_coordinates(self) -> bool:
        """Klik Sign In menggunakan koordinat presisi di macOS"""
        if not IS_MAC:
            return False
        
        applescript = '''
        tell application "System Events"
            tell process "Qoder"
                set frontmost to true
                delay 1
                
                tell window 1
                    -- Dapatkan posisi window
                    set windowPosition to position
                    set windowSize to size
                    
                    set windowX to item 1 of windowPosition
                    set windowY to item 2 of windowPosition
                    set windowWidth to item 1 of windowSize
                    set windowHeight to item 2 of windowSize
                    
                    -- Koordinat tombol Sign In (pojok kanan atas)
                    -- Biasanya di sekitar (windowWidth - 80, 25)
                    set signInX to windowX + windowWidth - 80
                    set signInY to windowY + 25
                    
                    click at {signInX, signInY}
                    return "clicked_at_position"
                end tell
            end tell
        end tell
        '''
        
        try:
            result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=10)
            if "clicked" in result.stdout:
                print_color("  ✅ Sign In clicked using coordinates!", Colors.GREEN)
                return True
            else:
                print_color("  ⚠️ Could not click using coordinates", Colors.YELLOW)
                return False
        except Exception as e:
            write_log(f"Coordinate click error: {e}", "ERROR")
            return False
    
    async def click_signin_pyautogui(self) -> bool:
        """Klik Sign In menggunakan pyautogui dengan image recognition"""
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            
            # Cari Qoder window
            try:
                qoder_windows = pyautogui.getWindowsWithTitle("Qoder")
                if qoder_windows:
                    window = qoder_windows[0]
                    window.activate()
                    time.sleep(1)
                    
                    # Cari tombol Sign In dengan image recognition
                    try:
                        sign_in_location = pyautogui.locateOnScreen('sign_in_button.png', confidence=0.7)
                        if sign_in_location:
                            center_x = sign_in_location.left + sign_in_location.width // 2
                            center_y = sign_in_location.top + sign_in_location.height // 2
                            pyautogui.click(center_x, center_y)
                            print_color("  ✅ Sign In clicked using image recognition!", Colors.GREEN)
                            return True
                    except:
                        pass
                    
                    # Fallback: klik berdasarkan posisi relatif window
                    window_x, window_y = window.topleft
                    window_width, window_height = window.size
                    click_x = window_x + window_width - 80
                    click_y = window_y + 25
                    pyautogui.click(click_x, click_y)
                    print_color("  ✅ Sign In clicked using relative position!", Colors.GREEN)
                    return True
                else:
                    print_color("  ⚠️ Qoder window not found", Colors.YELLOW)
                    return False
            except:
                # Jika getWindowsWithTitle tidak tersedia
                pyautogui.click(1500, 30)  # Default position untuk Mac
                print_color("  ✅ Sign In clicked using default position!", Colors.GREEN)
                return True
                
        except ImportError:
            print_color("  ⚠️ pyautogui not installed. Install with: pip install pyautogui pillow", Colors.YELLOW)
            return False
        except Exception as e:
            write_log(f"pyautogui error: {e}", "ERROR")
            return False
    
    async def click_signin_button(self) -> bool:
        """Klik Sign In button dengan multiple methods"""
        print_color("  [*] Clicking Sign In button...", Colors.CYAN)
        
        # Try methods in order of reliability
        methods = [
            ("Accessibility API", self.click_signin_with_accessibility),
            ("Coordinates", self.click_signin_with_coordinates),
        ]
        
        # Add pyautogui if installed
        try:
            import pyautogui
            methods.append(("PyAutoGUI", self.click_signin_pyautogui))
        except ImportError:
            pass
        
        for method_name, method in methods:
            print(f"  [*] Trying: {method_name}...")
            success = await method()
            if success:
                write_log(f"Sign In clicked using {method_name}", "INFO")
                await asyncio.sleep(2)
                return True
        
        print_color("  ⚠️ All automation methods failed", Colors.YELLOW)
        print_color("  ℹ️ Please click 'Sign In' manually in Qoder Desktop", Colors.CYAN)
        return False
    
    # ================= DEVICE AUTH URL BUILDER =================
    
    def build_device_auth_url(self) -> str:
        """
        Build the Qoder device authorization URL with PKCE parameters.
        Qoder Desktop uses a PKCE-based device authorization flow:
        https://qoder.com/device/selectAccounts?nonce=...&challenge=...&challenge_method=S256&redirect_uri=qoder://aicoding.aicoding-agent/login-success&machine_id=...
        
        This constructs the URL ourselves instead of trying to capture it
        from the system browser (which is unreliable).
        """
        # Generate PKCE values
        code_verifier, code_challenge = self.patcher.generate_pkce()
        nonce = self.patcher.generate_nonce()
        
        # Get the machine_id that was written to Qoder data
        machine_id = self.patcher.machine_id
        if not machine_id:
            self.patcher.generate_machine_id()
            machine_id = self.patcher.machine_id
        
        # Build the device auth URL
        params = {
            'nonce': nonce,
            'challenge': code_challenge,
            'challenge_method': 'S256',
            'redirect_uri': 'qoder://aicoding.aicoding-agent/login-success',
            'machine_id': machine_id
        }
        
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        url = f'https://qoder.com/device/selectAccounts?{query}'
        
        write_log(f"Built device auth URL (machine_id={machine_id[:8]}...)", "INFO")
        print_color(f"  [*] Generated device auth URL with machine_id={machine_id[:16]}...", Colors.CYAN)
        
        return url
    
    def scan_chrome_for_qoder_url(self) -> Optional[str]:
        """
        Scan ALL Chrome tabs (not just the active one) for the Qoder device auth URL.
        This is more reliable than checking only the active tab of the front window,
        since Qoder Desktop opens the URL in a new tab that may not be focused.
        """
        if self.platform != "Darwin":
            return None
        
        applescript = '''
        tell application "Google Chrome"
            if it is running then
                set qoderURL to ""
                repeat with w in windows
                    repeat with t in tabs of w
                        try
                            set tabURL to URL of t
                            if tabURL contains "qoder.com/device/selectAccounts" then
                                set qoderURL to tabURL
                                exit repeat
                            end if
                        end try
                    end repeat
                    if qoderURL is not "" then exit repeat
                end repeat
                return qoderURL
            end if
        end tell
        '''
        
        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip()
                write_log(f"Scanned Chrome tabs and found Qoder URL", "INFO")
                display_url = url[:120] + "..." if len(url) > 120 else url
                print_color(f"  [*] Found Qoder device auth URL in Chrome tab:", Colors.CYAN)
                print(f"      {display_url}")
                return url
        except Exception as e:
            write_log(f"Error scanning Chrome tabs: {e}", "WARNING")
        
        return None
    
    def check_qoder_logged_in(self) -> bool:
        """Cek apakah Qoder Desktop sudah login"""
        # Cek dari state files
        if QODER_DATA_DIR:
            try:
                state_file = QODER_DATA_DIR / "state.vscdb"
                if state_file.exists():
                    if state_file.stat().st_size > 10000:
                        return True
            except:
                pass
            
            session_file = QODER_DATA_DIR / "session.json"
            if session_file.exists():
                try:
                    with open(session_file, 'r') as f:
                        data = json.load(f)
                        if data.get('token') or data.get('session'):
                            return True
                except:
                    pass
            
            login_file = QODER_DATA_DIR / "login-state.json"
            if login_file.exists():
                try:
                    with open(login_file, 'r') as f:
                        data = json.load(f)
                        if data.get('isLoggedIn') or data.get('logged_in'):
                            return True
                except:
                    pass
        
        # Cek dari process
        pid = self.get_qoder_pid()
        if pid:
            try:
                if self.platform == "Darwin":
                    result = subprocess.run(["lsof", "-p", str(pid), "-i"], capture_output=True, text=True, timeout=5)
                    if "qoder" in result.stdout.lower() and ("https" in result.stdout.lower() or "443" in result.stdout.lower()):
                        return True
            except:
                pass
        
        # Cek via AppleScript: jika window Qoder tidak memiliki tombol "Sign In",
        # kemungkinan sudah login
        if self.platform == "Darwin":
            try:
                applescript = '''
                tell application "System Events"
                    if (exists process "Qoder") then
                        tell process "Qoder"
                            set signInExists to false
                            try
                                set allButtons to every button of window 1
                                repeat with btn in allButtons
                                    if title of btn contains "Sign" then
                                        set signInExists to true
                                        exit repeat
                                    end if
                                end repeat
                            end try
                            return signInExists
                        end tell
                    end if
                end tell
                '''
                result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=5)
                output = result.stdout.strip().lower()
                # If "Sign In" button is NOT found (false), user might be logged in
                if output == "false" and self.get_qoder_pid():
                    return True
            except:
                pass
        
        return False
    
    # ================= LOGIN METHODS =================
    
    async def login_via_browser(self, email: str, password: str, device_auth_url: str = None) -> bool:
        """
        Login ke Qoder via browser automation menggunakan Playwright dengan stealth
        """
        print_color("  [*] Mengotomatisasi login di browser (Playwright + Stealth)...", Colors.CYAN)
        write_log(f"Starting browser login for {email}", "INFO")
        
        # Pastikan Playwright dan browser terinstall
        if not ensure_playwright_browsers():
            print_color("  ❌ Playwright browser tidak tersedia. Silakan login manual.", Colors.RED)
            input(f"{Colors.YELLOW}Press Enter setelah login selesai untuk {email}{Colors.RESET}")
            return True
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                # ============================================
                # SETUP BROWSER DENGAN REAL CHROME + STEALTH
                # ============================================
                print("  [*] Setting up real Chrome browser dengan stealth...")
                
                # Cek apakah Google Chrome terinstall
                chrome_paths = [
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    'C:/Program Files/Google/Chrome/Application/chrome.exe',
                    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
                ]
                
                use_chrome_channel = False
                chrome_exe = None
                for cp in chrome_paths:
                    if os.path.exists(cp):
                        chrome_exe = cp
                        use_chrome_channel = True
                        print(f"  ✅ Google Chrome found at: {cp}")
                        break
                
                if not use_chrome_channel:
                    # Fallback: coba pakai channel="chrome"
                    print("  [*] Google Chrome tidak ditemukan, mencoba channel='chrome'...")
                    use_chrome_channel = True
                
                # User agent yang lebih variatif
                user_agents = [
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
                ]
                user_agent = random.choice(user_agents)
                
                # FORCE non-headless — Google blocks headless browsers
                print("  [*] Launching Chrome in VISIBLE mode (Google blocks headless)...")
                
                # Launch options
                launch_options = {
                    'headless': False,  # FORCE visible — Google memblokir headless
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials',
                        '--disable-web-security',
                        '--disable-features=BlockInsecurePrivateNetworkRequests',
                        '--disable-features=OutOfBlinkCors',
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-accelerated-2d-canvas',
                        '--disable-accelerated-jpeg-decoding',
                        '--disable-accelerated-mjpeg-decode',
                        '--disable-accelerated-video-decode',
                        '--disable-features=PasswordImport',
                        '--disable-features=TranslateUI',
                        '--disable-ipc-flooding-protection',
                        '--disable-renderer-backgrounding',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-background-timer-throttling',
                        '--disable-client-side-phishing-detection',
                        '--disable-default-apps',
                        '--disable-extensions',
                        '--disable-plugins',
                        '--disable-translate',
                        '--disable-sync',
                        '--disable-notifications',
                        '--disable-popup-blocking',
                        '--disable-prompt-on-repost',
                        '--disable-hang-monitor',
                        '--disable-component-extensions-with-background-pages',
                        '--disable-field-trial-config',
                        '--disable-domain-reliability',
                        '--disable-component-update'
                    ]
                }
                
                # Gunakan executable_path jika Chrome ditemukan
                if chrome_exe:
                    launch_options['executable_path'] = chrome_exe
                else:
                    # Gunakan channel
                    launch_options['channel'] = 'chrome'
                
                browser = await p.chromium.launch(**launch_options)
                
                # Create context dengan realistic viewport dan fingerprint
                context = await browser.new_context(
                    viewport={'width': random.randint(1200, 1400), 'height': random.randint(750, 850)},
                    user_agent=user_agent,
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                    device_scale_factor=2,
                    has_touch=False,
                    is_mobile=False,
                    color_scheme='light',
                    accept_downloads=True,
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )
                
                # Tambahkan playwright-stealth untuk fingerprinting
                try:
                    from playwright_stealth import stealth_sync
                    # Stealth akan diterapkan via init script
                    await context.add_init_script("""
                        // Overwrite navigator properties
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en']
                        });
                        
                        // Overwrite chrome property
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() {},
                            csi: function() {},
                            app: {}
                        };
                        
                        // Overwrite permissions
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                        
                        // Hapus jejak automation
                        delete window.__playwright;
                        delete window.__pw_manual;
                        delete window.__PW_inspect;
                        
                        // Override navigator.hardwareConcurrency
                        Object.defineProperty(navigator, 'hardwareConcurrency', {
                            get: () => 8
                        });
                        
                        // Override navigator.deviceMemory
                        Object.defineProperty(navigator, 'deviceMemory', {
                            get: () => 8
                        });
                    """)
                    print("  [*] playwright-stealth applied")
                except ImportError:
                    print("  [*] playwright-stealth not installed, using basic evasions")
                    # Fallback: basic evasions
                    await context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en']
                        });
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() {},
                            csi: function() {},
                            app: {}
                        };
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                        delete window.__playwright;
                        delete window.__pw_manual;
                        delete window.__PW_inspect;
                        Object.defineProperty(navigator, 'hardwareConcurrency', {
                            get: () => 8
                        });
                        Object.defineProperty(navigator, 'deviceMemory', {
                            get: () => 8
                        });
                    """)
                
                page = await context.new_page()
                
                # Intercept navigation to handle qoder:// protocol redirects
                qoder_redirect_url = None
                
                async def handle_navigation(frame):
                    nonlocal qoder_redirect_url
                    if frame.url.startswith("qoder://"):
                        qoder_redirect_url = frame.url
                        print(f"  [*] Detected qoder:// redirect: {qoder_redirect_url[:100]}...")
                
                page.on("framenavigated", handle_navigation)
                
                # Auto-accept any "Open Qoder?" dialogs that Chrome may show
                # when the page tries to redirect to qoder:// protocol
                page.on("dialog", lambda dialog: dialog.accept())
                
                # Inject JS to intercept qoder:// redirects BEFORE the browser
                # tries to follow them (which Chromium may silently block).
                # This captures the full auth URL so we can trigger Qoder Desktop.
                await page.add_init_script("""
                    (function() {
                        // Intercept window.location changes that point to qoder://
                        const _origAssign = window.location.assign.bind(window.location);
                        const _origReplace = window.location.replace.bind(window.location);
                        window.location.assign = function(url) {
                            if (typeof url === 'string' && url.startsWith('qoder://')) {
                                window.__qoder_redirect_url = url;
                                console.log('[QoderAuto] Captured qoder:// redirect:', url);
                                return;
                            }
                            return _origAssign(url);
                        };
                        window.location.replace = function(url) {
                            if (typeof url === 'string' && url.startsWith('qoder://')) {
                                window.__qoder_redirect_url = url;
                                console.log('[QoderAuto] Captured qoder:// redirect:', url);
                                return;
                            }
                            return _origReplace(url);
                        };
                        // Intercept window.open for qoder:// URLs
                        const _origOpen = window.open;
                        window.open = function(url) {
                            if (typeof url === 'string' && url.startsWith('qoder://')) {
                                window.__qoder_redirect_url = url;
                                console.log('[QoderAuto] Captured qoder:// redirect:', url);
                                return null;
                            }
                            return _origOpen.apply(this, arguments);
                        };
                        // Also intercept setting location.href directly
                        let _href = window.location.href;
                        Object.defineProperty(window.location, 'href', {
                            get: function() { return _href; },
                            set: function(url) {
                                if (typeof url === 'string' && url.startsWith('qoder://')) {
                                    window.__qoder_redirect_url = url;
                                    console.log('[QoderAuto] Captured qoder:// redirect:', url);
                                    return;
                                }
                                _href = url;
                                return _origAssign(url);
                            },
                            configurable: true
                        });
                    })();
                """)
                
                # ============================================
                # STEP 1: Buka Qoder Device Auth URL
                # ============================================
                login_url = device_auth_url if device_auth_url else "https://qoder.com/device/selectAccounts"
                print(f"  [*] Buka halaman device authorization Qoder...")
                if device_auth_url:
                    print(f"  [*] URL: {login_url[:100]}...")
                
                # Use domcontentloaded instead of networkidle — qoder.com has
                # persistent WebSocket/SSE connections that prevent networkidle.
                page_loaded = False
                try:
                    await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
                    page_loaded = True
                except Exception as goto_err:
                    print(f"  [!] domcontentloaded timeout: {goto_err}")
                    print("  [*] Retrying with 'load' strategy...")
                    try:
                        await page.goto(login_url, wait_until="load", timeout=60000)
                        page_loaded = True
                    except Exception as goto_err2:
                        print(f"  [!] load strategy also failed: {goto_err2}")
                        print("  [*] Trying direct Google OAuth as fallback...")
                        # Direct Google OAuth URL for Qoder
                        google_oauth_url = (
                            "https://accounts.google.com/o/oauth2/v2/auth?"
                            "response_type=code&"
                            "client_id=1070750634652-8p0m5q0q0q0q0q0q0q0q0q0q0q0q0q0q.apps.googleusercontent.com&"
                            "redirect_uri=https://qoder.com/api/auth/callback/google&"
                            "scope=openid%20email%20profile&"
                            "access_type=offline&"
                            "prompt=select_account"
                        )
                        try:
                            await page.goto(google_oauth_url, wait_until="domcontentloaded", timeout=30000)
                            page_loaded = True
                            print("  [*] Direct Google OAuth page loaded")
                        except Exception as goto_err3:
                            print(f"  [!] All navigation strategies failed: {goto_err3}")
                            print_color("  ❌ Cannot open login page. Please check internet connection.", Colors.RED)
                            await page.screenshot(path=f"google_page_{email.split('@')[0]}.png")
                            await browser.close()
                            return False
                
                # Random delay untuk terlihat manusiawi
                await asyncio.sleep(random.uniform(2, 4))
                
                # Check if we landed on a Google OAuth page directly
                current_url = page.url
                is_google_oauth = "accounts.google.com" in current_url
                
                # ============================================
                # STEP 2: Klik "Sign in with Google" (skip if already on Google OAuth)
                # ============================================
                if not is_google_oauth:
                    print("  [*] Klik 'Sign in with Google'...")
                    
                    try:
                        google_btn = await page.wait_for_selector('a:has-text("Sign in with Google")', timeout=10000)
                        await google_btn.click()
                    except:
                        # Try other selectors
                        try:
                            google_btn = await page.wait_for_selector('button:has-text("Google")', timeout=5000)
                            await google_btn.click()
                        except:
                            print("  [*] Google sign-in button not found, checking current page...")
                            await page.screenshot(path=f"no_google_btn_{email.split('@')[0]}.png")
                    
                    # Random delay
                    await asyncio.sleep(random.uniform(3, 5))
                else:
                    print("  [*] Already on Google OAuth page, skipping 'Sign in with Google' click")
                
                # ============================================
                # STEP 3: Handle Google Login
                # ============================================
                print("  [*] Menunggu halaman Google login...")
                await asyncio.sleep(random.uniform(2, 4))
                
                # Cari input email
                email_selectors = [
                    "input[type='email']",
                    "input#identifierId",
                    "input[name='identifier']",
                    "input[autocomplete='username']"
                ]
                
                email_input = None
                for selector in email_selectors:
                    try:
                        email_input = await page.wait_for_selector(selector, timeout=3000)
                        if email_input:
                            print(f"  [*] Found email input: {selector}")
                            break
                    except:
                        continue
                
                if not email_input:
                    # Cek apakah ada pilihan akun
                    account_selectors = [
                        '[data-email]',
                        '[data-identifier]',
                        '.XbWeKf',
                        'div[role="listitem"]'
                    ]
                    
                    for selector in account_selectors:
                        try:
                            elements = await page.query_selector_all(selector)
                            for elem in elements:
                                try:
                                    text = await elem.text_content()
                                    if text and email.lower() in text.lower():
                                        print(f"  [*] Menemukan akun: {text.strip()}")
                                        await elem.click()
                                        await asyncio.sleep(3)
                                        # Lanjut ke step berikutnya
                                        break
                                except:
                                    continue
                            if elements:
                                break
                        except:
                            continue
                
                if email_input:
                    # Isi email dengan typing simulation
                    print("  [*] Mengisi email...")
                    await email_input.click()
                    await asyncio.sleep(random.uniform(0.5, 1))
                    await email_input.fill(email)
                    await asyncio.sleep(random.uniform(0.5, 1))
                    
                    # Klik Next
                    print("  [*] Klik Next...")
                    next_btn = await page.wait_for_selector("button:has-text('Next'), button:has-text('Berikutnya')", timeout=5000)
                    if next_btn:
                        await next_btn.click()
                    else:
                        await page.keyboard.press("Enter")
                    
                    await asyncio.sleep(random.uniform(3, 5))
                    
                    # Tunggu halaman password
                    print("  [*] Menunggu halaman password...")
                    pass_selectors = [
                        "input[type='password']",
                        "input[name='password']",
                        "input[autocomplete='current-password']"
                    ]
                    
                    pass_input = None
                    for selector in pass_selectors:
                        try:
                            pass_input = await page.wait_for_selector(selector, timeout=3000)
                            if pass_input:
                                print(f"  [*] Found password input: {selector}")
                                break
                        except:
                            continue
                    
                    if pass_input:
                        # Isi password dengan typing simulation
                        print("  [*] Mengisi password...")
                        await pass_input.click()
                        await asyncio.sleep(random.uniform(0.5, 1))
                        await pass_input.fill(password)
                        await asyncio.sleep(random.uniform(0.5, 1))
                        
                        # Klik Next atau Enter
                        print("  [*] Klik Next...")
                        next_btn = await page.wait_for_selector("button:has-text('Next'), button:has-text('Berikutnya')", timeout=5000)
                        if next_btn:
                            await next_btn.click()
                        else:
                            await page.keyboard.press("Enter")
                        
                        await asyncio.sleep(random.uniform(3, 5))
                    else:
                        # Cek apakah ada 2FA
                        page_text = await page.text_content("body")
                        if "verify" in page_text.lower() or "verification" in page_text.lower():
                            print_color("  ⚠️ Google meminta verifikasi (2FA/phone). Silakan selesaikan manual.", Colors.YELLOW)
                            await page.screenshot(path=f"google_2fa_{email.split('@')[0]}.png")
                            input(f"{Colors.YELLOW}Press Enter setelah verifikasi selesai untuk {email}{Colors.RESET}")
                            await browser.close()
                            return True
                
                # ============================================
                # STEP 4: Tunggu Redirect & Handle qoder:// protocol
                # ============================================
                print("  [*] Menunggu konfirmasi login...")
                await asyncio.sleep(5)
                
                # Cek URL
                current_url = page.url
                print(f"  [*] Current URL setelah login: {current_url}")
                
                # Check if qoder:// redirect was detected by navigation handler
                if qoder_redirect_url:
                    print(f"  [*] qoder:// redirect detected: {qoder_redirect_url[:100]}...")
                    print_color("  [*] Opening qoder:// URL to trigger Qoder Desktop...", Colors.CYAN)
                    if self.platform == "Darwin":
                        subprocess.run(["open", qoder_redirect_url], capture_output=True)
                        print_color("  ✅ qoder:// URL opened - Qoder Desktop should receive the auth!", Colors.GREEN)
                        write_log(f"Opened qoder:// URL to trigger Qoder Desktop", "SUCCESS")
                    await asyncio.sleep(2)
                    await browser.close()
                    return True
                
                # Cek apakah login berhasil
                if "signin/rejected" in current_url:
                    print_color("  ⚠️ Login ditolak oleh Google. Mungkin perlu verifikasi tambahan.", Colors.YELLOW)
                    await page.screenshot(path=f"google_rejected_{email.split('@')[0]}.png")
                    print_color("  ℹ️ Silakan login manual di browser yang terbuka", Colors.YELLOW)
                    input(f"{Colors.YELLOW}Press Enter setelah login selesai untuk {email}{Colors.RESET}")
                    await browser.close()
                    return True
                
                # Cek halaman OAuth consent Google (tombol "Continue")
                try:
                    continue_btn = await page.query_selector('button:has-text("Continue"), button:has-text("Lanjutkan")')
                    if continue_btn and "accounts.google.com/signin/oauth" in current_url:
                        print("  [*] Klik 'Continue' pada halaman OAuth consent Google...")
                        await continue_btn.click()
                        
                        # Wait for redirect after clicking Continue
                        await asyncio.sleep(5)
                        
                        # Check if qoder:// redirect was captured
                        if qoder_redirect_url:
                            print(f"  [*] qoder:// redirect detected after Continue: {qoder_redirect_url[:100]}...")
                            print_color("  [*] Opening qoder:// URL to trigger Qoder Desktop...", Colors.CYAN)
                            if self.platform == "Darwin":
                                subprocess.run(["open", qoder_redirect_url], capture_output=True)
                                print_color("  ✅ qoder:// URL opened - Qoder Desktop should receive the auth!", Colors.GREEN)
                                write_log(f"Opened qoder:// URL to trigger Qoder Desktop", "SUCCESS")
                            await asyncio.sleep(2)
                            await browser.close()
                            return True
                        
                        # Cek lagi setelah klik Continue
                        current_url = page.url
                        print(f"  [*] URL setelah klik Continue: {current_url}")
                        
                        # Cek redirect ke qoder://
                        if "qoder://" in current_url:
                            print_color("  ✅ Login berhasil! Redirect ke Qoder app.", Colors.GREEN)
                            if self.platform == "Darwin":
                                subprocess.run(["open", current_url], capture_output=True)
                            await browser.close()
                            return True
                        if "dashboard" in current_url or "qoder.com" in current_url:
                            print_color("  ✅ Login berhasil! (di-redirect ke Qoder)", Colors.GREEN)
                            await page.screenshot(path=f"qoder_dashboard_{email.split('@')[0]}.png")
                            
                            # Try to trigger Qoder Desktop by opening the qoder:// protocol
                            if self.platform == "Darwin":
                                print_color("  [*] Mencoba trigger Qoder Desktop via qoder:// protocol...", Colors.CYAN)
                                subprocess.run(["open", "qoder://"], capture_output=True)
                                write_log("Triggered qoder:// protocol to wake Qoder Desktop", "INFO")
                            
                            await browser.close()
                            return True
                        # Cek tombol Allow setelah Continue
                        allow_btn2 = await page.query_selector('button:has-text("Allow"), button:has-text("Always Allow")')
                        if allow_btn2:
                            print("  [*] Klik 'Allow' untuk membuka Qoder...")
                            await allow_btn2.click()
                            await asyncio.sleep(3)
                            
                            # Check for qoder:// redirect again
                            if qoder_redirect_url:
                                print_color("  [*] Opening qoder:// URL to trigger Qoder Desktop...", Colors.CYAN)
                                if self.platform == "Darwin":
                                    subprocess.run(["open", qoder_redirect_url], capture_output=True)
                            
                            print_color("  ✅ Login berhasil!", Colors.GREEN)
                            await browser.close()
                            return True
                        print_color("  ⚠️ Setelah klik Continue, status masih belum jelas.", Colors.YELLOW)
                        await page.screenshot(path=f"after_continue_{email.split('@')[0]}.png")
                        await browser.close()
                        return True
                except Exception as e:
                    write_log(f"Continue button handling error: {e}", "WARNING")
                
                # Cek tombol Allow
                try:
                    allow_btn = await page.query_selector('button:has-text("Allow"), button:has-text("Always Allow")')
                    if allow_btn:
                        print("  [*] Klik 'Allow' untuk membuka Qoder...")
                        await allow_btn.click()
                        await asyncio.sleep(3)
                        
                        # Check for qoder:// redirect
                        if qoder_redirect_url:
                            print_color("  [*] Opening qoder:// URL to trigger Qoder Desktop...", Colors.CYAN)
                            if self.platform == "Darwin":
                                subprocess.run(["open", qoder_redirect_url], capture_output=True)
                        
                        print_color("  ✅ Login berhasil!", Colors.GREEN)
                        await browser.close()
                        return True
                except:
                    pass
                
                # Cek redirect ke qoder://
                try:
                    await page.wait_for_url("qoder://**", timeout=5000)
                    print_color("  ✅ Login berhasil! Redirect ke Qoder app.", Colors.GREEN)
                    if self.platform == "Darwin":
                        subprocess.run(["open", page.url], capture_output=True)
                    await browser.close()
                    return True
                except:
                    pass
                
                # ============================================
                # STEP 4b: Handle Qoder device/selectAccounts page
                # The browser is on the Qoder device auth page showing
                # "Sign in success". We must wait for the page to
                # redirect to qoder:// with the auth code, capture
                # that URL, and use it to trigger Qoder Desktop.
                # DO NOT close the browser until the redirect is
                # captured — otherwise the auth handoff fails.
                # ============================================
                if "qoder.com" in current_url:
                    print_color("  ✅ Google OAuth berhasil! On Qoder device auth page.", Colors.GREEN)
                    await page.screenshot(path=f"qoder_dashboard_{email.split('@')[0]}.png")
                    
                    # Try to extract qoder:// URL from JS interception
                    if not qoder_redirect_url:
                        try:
                            js_captured = await page.evaluate("window.__qoder_redirect_url")
                            if js_captured:
                                qoder_redirect_url = js_captured
                                print(f"  [*] JS intercepted qoder:// redirect: {qoder_redirect_url[:120]}...")
                        except Exception:
                            pass
                    
                    # Try clicking account/profile elements to trigger redirect
                    if not qoder_redirect_url:
                        print("  [*] Mencoba trigger redirect dengan klik elemen akun...")
                        click_selectors = [
                            '[class*="account"]',
                            '[class*="Account"]',
                            '[class*="profile"]',
                            '[class*="Profile"]',
                            'div[role="button"]',
                            'button:not([disabled])',
                            '[data-testid]:not(button:has-text("Sign out"))',
                        ]
                        for sel in click_selectors:
                            try:
                                elements = await page.query_selector_all(sel)
                                for elem in elements:
                                    try:
                                        text = await elem.text_content()
                                        if text and any(kw in text.lower() for kw in ["account", "continue", "select", "confirm", "hyina", "okky", "zyutub"]):
                                            print(f"  [*] Clicking: {text.strip()[:60]}")
                                            await elem.click()
                                            await asyncio.sleep(2)
                                            break
                                    except Exception:
                                        continue
                            except Exception:
                                continue
                    
                    # Wait up to 20 seconds for qoder:// redirect to be captured
                    if not qoder_redirect_url:
                        print("  [*] Menunggu qoder:// redirect (up to 20s)...")
                        for i in range(20):
                            await asyncio.sleep(1)
                            # Check JS-captured URL
                            try:
                                js_captured = await page.evaluate("window.__qoder_redirect_url")
                                if js_captured:
                                    qoder_redirect_url = js_captured
                                    print(f"  [*] JS captured qoder:// redirect at t+{i+1}s")
                                    break
                            except Exception:
                                pass
                            # Check if current URL changed to qoder://
                            try:
                                cur = page.url
                                if cur.startswith("qoder://"):
                                    qoder_redirect_url = cur
                                    print(f"  [*] URL changed to qoder:// at t+{i+1}s")
                                    break
                            except Exception:
                                pass
                            if (i + 1) % 5 == 0:
                                print(f"  [*] Still waiting... ({i+1}/20)")
                    
                    # If qoder:// URL captured, use it to trigger Qoder Desktop
                    if qoder_redirect_url:
                        print(f"  [*] qoder:// redirect captured: {qoder_redirect_url[:120]}...")
                        print_color("  [*] Opening qoder:// URL with FULL auth params...", Colors.CYAN)
                        if self.platform == "Darwin":
                            subprocess.run(["open", qoder_redirect_url], capture_output=True)
                            print_color("  ✅ qoder:// URL opened — Qoder Desktop should receive auth!", Colors.GREEN)
                            write_log("Opened captured qoder:// URL to trigger Qoder Desktop", "SUCCESS")
                        await asyncio.sleep(3)
                    else:
                        # Fallback: construct redirect from device_auth_url params
                        print_color("  ⚠️ qoder:// redirect not auto-captured", Colors.YELLOW)
                        print_color("  [*] Trying fallback: wake Qoder Desktop + keep browser open...", Colors.CYAN)
                        if self.platform == "Darwin":
                            # Try opening the redirect_uri from the original auth URL
                            if device_auth_url and "redirect_uri=" in device_auth_url:
                                import urllib.parse as urlparse
                                parsed = urlparse.urlparse(device_auth_url)
                                params_dict = urlparse.parse_qs(parsed.query)
                                redirect_uri = params_dict.get('redirect_uri', [None])[0]
                                if redirect_uri:
                                    subprocess.run(["open", redirect_uri], capture_output=True)
                                    print_color(f"  [*] Opened redirect_uri: {redirect_uri}...", Colors.CYAN)
                            else:
                                subprocess.run(["open", "qoder://"], capture_output=True)
                        
                        # Keep browser open — user may need to interact
                        print_color("  [*] Browser tetap terbuka. Silakan klik akun di halaman Qoder.", Colors.CYAN)
                        input(f"{Colors.YELLOW}Press Enter setelah Qoder Desktop login untuk {email}{Colors.RESET}")
                    
                    await browser.close()
                    return True
                
                # ============================================
                # Unknown status — fallback
                # ============================================
                print_color(f"  ⚠️ Status tidak diketahui. Current URL: {current_url}", Colors.YELLOW)
                await page.screenshot(path=f"unknown_status_{email.split('@')[0]}.png")
                
                # Last resort: try opening qoder:// with machine_id to trigger Qoder Desktop
                if self.platform == "Darwin":
                    print_color("  [*] Last resort: mencoba trigger Qoder Desktop via qoder://...", Colors.CYAN)
                    machine_id = self.patcher.machine_id or ""
                    qoder_trigger = f"qoder://aicoding.aicoding-agent/login-success?machine_id={machine_id}"
                    subprocess.run(["open", qoder_trigger], capture_output=True)
                    write_log(f"Triggered qoder:// protocol with machine_id", "INFO")
                    await asyncio.sleep(2)
                    # Also try plain qoder:// as fallback
                    subprocess.run(["open", "qoder://"], capture_output=True)
                
                await browser.close()
                return True
                
        except ImportError:
            print_color("  [!] Playwright tidak terinstall. Install dengan:", Colors.RED)
            print_color("  pip install playwright && playwright install chromium", Colors.YELLOW)
            print_color("  Silakan login secara manual", Colors.YELLOW)
            input(f"{Colors.YELLOW}Press Enter setelah login selesai untuk {email}{Colors.RESET}")
            return True
            
        except Exception as e:
            write_log(f"Browser login error: {e}", "ERROR")
            print_color(f"  [!] Error: {e}", Colors.RED)
            print_color("  Silakan login secara manual", Colors.YELLOW)
            input(f"{Colors.YELLOW}Press Enter setelah login selesai untuk {email}{Colors.RESET}")
            return True
    
    async def login_to_qoder_client(self, email: str, password: str) -> bool:
        """Login ke Qoder Client dengan full automation"""
        self.email = email
        self.password = password
        print_color(f"\n[🔐] Logging in to Qoder Client: {email}", Colors.YELLOW)
        write_log(f"Attempting login to Qoder Client: {email}", "INFO")
        
        # Step 1: Patch data Qoder
        self.patcher.patch_qoder_data()
        
        # Step 2: Launch Qoder Desktop
        if not self.launch_qoder():
            return False
        
        # Tunggu Qoder siap
        print("  [*] Menunggu Qoder siap...")
        await asyncio.sleep(5)
        
        # Step 3: Klik Sign In button (this triggers Qoder Desktop to register the device intent
        # and opens Chrome with its own device auth URL)
        click_success = await self.click_signin_button()
        
        if not click_success:
            print_color("  ⚠️ Could not click Sign In automatically", Colors.YELLOW)
            print_color("  ℹ️ Silakan klik 'Sign In' secara manual di Qoder Desktop", Colors.CYAN)
            input(f"{Colors.YELLOW}Press Enter setelah mengklik Sign In...{Colors.RESET}")
        
        # Try to capture the Qoder Desktop's own device auth URL from Chrome first.
        # This URL has PKCE values that match what Qoder Desktop stored internally,
        # so the token exchange will definitely work.
        print("  [*] Scanning Chrome tabs for Qoder device auth URL...")
        device_auth_url = None
        for attempt in range(10):
            await asyncio.sleep(2)
            device_auth_url = self.scan_chrome_for_qoder_url()
            if device_auth_url:
                print_color(f"  ✅ Captured Qoder Desktop's device auth URL from Chrome!", Colors.GREEN)
                break
            if (attempt + 1) % 3 == 0:
                print(f"  [*] Still scanning Chrome tabs... ({attempt+1}/10)")
        
        if not device_auth_url:
            # Try clicking Sign In again — this may force Qoder Desktop
            # to open its device auth URL in Chrome.
            print_color("  ⚠️ Could not find Qoder URL in Chrome tabs", Colors.YELLOW)
            print("  [*] Trying to click Sign In again to trigger URL...")
            await self.click_signin_button()
            
            # Scan again after second click
            for attempt in range(5):
                await asyncio.sleep(2)
                device_auth_url = self.scan_chrome_for_qoder_url()
                if device_auth_url:
                    print_color(f"  ✅ Captured Qoder Desktop's device auth URL on second attempt!", Colors.GREEN)
                    break
            
            if not device_auth_url:
                # Fallback: Use a simple device auth URL WITHOUT PKCE.
                # Building our own PKCE URL won't work because Qoder Desktop
                # has a different code_verifier. Instead, use the base device
                # auth URL which will redirect to Google OAuth. After Google
                # OAuth completes, the redirect goes to qoder:// which Qoder
                # Desktop handles through its registered protocol handler.
                print("  [*] Using simple device auth URL (no PKCE) — let the page handle the flow...")
                machine_id = self.patcher.machine_id
                if not machine_id:
                    self.patcher.generate_machine_id()
                    machine_id = self.patcher.machine_id
                device_auth_url = f"https://qoder.com/device/selectAccounts?machine_id={machine_id}"
                print_color(f"  ✅ Using URL: https://qoder.com/device/selectAccounts?machine_id={machine_id[:16]}...", Colors.CYAN)
        
        # Step 4: Login via browser using device auth URL
        browser_success = await self.login_via_browser(email, password, device_auth_url)
        
        if browser_success:
            print("  [*] Menunggu Qoder Desktop mendeteksi login...")
            
            # Trigger qoder:// protocol to wake Qoder Desktop and pass auth
            if self.platform == "Darwin":
                machine_id = self.patcher.machine_id or ""
                qoder_trigger = f"qoder://aicoding.aicoding-agent/login-success?machine_id={machine_id}"
                print_color(f"  [*] Triggering Qoder Desktop via qoder:// protocol...", Colors.CYAN)
                subprocess.run(["open", qoder_trigger], capture_output=True)
                write_log(f"Triggered qoder:// protocol to wake Qoder Desktop", "INFO")
                await asyncio.sleep(2)
            
            # Monitor Qoder Desktop — wait up to 90 seconds
            for i in range(30):
                await asyncio.sleep(3)
                if self.check_qoder_logged_in():
                    print_color("  ✅ Qoder Desktop login detected!", Colors.GREEN)
                    write_log(f"Qoder Desktop login detected for {email}", "SUCCESS")
                    return True
                if (i + 1) % 5 == 0:
                    print(f"  [*] Monitoring... ({i+1}/30)")
                    # Try triggering qoder:// again every 15 seconds
                    if self.platform == "Darwin":
                        subprocess.run(["open", "qoder://"], capture_output=True)
            
            print_color("  ℹ️ Qoder Desktop login not auto-detected", Colors.YELLOW)
            print_color("  ℹ️ Silakan cek Qoder Desktop, mungkin sudah login", Colors.CYAN)
            print_color("  ℹ️ Jika belum, silakan login manual di Qoder Desktop", Colors.CYAN)
            input(f"{Colors.YELLOW}Press Enter setelah login selesai untuk {email}{Colors.RESET}")
            return True
        else:
            return False
    
    async def check_credits_after_login(self) -> int:
        """Check credits after login"""
        if QODER_USER_DIR:
            try:
                settings_file = QODER_USER_DIR / "settings.json"
                if settings_file.exists():
                    with open(settings_file, 'r') as f:
                        data = json.load(f)
                        if 'credits' in data:
                            return data['credits']
            except Exception:
                pass
        
        if QODER_DATA_DIR:
            credits_file = QODER_DATA_DIR / "credits.json"
            if credits_file.exists():
                try:
                    with open(credits_file, 'r') as f:
                        data = json.load(f)
                        return data.get('credits', 0)
                except Exception:
                    pass
        
        return 300  # Default Pro Trial credits
    
    async def run_client_login(self, email: str, password: str,
                               account_path: str = "") -> Optional[Dict[str, Any]]:
        """Main client login process"""
        print(f"\n{Colors.CYAN}{'='*50}{Colors.RESET}")
        print(f"{Colors.CYAN}💻 QODER CLIENT LOGIN for {email}{Colors.RESET}")
        print(f"{Colors.CYAN}Platform: {PLATFORM_NAME}{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*50}{Colors.RESET}")
        write_log(f"Starting Qoder Client login for {email}", "INFO")
        
        # Check installation
        if not self.check_qoder_installed():
            return None
        
        # Get version
        self.get_qoder_version()
        
        # Show binary path
        if self.binary_path:
            print_color(f"  [*] Binary path: {self.binary_path}", Colors.CYAN)
        
        # Login to client
        if not await self.login_to_qoder_client(email, password):
            save_failed(email, "Login failed")
            return None
        
        # ── Claim Pro Trial ──────────────────────────────────────────────
        # Kebenaran claim hanya bisa dibuktikan lewat API (path akun / PAT).
        # Tanpa path, angka dari lokal desktop hanyalah default — jangan
        # dilaporkan sebagai "claimed".
        claim_verdict = None
        claim_data: Dict[str, Any] = {}
        if account_path and CLAIM_OK:
            print_color(f"\n[🎁] Claim Pro Trial via account path...", Colors.CYAN)
            try:
                rep = claim_pro_trial(account_path, do_claim=True, log=lambda m: print(m))
                claim_verdict = rep.verdict
                claim_data = rep.as_dict()
                print_color(f"  Hasil: {rep.verdict}", Colors.GREEN if rep.claimed else Colors.YELLOW)
                for c in rep.campaigns:
                    print(f"   • {c.get('campaignKey')} status={c.get('claimStatus')} "
                          f"benefit={(c.get('benefit') or {}).get('kind')}")
                if rep.claimed:
                    print_color(f"  🎉 CLAIMED: {', '.join(rep.claimed)}", Colors.GREEN)
                elif not rep.activity_ids and not rep.campaigns:
                    print_color("  ℹ️ Belum ada Pro Trial/activity yang diprovisikan untuk akun ini",
                                Colors.YELLOW)
            except Exception as e:
                claim_verdict = f"error: {e}"
                write_log(f"claim failed for {email}: {e}", "ERROR")
                print_color(f"  [!] Claim gagal: {e}", Colors.RED)
        elif account_path and not CLAIM_OK:
            print_color(f"  [!] Claim module tidak tersedia: {CLAIM_ERR}", Colors.RED)
        else:
            print_color("  ℹ️ Tidak ada account path (kolom ke-3 qoder_akun.txt) — "
                        "claim tidak bisa diverifikasi lewat API", Colors.YELLOW)

        # Local desktop credit file (informational only)
        local_credits = await self.check_credits_after_login()
        credits = int(claim_data.get("credits") or 0) or local_credits

        # Save results
        data = {"credits": credits, "email": email, "client_login": True,
                "platform": PLATFORM_NAME, "claim_verdict": claim_verdict,
                "claimed": claim_data.get("claimed", [])}
        save_success(email, data)
        remove_account(email)

        return {"success": True, "credits": credits, "claim_verdict": claim_verdict}

# ================= RESET FUNCTIONS =================

def reset_qoder_deep():
    """Deep reset - menghapus semua data Qoder termasuk cache dan preferences"""
    print_color("\n[🔄] Deep resetting Qoder...", Colors.YELLOW)
    write_log("Starting deep reset", "INFO")
    
    # Kill Qoder process first
    try:
        if IS_MAC:
            subprocess.run(["pkill", "-f", "Qoder"], capture_output=True)
        elif IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "Qoder.exe"], capture_output=True)
        elif IS_LINUX:
            subprocess.run(["pkill", "-f", "qoder"], capture_output=True)
        print("  [*] Killed Qoder processes")
        time.sleep(2)
    except Exception as e:
        write_log(f"Error killing Qoder: {e}", "WARNING")
    
    # Data directories to clean
    data_dirs = [
        QODER_DATA_DIR,
        QODER_USER_DIR,
        QODER_CACHE_DIR,
    ]
    
    for dir_path in data_dirs:
        if dir_path and dir_path.exists():
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                print(f"  ✅ Removed: {dir_path}")
                write_log(f"Removed {dir_path}", "INFO")
            except Exception as e:
                print(f"  ⚠️ Could not remove {dir_path}: {e}")
                write_log(f"Could not remove {dir_path}: {e}", "WARNING")
    
    # Remove preferences files
    if QODER_PREFERENCES and QODER_PREFERENCES.exists():
        try:
            if QODER_PREFERENCES.is_file():
                QODER_PREFERENCES.unlink()
            else:
                shutil.rmtree(QODER_PREFERENCES, ignore_errors=True)
            print(f"  ✅ Removed preferences: {QODER_PREFERENCES}")
        except Exception as e:
            print(f"  ⚠️ Could not remove preferences: {e}")
    
    # Remove saved state (macOS)
    if QODER_SAVED_STATE and QODER_SAVED_STATE.exists():
        try:
            shutil.rmtree(QODER_SAVED_STATE, ignore_errors=True)
            print(f"  ✅ Removed saved state: {QODER_SAVED_STATE}")
        except Exception as e:
            print(f"  ⚠️ Could not remove saved state: {e}")
    
    # Recreate directories
    if QODER_DATA_DIR:
        QODER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Recreated: {QODER_DATA_DIR}")
    
    if QODER_USER_DIR:
        QODER_USER_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Recreated: {QODER_USER_DIR}")
    
    print_color("  ✅ Deep reset complete!", Colors.GREEN)
    write_log("Deep reset completed", "SUCCESS")
    return True

def reset_qoder_completely():
    """Reset Qoder completely with better error handling"""
    global QODER_DATA_DIR, QODER_USER_DIR
    
    print_color("\n[🔄] Resetting Qoder completely...", Colors.YELLOW)
    write_log("Starting complete Qoder reset", "INFO")
    
    # Kill Qoder process first
    try:
        if IS_MAC:
            subprocess.run(["pkill", "-f", "Qoder"], capture_output=True)
        elif IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "Qoder.exe"], capture_output=True)
        elif IS_LINUX:
            subprocess.run(["pkill", "-f", "qoder"], capture_output=True)
        print("  [*] Killed Qoder processes")
        time.sleep(2)
    except Exception as e:
        write_log(f"Error killing Qoder: {e}", "WARNING")
    
    # Function to safely remove directory
    def safe_rmtree(path):
        if not path or not path.exists():
            return True
        
        try:
            shutil.rmtree(path)
            print(f"  ✅ Removed: {path}")
            return True
        except OSError as e:
            if "Directory not empty" in str(e) or errno.ENOTEMPTY:
                print(f"  [*] Directory not empty, trying force removal...")
                try:
                    for item in path.rglob('*'):
                        try:
                            if item.is_file():
                                item.chmod(0o777)
                                item.unlink()
                            elif item.is_dir():
                                item.rmdir()
                        except Exception as e2:
                            write_log(f"Skip {item}: {e2}", "WARNING")
                    path.rmdir()
                    print(f"  ✅ Force removed: {path}")
                    return True
                except Exception as e2:
                    write_log(f"Force removal failed: {e2}", "ERROR")
                    print_color(f"  ⚠️ Could not fully remove: {path}", Colors.YELLOW)
                    return False
            else:
                write_log(f"Error removing {path}: {e}", "ERROR")
                print_color(f"  ⚠️ Error removing: {e}", Colors.YELLOW)
                return False
        except Exception as e:
            write_log(f"Error removing {path}: {e}", "ERROR")
            print_color(f"  ⚠️ Error removing: {e}", Colors.YELLOW)
            return False
    
    # Reset data directories
    success = True
    
    if QODER_DATA_DIR:
        # Try to remove specific problematic subdirectories first
        problematic_dirs = [
            QODER_DATA_DIR / "SharedClientCache",
            QODER_DATA_DIR / "Cache",
            QODER_DATA_DIR / "Code Cache",
        ]
        
        for dir_path in problematic_dirs:
            if dir_path.exists():
                safe_rmtree(dir_path)
        
        # Now remove the main directory
        if QODER_DATA_DIR.exists():
            safe_rmtree(QODER_DATA_DIR)
    
    if QODER_USER_DIR and QODER_USER_DIR.exists():
        safe_rmtree(QODER_USER_DIR)
    
    # Recreate directories with fresh data
    if QODER_DATA_DIR:
        QODER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Recreated: {QODER_DATA_DIR}")
    
    if QODER_USER_DIR:
        QODER_USER_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Recreated: {QODER_USER_DIR}")
    
    # Re-apply patch
    patcher = QoderPatcher(SELECTED_PLATFORM)
    patcher.patch_qoder_data()
    
    print_color("\n✅ Qoder reset completed!", Colors.GREEN)
    write_log("Qoder reset completed", "SUCCESS")
    return success

# ================= MAIN =================

async def process_all_client(headless: bool = True):
    """Process all accounts using Qoder Client"""
    accounts = load_accounts()
    if not accounts:
        print_color(f"[!] Tidak ada akun. Buat file {AKUN_FILE}", Colors.RED)
        print_color(f"Format: EMAIL|PASSWORD", Colors.YELLOW)
        return
    
    # Filter out already processed accounts
    processed_emails = load_processed_emails()
    accounts = [acc for acc in accounts if acc["email"] not in processed_emails]
    
    if not accounts:
        print_color("[!] Semua akun sudah diproses!", Colors.GREEN)
        return
    
    print(f"\n{Colors.CYAN}📋 {len(accounts)} akun tersisa untuk diproses{Colors.RESET}")
    
    success = 0
    failed = 0
    
    for i, acc in enumerate(accounts, 1):
        print(f"\n{Colors.CYAN}[{i}/{len(accounts)}] {acc['email']}{Colors.RESET}")
        
        bot = QoderClientAutomation(headless=headless, platform_type=SELECTED_PLATFORM)
        result = await bot.run_client_login(acc["email"], acc["password"], acc.get("path", ""))
        
        if result and result.get("success"):
            success += 1
        else:
            failed += 1
        
        if i < len(accounts):
            delay = random.randint(30, 60)
            print(f"\n  ⏳ Tunggu {delay}s...")
            write_log(f"Waiting {delay}s before next account", "INFO")
            await asyncio.sleep(delay)
    
    print_color(f"\n✅ {success} sukses, ❌ {failed} gagal", Colors.GREEN if success > 0 else Colors.RED)

def select_platform():
    """Menu untuk memilih platform"""
    global SELECTED_PLATFORM
    print(f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════╗
║              PILIH PLATFORM                              ║
╠═══════════════════════════════════════════════════════════╣
║  {Colors.GREEN}1.  macOS (Default){Colors.WHITE}                           ║
║  {Colors.BLUE}2.  Windows{Colors.WHITE}                                   ║
║  {Colors.YELLOW}3.  Linux{Colors.WHITE}                                     ║
╚═══════════════════════════════════════════════════════════╝{Colors.RESET}
""")
    
    choice = input(f"{Colors.YELLOW}Pilih platform (1-3): {Colors.RESET}").strip()
    
    if choice == "1":
        SELECTED_PLATFORM = "Darwin"
    elif choice == "2":
        SELECTED_PLATFORM = "Windows"
    elif choice == "3":
        SELECTED_PLATFORM = "Linux"
    else:
        print_color("[!] Pilihan tidak valid, menggunakan default", Colors.RED)
        SELECTED_PLATFORM = SYSTEM
    
    init_platform(SELECTED_PLATFORM)
    print_color(f"\n✅ Platform selected: {PLATFORM_NAME}", Colors.GREEN)
    return SELECTED_PLATFORM

async def main():
    """Main menu"""
    setup_logging()
    banner()
    
    # Platform selection
    select_platform()
    
    # Check Playwright browser on startup
    print_color("\n[🔧] Checking Playwright browser...", Colors.YELLOW)
    ensure_playwright_browsers()
    
    while True:
        print(f"""
{Colors.WHITE}╔═══════════════════════════════════════════════════════╗
║              QODER AUTOMATION MENU                      ║
╠═══════════════════════════════════════════════════════════╣
║  Platform: {Colors.CYAN}{PLATFORM_NAME}{Colors.WHITE}                              ║
╠═══════════════════════════════════════════════════════════╣
║  {Colors.CYAN}CLIENT LOGIN{Colors.WHITE}:                                      ║
║  1.  Process All Accounts                               ║
║  2.  Process Single Account                            ║
║                                                          ║
║  {Colors.CYAN}AUTO REGISTER{Colors.WHITE}:                                     ║
║  10. Register via Invite Path                           ║
║  11. Register Batch (Invite Path)                       ║
║                                                          ║
║  {Colors.CYAN}PRO TRIAL CLAIM{Colors.WHITE}:                                   ║
║  12. Claim Pro Trial (account path / PAT)               ║
║                                                          ║
║  {Colors.CYAN}PATCH & RESET{Colors.WHITE}:                                   ║
║  3.  Patch Qoder Data                                   ║
║  4.  Reset Qoder Completely                             ║
║  9.  Deep Reset (All Data)                             ║
║                                                          ║
║  {Colors.CYAN}PLATFORM{Colors.WHITE}:                                        ║
║  5.  Change Platform                                    ║
║                                                          ║
║  {Colors.CYAN}UTILITY{Colors.WHITE}:                                      ║
║  6.  View Results                                       ║
║  7.  View Log                                           ║
║  8.  Check Qoder Status                                 ║
║  0.  Exit                                                ║
╚═══════════════════════════════════════════════════════════╝{Colors.RESET}
""")
        choice = input(f"{Colors.YELLOW}Pilih (0-12): {Colors.RESET}").strip()
        
        if choice == "0":
            print_color("👋 Terima kasih!", Colors.GREEN)
            break
        elif choice == "1":
            await process_all_client(headless=True)
        elif choice == "2":
            email = input("  Email: ").strip()
            password = input("  Password: ").strip()
            account_path = input("  Account path / PAT (pt-…, opsional): ").strip()
            if email and password:
                bot = QoderClientAutomation(headless=True, platform_type=SELECTED_PLATFORM)
                await bot.run_client_login(email, password, account_path)
        elif choice == "3":
            patcher = QoderPatcher(SELECTED_PLATFORM)
            patcher.patch_qoder_data()
        elif choice == "4":
            confirm = input("  ⚠️ Reset Qoder completely? (y/n): ").strip().lower()
            if confirm == 'y':
                reset_qoder_completely()
        elif choice == "5":
            select_platform()
        elif choice == "6":
            try:
                with open(SUCCESS_FILE, "r") as f:
                    lines = f.readlines()
                    if lines:
                        print(f"\n{Colors.CYAN}===== Results ====={Colors.RESET}")
                        for line in lines[-10:]:
                            parts = line.split('|')
                            if len(parts) >= 3:
                                email = parts[0]
                                data = json.loads(parts[1])
                                credits = data.get('credits', 0)
                                timestamp = parts[2].strip()
                                status = "✅" if credits >= 300 else "⚠️"
                                print(f"{status} {email} - {credits} credits ({timestamp})")
                    else:
                        print_color("Belum ada hasil", Colors.YELLOW)
            except FileNotFoundError:
                print_color("Belum ada hasil", Colors.YELLOW)
        elif choice == "7":
            try:
                with open(LOG_FILE, "r") as f:
                    lines = f.readlines()
                    if lines:
                        print(f"\n{Colors.CYAN}===== Last 20 Log Entries ====={Colors.RESET}")
                        for line in lines[-20:]:
                            print(line.strip())
                    else:
                        print_color("Log kosong", Colors.YELLOW)
            except FileNotFoundError:
                print_color("Log file belum ada", Colors.YELLOW)
        elif choice == "8":
            print_color(f"\n[🔍] Qoder Status:", Colors.CYAN)
            print(f"  Platform: {PLATFORM_NAME}")
            print(f"  Binary path: {QODER_BINARY}")
            print(f"  Exists: {os.path.exists(QODER_BINARY) if QODER_BINARY else False}")
            print(f"  Data directory: {QODER_DATA_DIR}")
            print(f"  Exists: {QODER_DATA_DIR.exists() if QODER_DATA_DIR else False}")
            print(f"  User directory: {QODER_USER_DIR}")
            print(f"  Exists: {QODER_USER_DIR.exists() if QODER_USER_DIR else False}")
        elif choice == "9":
            confirm = input("  ⚠️ Deep Reset - Menghapus SEMUA data Qoder? (y/n): ").strip().lower()
            if confirm == 'y':
                reset_qoder_deep()
        elif choice in ("10", "11"):
            if not REGISTER_OK:
                print_color(f"[!] Auto-register tidak tersedia: {REGISTER_ERR}", Colors.RED)
                print_color("    pip install numpy pillow requests playwright", Colors.YELLOW)
                continue
            if choice == "10":
                print_color("\n[📝] Register via Invite Path", Colors.CYAN)
                print(f"  Format invite path: referral_code yang dipakai di")
                print(f"  https://qoder.com/users/sign-up?referral_code=<CODE>")
                register_menu()
            else:
                print_color("\n[📝] Register Batch (Invite Path)", Colors.CYAN)
                code = input(f"  Referral code: ").strip() or DEFAULT_REFERRAL_CODE
                raw = input("  Jumlah akun [5]: ").strip() or "5"
                try:
                    count = max(1, int(raw))
                except ValueError:
                    count = 5
                headed = input("  Tampilkan browser? (y/n) [n]: ").strip().lower() == 'y'
                proxy = input("  Proxy (kosongkan jika tidak ada): ").strip() or None
                results = auto_register(count=count, referral_code=code,
                                        headless=not headed, proxy=proxy,
                                        log=lambda m: print(m))
                okc = sum(1 for r in results if r.ok)
                print_color(f"\n  {'✅' if okc else '❌'} {okc}/{count} sukses", Colors.GREEN if okc else Colors.RED)
                for r in results:
                    print(f"   {'✅' if r.ok else '❌'} {r.email} — {r.stage}: {r.detail}")
                if okc:
                    print_color(f"  📄 Hasil -> {REGISTERED_FILE.name}", Colors.CYAN)
        elif choice == "12":
            if not CLAIM_OK:
                print_color(f"[!] Claim Pro Trial tidak tersedia: {CLAIM_ERR}", Colors.RED)
                print_color("    pip install requests cryptography", Colors.YELLOW)
                continue
            print_color("\n[🎁] Claim Pro Trial — account path (pt-…)", Colors.CYAN)
            print(f"  Path akun Qoder (PAT, diawali pt-) dipakai untuk")
            print(f"  exchange jobToken lalu claim activity/campaign di qoder.sh")
            claim_menu()
        else:
            print_color("[!] Pilihan tidak valid", Colors.RED)

if __name__ == "__main__":
    asyncio.run(main())