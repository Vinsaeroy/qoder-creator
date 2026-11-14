#!/usr/bin/env python3
"""
Qoder auto-register via invite path (referral_code).

Drop-in module for qoder-creator. Handles the whole public sign-up flow:

    POST /users/sign-up?referral_code=<CODE>
      step 1  firstName + lastName + email + accept terms
      step 2  password
      step 3  Aliyun slider captcha  (solved by template matching)
      step 4  e-mail one-time code   (read from a mail.tm inbox)

Endpoints taken from the live app bundle (qbase/qoder 0.0.757):
    POST /api/v1/verificationCodes   {channel:"email", scene, email}
    POST /api/v1/users               {type,email,password,code,name,
                                      invitation_code,attribution,channel_code,
                                      channel_ref,landing_id,captured_at}
    GET  /api/v1/me                  -> plan + credits, used as proof of success

Standalone use:
    python qoder_register.py --count 1
    python qoder_register.py --code pt-xxxx --headed --keep-open
"""

from __future__ import annotations

import base64
import email
import imaplib
import re as _re
import io
import json
import os
import random
import re
import string
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view
    from PIL import Image
    import requests
    from playwright.sync_api import Page, TimeoutError as PWTimeout
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"[register] missing dependency: {e}\n"
                     f"  pip install numpy pillow requests playwright playwright-stealth")

# ─────────────────────────── defaults ─────────────────────────

# Mowy's invite path. Can be overridden per call / from the menu.
DEFAULT_REFERRAL_CODE = "pt-bftOfFy7tDRJpRIVOWINV8Dk_01a1d5f9-75da-7c85-ad8f-c2ecca9016da"

SIGNUP_URL = "https://qoder.com/users/sign-up"
ME_API = "https://qoder.com/api/v1/me"
BASE_DIR = Path(__file__).parent
DEBUG_DIR = BASE_DIR / "register_debug"
REGISTERED_FILE = BASE_DIR / "qoder_registered.txt"   # email|password|code|credits|ts
REGISTER_FAILED_FILE = BASE_DIR / "qoder_reg_failed.txt"
REGISTER_LOG = BASE_DIR / "qoder_reg_log.txt"

NAV_TIMEOUT = 60_000
STEP_TIMEOUT = 30_000
MAIL_WAIT = 180
MAIL_PROVIDER = os.environ.get("QREG_MAIL", "inboxes")   # inboxes | mailnesia | tmplol | mailtm

FIRST_NAMES = ["Aiden", "Nadia", "Rafael", "Yuki", "Tomas", "Selma", "Ivan",
               "Mira", "Dorian", "Lena", "Kai", "Farah", "Nils", "Anya"]
LAST_NAMES = ["Voss", "Halim", "Moreau", "Kanda", "Ricci", "Brandt", "Novak",
              "Idris", "Falk", "Sato", "Duarte", "Kessler"]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/145.0.0.0 Safari/537.36")

STEALTH_JS = """
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
window.chrome = window.chrome || {runtime:{}};
const gp = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p){
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return gp.apply(this, arguments);
};
const q = window.navigator.permissions && window.navigator.permissions.query;
if (q) window.navigator.permissions.query = (p) =>
    p && p.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : q(p);
"""


# ─────────────────────────── logging ──────────────────────────

def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with REGISTER_LOG.open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _p(msg: str, log=None) -> None:
    _log(msg)
    (log or print)(msg, flush=True)


# ─────────────────────────── mailbox ──────────────────────────

@dataclass
class Mailbox:
    address: str
    password: str = ""
    token: str = ""
    kind: str = "mailtm"          # mailtm | tmplol | mailnesia | inboxes | imap
    host: str = ""

    # ── mail.tm ──
    def refresh(self) -> None:
        r = requests.post("https://api.mail.tm/token",
                          json={"address": self.address, "password": self.password},
                          timeout=30)
        r.raise_for_status()
        self.token = r.json()["token"]

    def _mailtm(self) -> list[dict]:
        url = "https://api.mail.tm/messages"
        r = requests.get(url, headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        if r.status_code == 401:
            self.refresh()
            r = requests.get(url, headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        r.raise_for_status()
        j = r.json()
        return j.get("hydra:member", []) if isinstance(j, dict) else j

    def _mailtm_body(self, mid: str) -> str:
        r = requests.get(f"https://api.mail.tm/messages/{mid}",
                         headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        r.raise_for_status()
        d = r.json()
        return "\n".join(filter(None, [d.get("subject", ""), d.get("text", ""),
                                       d.get("html", "")]))

    # ── IMAP (real mailbox, plus-address) ──
    def _imap_conn(self):
        host = self.host or ("imap.gmail.com" if self.address.endswith("gmail.com")
                             else "outlook.office365.com")
        box = imaplib.IMAP4_SSL(host)
        box.login(self.address, self.password)
        box.select("INBOX")
        return box

    def _imap(self) -> list[dict]:
        box = self._imap_conn()
        try:
            typ, data = box.search(None, "ALL")
            out = []
            nums = (data[0].split()[-15:] if data and data[0] else [])[::-1]   # newest first
            for num in nums:
                out.append({"id": num.decode(), "subject": "", "idx": 0})
            return out
        finally:
            try:
                box.logout()
            except Exception:
                pass

    def _imap_body(self, mid: str) -> str:
        box = self._imap_conn()
        try:
            typ, data = box.fetch(mid.encode(), "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            parts = [msg.get("Subject", ""), msg.get("To", ""), msg.get("Date", "")]
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() in ("text/plain", "text/html"):
                        try:
                            parts.append(part.get_payload(decode=True).decode("utf-8", "ignore"))
                        except Exception:
                            pass
            else:
                try:
                    parts.append(msg.get_payload(decode=True).decode("utf-8", "ignore"))
                except Exception:
                    pass
            return "\n".join(parts)
        finally:
            try:
                box.logout()
            except Exception:
                pass

    # ── inboxes.com ──
    def _inboxes(self) -> list[dict]:
        r = requests.get(f"https://inboxes.com/api/v2/inbox/{self.address}?token={self.token}",
                         timeout=30)
        r.raise_for_status()
        out = []
        for i, m in enumerate(r.json().get("msgs", []) or []):
            out.append({"id": str(i), "subject": m.get("subject") or "", "idx": i})
        return out

    def _inboxes_body(self, mid: str) -> str:
        r = requests.get(f"https://inboxes.com/api/v2/inbox/{self.address}?token={self.token}",
                         timeout=30)
        r.raise_for_status()
        msgs = r.json().get("msgs", []) or []
        i = int(mid)
        if i >= len(msgs):
            return ""
        m = msgs[i]
        return "\n".join(filter(None, [m.get("subject", ""), m.get("body", ""),
                                       str(m.get("html", ""))]))

    # ── mailnesia (public inbox) ──
    def _mailnesia(self) -> list[dict]:
        local = self.address.split("@")[0]
        html = requests.get(f"https://mailnesia.com/mailbox/{local}", timeout=30).text
        out = []
        for m in re.finditer(r'href="https://mailnesia\.com/mail/([^"]+)"', html):
            out.append({"id": m.group(1), "subject": "", "idx": 0})
        return out

    def _mailnesia_body(self, mid: str) -> str:
        r = requests.get(f"https://mailnesia.com/mail/{mid}", timeout=30)
        return re.sub(r"<[^>]+>", " ", r.text)

    # ── tempmail.lol ──
    def _tmplol(self) -> list[dict]:
        r = requests.get(f"https://api.tempmail.lol/v2/inbox?token={self.token}", timeout=30)
        r.raise_for_status()
        out = []
        for i, m in enumerate(r.json().get("emails", [])):
            out.append({"id": m.get("id") or f"{i}:{(m.get('subject') or '')[:20]}",
                        "subject": m.get("subject") or "", "idx": i})
        return out

    def _tmplol_body(self, mid: str) -> str:
        r = requests.get(f"https://api.tempmail.lol/v2/inbox?token={self.token}", timeout=30)
        r.raise_for_status()
        emails = r.json().get("emails", [])
        idx = int(mid.split(":")[0])
        if idx >= len(emails):
            return ""
        d = emails[idx]
        return "\n".join(filter(None, [d.get("subject", ""), d.get("body", ""),
                                       d.get("html", "")]))

    def messages(self) -> list[dict]:
        if self.kind == "imap":
            return self._imap()
        if self.kind == "inboxes":
            return self._inboxes()
        if self.kind == "mailnesia":
            return self._mailnesia()
        return self._tmplol() if self.kind == "tmplol" else self._mailtm()

    def body(self, mid: str) -> str:
        if self.kind == "imap":
            return self._imap_body(mid)
        if self.kind == "inboxes":
            return self._inboxes_body(mid)
        if self.kind == "mailnesia":
            return self._mailnesia_body(mid)
        return self._tmplol_body(mid) if self.kind == "tmplol" else self._mailtm_body(mid)


def _create_mailtm() -> Mailbox:
    r = requests.get("https://api.mail.tm/domains", timeout=30)
    r.raise_for_status()
    j = r.json()
    rows = j.get("hydra:member", []) if isinstance(j, dict) else j
    doms = [d["domain"] for d in rows if d.get("isActive") and not d.get("isPrivate")]
    if not doms:
        raise RuntimeError("mail.tm: no active domain")
    user = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(13))
    pw = "Qx" + "".join(random.choice(string.ascii_letters + string.digits) for _ in range(14))
    r = requests.post("https://api.mail.tm/accounts",
                      json={"address": f"{user}@{doms[0]}", "password": pw}, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"mail.tm create {r.status_code}: {r.text[:160]}")
    mb = Mailbox(f"{user}@{doms[0]}", pw)
    mb.refresh()
    return mb


def _create_tmplol() -> Mailbox:
    r = requests.post("https://api.tempmail.lol/v2/inbox/create",
                      json={}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if not d.get("address") or not d.get("token"):
        raise RuntimeError(f"tempmail.lol: {d}")
    return Mailbox(d["address"], kind="tmplol", token=d["token"])


def _create_inboxes() -> Mailbox:
    r = requests.post("https://inboxes.com/api/v2/inbox", json={}, timeout=30)
    r.raise_for_status()
    addr = r.json().get("inbox") or ""
    if not addr:
        raise RuntimeError(f"inboxes.com: {r.text[:120]}")
    return Mailbox(r.json()["inbox"], kind="inboxes", token=r.json().get("token", ""))


def _create_mailnesia() -> Mailbox:
    local = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))
    return Mailbox(f"{local}@mailnesia.com", kind="mailnesia")


IMAP_ACCOUNT = os.environ.get("QREG_IMAP", "")   # user@gmail.com:app-password


def _create_imap() -> Mailbox:
    """Plus-addressed real mailbox: `user+qoderN@gmail.com`, same inbox."""
    if not IMAP_ACCOUNT or ":" not in IMAP_ACCOUNT:
        raise RuntimeError("set QREG_IMAP=user@host:app-password")
    addr, pw = IMAP_ACCOUNT.split(":", 1)
    pw = pw.replace(" ", "")          # Gmail shows app passwords in 4 spaced groups
    local, domain = addr.split("@", 1)
    tag = "q" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return Mailbox(f"{local}+{tag}@{domain}", pw, kind="imap")


def new_mailbox(provider: str = "inboxes") -> Mailbox:
    """Create a disposable inbox. provider: mailnesia | tmplol | mailtm | auto."""
    order = {"imap": [_create_imap, _create_inboxes],
             "inboxes": [_create_inboxes, _create_mailnesia, _create_mailtm],
             "mailnesia": [_create_mailnesia, _create_inboxes, _create_mailtm],
             "tmplol": [_create_tmplol, _create_mailtm],
             "mailtm": [_create_mailtm, _create_tmplol],
             "auto": [_create_mailnesia, _create_tmplol, _create_mailtm]}.get(
                 provider, [_create_mailnesia])
    last = None
    for factory in order:
        try:
            return factory()
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    raise RuntimeError(f"no mailbox provider worked: {last}")


_CODE_RE = re.compile(r"\b(\d{4,8})\b")
# Codes are shown with stray markup/spacing ("208 0 12"), so match digit groups
# that may be separated by spaces or hyphens and then join them.
_CODE_SPLIT_RE = re.compile(r"(?<!\d)(\d(?:[\s\u00a0\-]?\d){3,7})(?!\d)")


def wait_for_code(mb: Mailbox, timeout: int = MAIL_WAIT, log=None) -> str | None:
    t0 = time.time()
    seen: set[str] = set()
    warned = False
    while time.time() - t0 < timeout:
        try:
            for m in mb.messages():
                if m["id"] in seen:
                    continue
                seen.add(m["id"])
                txt = mb.body(m["id"])
                if not re.search(r"qoder", (m.get("subject", "") + txt).lower()):
                    continue
                # on a shared real inbox only the mail addressed to *this* tag counts
                if mb.kind == "imap" and mb.address and mb.address.lower() not in txt.lower():
                    continue
                flat = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", txt, flags=re.S)
                flat = re.sub(r"<[^>]+>", " ", flat)
                flat = re.sub(r"&nbsp;?", " ", flat)
                flat = re.sub(r"\s+", " ", flat)

                runs = [(m.group(0), re.sub(r"\D", "", m.group(0)), m.start())
                        for m in _CODE_SPLIT_RE.finditer(flat)]
                if not runs:
                    continue

                def score(item) -> float:
                    _, dig, pos = item
                    sc = 0.0
                    if len(dig) == 6:
                        sc += 4                       # Qoder codes are 6 digits
                    elif len(dig) in (4, 5, 7, 8):
                        sc += 1
                    before = flat[max(0, pos - 40):pos].lower()
                    after = flat[pos:pos + 40].lower()
                    if "code" in before or "code" in after:
                        sc += 5                       # next to the word "code"
                    if dig[:2] in ("19", "20") and len(dig) == 4:
                        sc -= 2                       # a bare year
                    if re.search(r"expire", after) or re.search(r"expire", before):
                        sc += 2
                    return sc - pos / 100000.0        # earlier wins ties

                six = [r for r in runs if len(r[1]) == 6]
                if six:
                    runs = six                       # Qoder codes are 6 digits
                runs.sort(key=score, reverse=True)
                if score(runs[0]) > 0:
                    return runs[0][1]
        except requests.HTTPError as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code == 429:
                ra = getattr(e.response, "headers", {}).get("Retry-After")
                wait = min(60, float(ra)) if (ra or "").isdigit() else 20.0
                _p(f"  [!] mail throttled, sleeping {wait:.0f}s", log)
                time.sleep(wait)
                continue
            if not warned:
                _p(f"  [!] mail poll: {e}", log)
                warned = True
        except requests.RequestException as e:
            if not warned:
                _p(f"  [!] mail poll: {e}", log)
                warned = True
        time.sleep(random.uniform(6.0, 8.5))
    return None


# ────────────────────── aliyun slider solver ──────────────────

def _b64_to_arr(data_url: str) -> np.ndarray | None:
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
        return np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
    except Exception:
        return None


def _gray_border_mask(rgba: np.ndarray) -> np.ndarray:
    """Pixels that look like the puzzle piece's grey outline (low sat, mid value)."""
    im = Image.fromarray(rgba[..., :3])
    hsv = np.array(im.convert("HSV")).astype(np.int16)
    S, V = hsv[..., 1], hsv[..., 2]
    return (S < 70) & (V > 80) & (V < 225)


def _gap_offset(bg: np.ndarray, pz: np.ndarray) -> int:
    """
    Distance (in natural bg pixels) the piece must travel.

    Aliyun ships the background WITH a puzzle-shaped hole plus the piece itself.
    Their pixel content differs, so match the hole GEOMETRY: the piece outline
    and the hole outline both raise image-gradient energy. Compare the left and
    right edge bands of the outline against the background's gradient field —
    a plateau of cloud/mountain never scores as high as a real cut edge.
    """
    alpha = pz[..., 3]
    ys, xs = np.where(alpha > 128)
    if len(xs) == 0:
        return 0
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    ph, pw = y1 - y0 + 1, x1 - x0 + 1
    if bg.shape[1] - pw < 1:
        return 0

    gray = np.array(Image.fromarray(bg[..., :3]).convert("L")).astype(np.float32)
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], np.float32)
    padded = np.pad(gray, 1, mode="edge")
    gx = (sliding_window_view(padded, (3, 3)) * kx).sum(axis=(2, 3))
    gy = (sliding_window_view(padded, (3, 3)) * kx.T).sum(axis=(2, 3))
    energy = np.hypot(gx, gy)
    energy /= energy.max() + 1e-6

    shape = alpha[y0:y1 + 1, x0:x1 + 1] > 128
    eroded = sliding_window_view(np.pad(shape, 1), (3, 3)).min(axis=(2, 3)) > 0
    ring = shape & ~eroded
    if ring.sum() == 0:
        ring = shape

    # ── primary: overlap the piece outline with the hole outline in the bg,
    #            weighted by local gradient energy (cut edges are sharp) ──
    pb = _gray_border_mask(pz)[y0:y1 + 1, x0:x1 + 1]
    if pb.sum() >= 40:
        bb = _gray_border_mask(bg)
        energy = np.hypot(gx, gy)
        energy = energy / (energy.max() + 1e-6)
        best_x, best = x0, -1.0
        for x in range(0, bg.shape[1] - pw + 1):
            win_b = bb[y0:y0 + ph, x:x + pw]
            if win_b.shape != pb.shape:
                continue
            overlap = win_b & pb
            if not overlap.any():
                continue
            win_e = energy[y0:y0 + ph, x:x + pw]
            score = float(overlap.sum()) + 3.0 * float((overlap * win_e).sum())
            if score > best:
                best, best_x = score, x
        if best > 0:
            return max(0, best_x - x0)

    # ── fallback: strongest left+right edge bands under the outline ──
    band = max(2, pw // 12)
    scores = []
    for x in range(0, bg.shape[1] - pw + 1):
        win = energy[y0:y0 + ph, x:x + pw]
        left = win[:, :band][ring[:, :band]]
        right = win[:, pw - band:][ring[:, pw - band:]]
        if not len(left) or not len(right):
            continue
        scores.append(((float(left.mean()) + float(right.mean())) / 2.0, x))
    if scores:
        scores.sort(reverse=True)
        if scores[0][0] > 1e-4:
            return max(0, scores[0][1] - x0)
    return 0


_CAP_STATE_JS = """() => {
    const sl = document.querySelector('#aliyunCaptcha-sliding-body');
    const win = document.querySelector('#aliyunCaptcha-window-float');
    const box = document.querySelector('#aliyunCaptcha-img-box');
    const txt = document.querySelector('#aliyunCaptcha-captcha-text');
    const cap = document.querySelector('#captcha-element');
    const floatVisible = !!(win && win.offsetParent !== null);
    return {
        slider: !!sl && sl.offsetParent !== null,
        winFloat: floatVisible,
        imgBox: !!box && box.offsetParent !== null,
        text: txt ? txt.innerText : '',
        captchaEl: !!cap,
        path: location.pathname,
    };
}"""


def solve_aliyun_slider(page: Page, attempts: int = 6, log=None,
                        seen_requests: list | None = None) -> bool:
    """Drag the Aliyun slider handle onto the puzzle gap — closed loop.

    The piece's on-screen left edge is read back on every move, so no
    ratio/scale assumption is needed: keep nudging the handle until the piece
    sits on the detected hole, then release.
    """
    def passed() -> bool:
        if seen_requests and any("/api/v1/verificationCodes" in u for u in seen_requests):
            return True
        st = page.evaluate(_CAP_STATE_JS)
        return (not st["captchaEl"]) or ("/users/sign-up" not in st["path"])

    def piece_left() -> float | None:
        return page.evaluate(
            "() => { const e = document.querySelector('#aliyunCaptcha-puzzle');"
            " return e ? e.getBoundingClientRect().x : null; }")

    def _images_ready() -> dict | None:
        g = page.evaluate("""() => {
            const i = document.querySelector('#aliyunCaptcha-img'),
                  p = document.querySelector('#aliyunCaptcha-puzzle');
            return i && p ? {bg: i.src, pz: p.src} : null;
        }""")
        if g and _b64_to_arr(g["bg"]) is not None and _b64_to_arr(g["pz"]) is not None:
            return g
        return None

    def reload_puzzle() -> bool:
        """
        Fetch a fresh challenge.

        Aliyun does not expose a stable refresh hook, so try, in order: the
        refresh icon in the image's top-right corner, the error overlay, then
        close the window and re-open it from the 'Click to verify' bar.
        """
        for _ in range(5):
            box = page.evaluate("""() => {
                const e = document.querySelector('#aliyunCaptcha-img-box');
                if (!e) return null;
                const r = e.getBoundingClientRect();
                return {x: r.right - 16, y: r.top + 16};
            }""")
            if box:
                page.mouse.click(box["x"], box["y"])
                time.sleep(0.9)
            if _images_ready():
                return True
            if box:
                page.mouse.click(box["x"], box["y"])
                time.sleep(1.2)
                continue

            # window gone: re-open from the verify bar
            body = page.query_selector("#aliyunCaptcha-captcha-body")
            if body:
                try:
                    body.click(timeout=1500)
                except Exception:
                    pass
                time.sleep(1.5)
                if _images_ready():
                    return True
            time.sleep(0.6)
        return False

    reload_fails = 0
    for n in range(1, attempts + 1):
        try:
            page.wait_for_selector("#aliyunCaptcha-sliding-slider", timeout=STEP_TIMEOUT)
        except PWTimeout:
            if passed():
                return True
            _p("  [!] slider element never showed up", log)
            return False
        time.sleep(random.uniform(0.4, 0.9))

        geo = page.evaluate("""() => {
            const q = s => document.querySelector(s);
            const r = e => { const b = e.getBoundingClientRect();
                return {x:b.x, y:b.y, w:b.width, h:b.height}; };
            const img = q('#aliyunCaptcha-img'), pz = q('#aliyunCaptcha-puzzle'),
                  sl = q('#aliyunCaptcha-sliding-slider');
            if (!img || !pz || !sl) return null;
            return {bg: img.src, pz: pz.src, bgBox: r(img), pzBox: r(pz),
                    slBox: r(sl), natW: img.naturalWidth || img.width};
        }""")
        if not geo:
            _p("  [!] captcha nodes missing", log)
            return False

        bg_arr, pz_arr = _b64_to_arr(geo["bg"]), _b64_to_arr(geo["pz"])
        if bg_arr is None or pz_arr is None:
            reload_fails += 1
            _p(f"  [!] captcha images not ready, reloading ({reload_fails})", log)
            if reload_fails > 2 or not reload_puzzle():
                _p("  [!] puzzle will not refresh — giving up on this attempt", log)
                return False
            continue

        off_img = _gap_offset(bg_arr, pz_arr)
        scale = geo["bgBox"]["w"] / max(1, geo["natW"])
        target_left = geo["bgBox"]["x"] + off_img * scale
        _p(f"  [*] captcha {n}/{attempts}: hole={off_img}px nat -> piece target x={target_left:.1f}", log)

        if os.environ.get("QREG_DEBUG"):
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                stamp = f"cap_{int(time.time()*1000)}_{n}"
                Image.fromarray(bg_arr[..., :3]).save(DEBUG_DIR / f"{stamp}_bg.png")
                Image.fromarray(pz_arr).save(DEBUG_DIR / f"{stamp}_pz.png")
                marked = np.array(Image.fromarray(bg_arr[..., :3]).convert("RGB"))
                for xx in (off_img, min(off_img + 52, marked.shape[1] - 1)):
                    marked[:, max(0, xx - 1):xx + 1] = [255, 0, 0]
                Image.fromarray(marked).save(DEBUG_DIR / f"{stamp}_mark.png")
            except Exception:
                pass

        sl = geo["slBox"]
        sx, sy = sl["x"] + sl["w"] / 2, sl["y"] + sl["h"] / 2
        handle_x = sx

        page.mouse.move(sx, sy)
        time.sleep(random.uniform(0.12, 0.28))
        page.mouse.down()

        cur = piece_left() or 0.0
        grabbed = False
        for _ in range(90):                      # closed-loop approach
            delta = target_left - cur
            if not grabbed and abs(delta) > 1.0:
                grabbed = True                   # piece starts following the handle
            if abs(delta) <= 1.2:
                break
            if not grabbed:
                cur = piece_left() or cur
                if abs(cur - (target_left)) <= 1.2:
                    break
            step = max(-18.0, min(18.0, delta * random.uniform(0.55, 0.95)))
            if abs(step) < 0.6:
                step = 0.6 if delta > 0 else -0.6
            handle_x += step
            page.mouse.move(handle_x + random.uniform(-0.4, 0.4),
                            sy + random.uniform(-0.6, 0.6))
            time.sleep(random.uniform(0.012, 0.030))
            new = piece_left()
            if new is not None:
                if abs(new - cur) < 0.05 and abs(delta) > 3:   # handle is stuck
                    break
                cur = new

        page.mouse.move(handle_x + random.uniform(1.0, 3.0), sy, steps=2)
        time.sleep(random.uniform(0.08, 0.18))
        page.mouse.move(handle_x, sy, steps=2)
        time.sleep(random.uniform(0.15, 0.30))
        if os.environ.get("QREG_DEBUG"):
            try:
                page.screenshot(path=str(DEBUG_DIR / f"pre_release_{n}.png"))
            except Exception:
                pass
        page.mouse.up()
        _p(f"    final piece x={cur:.1f} (target {target_left:.1f})", log)

        deadline = time.time() + 10
        while time.time() < deadline:
            if passed():
                _p("  [*] captcha cleared", log)
                return True
            time.sleep(0.3)

        st = page.evaluate(_CAP_STATE_JS)
        _p(f"  [!] captcha rejected ({st.get('text', '')!r}), next attempt", log)
        if not reload_puzzle():
            _p("  [!] could not get a fresh puzzle — stopping", log)
            return False
        reload_fails = 0
    return False


# ─────────────────────────── register ─────────────────────────

@dataclass
class RegisterResult:
    email: str = ""
    password: str = ""
    ok: bool = False
    stage: str = ""
    detail: str = ""
    plan: str | None = None
    credits: int | None = None
    user_id: str | None = None
    started: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict:
        return dict(self.__dict__)

    def line(self) -> str:
        return (f"{self.email}|{self.password}|plan={self.plan}|credits={self.credits}"
                f"|{self.started}")


def _shot(page: Page, tag: str) -> None:
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DEBUG_DIR / f"{tag}.png"), full_page=True)
    except Exception:
        pass


def _save(res: RegisterResult) -> None:
    try:
        with (REGISTERED_FILE if res.ok else REGISTER_FAILED_FILE).open("a") as f:
            f.write((res.line() if res.ok else f"{res.email}|{res.stage}|{res.detail}|{res.started}") + "\n")
    except OSError:
        pass


def _fill_code(page: Page, code: str) -> bool:
    """Type the OTP into whatever input shape Qoder shows."""
    # 1) one-char boxes: focus the first and type, letting the widget advance
    boxes = page.query_selector_all("input[maxlength='1']")
    if boxes:
        boxes[0].click()
        page.keyboard.type(code, delay=random.uniform(40, 90))
        typed = "".join((b.input_value() or "") for b in boxes)
        if len(typed) >= min(4, len(code)):
            return True
        for box, ch in zip(boxes, code):        # fallback: fill one by one
            try:
                box.fill(ch)
            except Exception:
                pass
        return True
    # 2) a single dedicated code field
    for sel in ("input[autocomplete='one-time-code']", "input#code", "input[name='code']",
                "input[placeholder*='code' i]", "input[aria-label*='code' i]"):
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.fill(code)
            return True
    # 3) last resort: the only visible text input that is not email/password
    for el in page.query_selector_all("input[type='text'],input[type='tel'],input[inputmode='numeric']"):
        if el.is_visible() and el not in page.query_selector_all("#basic_email,#basic_firstName,#basic_lastName"):
            el.fill(code)
            return True
    return False


def _gen_password() -> str:
    """Qoder requires >8 chars with upper, lower, digit and special."""
    import random as _r
    pools = [string.ascii_uppercase, string.ascii_lowercase,
             string.digits, "!@#$%^&*"]
    chars = [_r.choice(p) for p in pools] + \
            [_r.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(10)]
    _r.shuffle(chars)
    return "".join(chars)


def register_one(browser, referral_code: str = DEFAULT_REFERRAL_CODE,
                 keep_open: bool = False, log=None,
                 mail_provider: str = MAIL_PROVIDER) -> RegisterResult:
    """Register a single Qoder account through the invite path."""
    res = RegisterResult()
    mb = new_mailbox(mail_provider)
    res.email, res.password = mb.address, _gen_password()
    full = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    _p(f"[*] mailbox {mb.address}", log)

    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, user_agent=UA,
                              locale="en-US", timezone_id="Asia/Singapore")
    ctx.add_init_script(STEALTH_JS)
    page = ctx.new_page()
    page.set_default_timeout(STEP_TIMEOUT)
    page.set_default_navigation_timeout(NAV_TIMEOUT)

    seen: list[str] = []
    page.on("request", lambda r: seen.append(r.url))

    api_trace: dict[str, tuple[int, str]] = {}

    net_log: list[str] = []

    def _on_request(req) -> None:
        if "qoder.com/api" in req.url and req.method == "POST":
            try:
                data = (req.post_data or "")[:300]
            except Exception:
                data = ""
            net_log.append(f"REQ {req.method} {req.url.split('?')[0]} body={data}")

    def _on_response(resp) -> None:
        url = resp.url.split("?")[0]
        if "qoder.com/api" not in url and "qoder.sh/api" not in url:
            return
        try:
            body = resp.text()[:300]
        except Exception:
            body = ""
        net_log.append(f"{resp.request.method} {url} -> {resp.status} {body[:180]}")
        if "/verificationCodes" in url or "/api/v1/users" in url:
            api_trace[url] = (resp.status, body)

    page.on("request", _on_request)
    page.on("response", _on_response)

    try:
        page.goto(f"{SIGNUP_URL}?referral_code={referral_code}", wait_until="domcontentloaded")
        page.wait_for_selector("#basic_firstName", timeout=STEP_TIMEOUT)

        # ── step 1: name + email + terms
        page.fill("#basic_firstName", full.split()[0])
        page.fill("#basic_lastName", full.split()[1])
        page.fill("#basic_email", res.email)
        page.click(".ant-checkbox-input")
        continue_btn = page.get_by_role("button", name=re.compile("Continue", re.I))

        # ── step 2: password (email is carried by the form)
        got_password = False
        for _ in range(3):
            continue_btn.click()
            try:
                page.wait_for_selector("#basic_password", state="visible", timeout=8000)
                got_password = True
                break
            except PWTimeout:
                body = page.inner_text("body")
                if re.search(r"valid email|already (exist|registered|in use)", body, re.I):
                    res.stage, res.detail = "signup", body.strip()[:140]
                    _shot(page, "fail_step1")
                    return res
                time.sleep(1.0)
        if not got_password:
            body = page.inner_text("body")
            res.stage, res.detail = "step1", f"password step missing: {body[:120]}"
            _shot(page, "fail_step1")
            return res

        page.fill("#basic_password", res.password)
        page.get_by_role("button", name=re.compile("Continue", re.I)).click()
        time.sleep(2.5)

        body = page.inner_text("body")
        if re.search(r"already (exist|registered|in use)", body, re.I):
            res.stage, res.detail = "signup", "email already registered"
            return res
        if re.search(r"password must", body, re.I):
            res.stage, res.detail = "signup", f"password rejected: {body[:140]}"
            return res

        # ── step 3: captcha
        try:
            page.wait_for_selector("#captcha-element", timeout=20_000)
        except PWTimeout:
            res.stage, res.detail = "captcha", "captcha never rendered"
            _shot(page, "fail_captcha_missing")
            return res
        try:
            page.click("#aliyunCaptcha-captcha-body", timeout=4000)
        except Exception:
            pass
        if not solve_aliyun_slider(page, log=log, seen_requests=seen):
            res.stage, res.detail = "captcha", "slider not solved"
            _shot(page, "fail_captcha")
            return res

        # ── step 4: e-mail code
        for line in net_log[-8:]:
            _p(f"  [net] {line}", log)
        if not api_trace:
            _p("  [!] no verificationCodes/users call yet — clicking the submit button", log)
            for label in ("Continue", "Sign up", "Create account", "Verify", "Next"):
                try:
                    page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=2500)
                except Exception:
                    continue
                time.sleep(2.5)
                if api_trace:
                    break
            for u, (st, b) in api_trace.items():
                _p(f"  [api] {u} -> {st} {b[:180]}", log)
        if not api_trace:
            _p("  [!] still nothing — dumping page text", log)
            _p("  [body] " + page.inner_text("body")[:300].replace("\n", " | "), log)
        code = wait_for_code(mb, log=log)
        if not code:
            res.stage, res.detail = "mail", "no code in inbox"
            _shot(page, "fail_mail")
            return res
        _p(f"  [*] email code {code}", log)

        deadline = time.time() + 25
        while time.time() < deadline:
            if page.query_selector("input[maxlength='1'], input[autocomplete='one-time-code'], input#code"):
                break
            time.sleep(0.5)
        if not _fill_code(page, code):
            res.stage, res.detail = "mail", "code input not found"
            _shot(page, "fail_code_input")
            return res

        for label in ("Verify", "Confirm", "Continue", "Sign up", "Create", "Submit", "Done"):
            try:
                page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=2500)
                break
            except Exception:
                continue
        time.sleep(5)

        # ── verify with an authenticated API call
        # The create call (POST /api/v1/users) sets the session cookie, but the
        # page only navigates after the OTP is accepted — reload once first.
        time.sleep(4)
        try:
            page.goto(HOME_URL, wait_until="domcontentloaded")
            time.sleep(2)
        except Exception:
            pass
        r = ctx.request.get(ME_API, headers={"Accept": "application/json"})
        if r.ok:
            j = r.json()
            res.ok = True
            res.stage = "done"
            res.user_id = str(j.get("id") or j.get("userId") or "")
            res.plan = (j.get("userPlan") or {}).get("name") or j.get("plan")
            res.credits = j.get("bigModelCredits") or j.get("credits")
            res.detail = "registered, session active"
        else:
            res.stage, res.detail = "verify", f"registered but /me -> {r.status}"
            res.ok = r.status == 200
        _shot(page, f"done_{res.email.split('@')[0]}")

    except Exception as e:  # noqa: BLE001
        res.stage, res.detail = "exception", f"{type(e).__name__}: {e}"
        _shot(page, "fail_exception")
    finally:
        if keep_open and not getattr(browser, "_net_stinger_headed", False):
            pass
        ctx.close()
        _save(res)
    return res


# ─────────────────────────── driver ───────────────────────────

def auto_register(count: int = 1, referral_code: str = DEFAULT_REFERRAL_CODE,
                  headless: bool = True, delay: float = 10.0, proxy: str | None = None,
                  keep_open: bool = False, log=None,
                  mail_provider: str = MAIL_PROVIDER,
                  retries: int = 3) -> list[RegisterResult]:
    """Register `count` accounts. Returns one RegisterResult per attempt."""
    from playwright.sync_api import sync_playwright

    results: list[RegisterResult] = []
    proxy_cfg = {"server": proxy} if proxy else None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless, proxy=proxy_cfg,
            channel=None if not headless else "chromium",   # full build, new headless
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for i in range(1, count + 1):
                r = None
                for attempt in range(1, retries + 1):
                    _p(f"\n=== [{i}/{count}] attempt {attempt}/{retries} "
                       f"referral_code={referral_code} ===", log)
                    r = register_one(browser, referral_code, keep_open=keep_open,
                                     log=log, mail_provider=mail_provider)
                    _p(f"[{'OK ' if r.ok else 'FAIL'}] {r.email} stage={r.stage} "
                       f"plan={r.plan} credits={r.credits} :: {r.detail}", log)
                    if r.ok:
                        break
                    # a stale/failed attempt leaves nothing useful behind
                    time.sleep(random.uniform(3, 7))
                results.append(r)
                if i < count:
                    time.sleep(delay + random.uniform(0, 6))
            if keep_open and not headless:
                _p("  [*] browser kept open — Ctrl+C to stop", log)
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
        finally:
            browser.close()
    return results


def register_menu(input_fn=input, print_fn=print) -> None:
    """Interactive entry used by main.py."""
    code = input_fn(f"  Referral code [{DEFAULT_REFERRAL_CODE[:18]}...]: ").strip() \
        or DEFAULT_REFERRAL_CODE
    raw = input_fn("  Jumlah akun [1]: ").strip() or "1"
    try:
        count = max(1, int(raw))
    except ValueError:
        count = 1
    headed = input_fn("  Tampilkan browser? (y/n) [n]: ").strip().lower() == "y"
    proxy = input_fn("  Proxy (kosongkan jika tidak ada): ").strip() or None

    print_fn(f"\n  [*] register {count} akun, code={code}, headless={not headed}")
    res = auto_register(count=count, referral_code=code, headless=not headed,
                        proxy=proxy, log=print_fn)
    okc = sum(1 for r in res if r.ok)
    print_fn(f"\n  {'✅' if okc else '❌'} {okc}/{count} sukses")
    for r in res:
        print_fn(f"   {'✅' if r.ok else '❌'} {r.email} — {r.stage}: {r.detail}")
    if okc:
        print_fn(f"  📄 hasil -> {REGISTERED_FILE.name}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Qoder auto-register via invite path")
    ap.add_argument("--code", default=DEFAULT_REFERRAL_CODE)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--keep-open", action="store_true")
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--delay", type=float, default=10.0)
    ap.add_argument("--mail", default=MAIL_PROVIDER,
                    choices=["imap", "inboxes", "mailnesia", "tmplol", "mailtm"],
                    help="mailbox provider")
    ap.add_argument("--retries", type=int, default=3,
                    help="attempts per account (captcha is ~70%%)")
    a = ap.parse_args()

    rs = auto_register(count=a.count, referral_code=a.code, headless=not a.headed,
                       delay=a.delay, proxy=a.proxy, keep_open=a.keep_open,
                       mail_provider=a.mail, retries=a.retries)
    print(json.dumps([r.as_dict() for r in rs], indent=2))
