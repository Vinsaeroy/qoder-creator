#!/usr/bin/env python3
"""
Does logging into the Qoder CLI/IDE grant the Pro Trial?

The repo's original premise is "log in on the desktop and the trial lands".
This drives the real device flow end to end for a *known Free* account and
measures the plan before/after:

  1. `qodercli login`            -> device URL (5 min TTL, nonce + machine_token)
  2. playwright opens that URL, signs in with email + password, approves
  3. `qodercli status` / `-p`    -> a real turn with a genuine machine identity
  4. plan via the web session    -> PLAN_TIER_* before and after

Usage (needs a display: xvfb-run -a …):
    python qoder_cli_login_test.py --email a+b@gmail.com --password '…'
    python qoder_cli_login_test.py --email … --password … --keep-browser
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import qoder_trial_probe as TP  # noqa: E402

CLI = Path("/home/ubuntu/qoder-cli/qodercli")
RESULT = Path(__file__).parent / "qoder_cli_login_test.json"


def _plan_via_web(email: str, password: str, log=print) -> dict:
    out = {"tier": None, "raw": None, "login": None}
    try:
        o = TP.web_plan(email, password, log=log)
        out["login"] = o.get("login")
        plan = o.get("plan")
        out["raw"] = plan
        if isinstance(plan, dict):
            out["tier"] = plan.get("plan_tier_name") or plan.get("plan_tier")
    except Exception as e:  # noqa: BLE001
        out["login"] = f"error: {e}"
    return out


def approve_device(url: str, email: str, password: str, keep: bool, log=print) -> str:
    """Sign in at the device URL and approve the CLI."""
    from playwright.sync_api import sync_playwright

    state = "unknown"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False,
                                     args=["--disable-blink-features=AutomationControlled",
                                           "--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(3)

            # sign in if asked (two-step: email then password)
            if page.query_selector("#basic_email"):
                page.fill("#basic_email", email)
                page.get_by_role("button", name=re.compile("Continue", re.I)).first.click()
                time.sleep(2.5)
                try:
                    page.wait_for_selector("#password_password, #basic_password",
                                           state="visible", timeout=15_000)
                except Exception:
                    pass
                pwd = page.query_selector("#password_password") or \
                    page.query_selector("#basic_password")
                if pwd:
                    pwd.click()
                    pwd.fill(password)
                    for attempt in range(1, 4):
                        for label in ("Sign in", "Continue", "Log in"):
                            try:
                                page.get_by_role("button", name=re.compile(f"^{label}$", re.I)) \
                                    .first.click(timeout=4000)
                                break
                            except Exception:
                                continue
                        time.sleep(2.5)
                        if page.query_selector("#captcha-element"):
                            log("  [browser] captcha on sign-in — solving")
                            TP._solve_captcha_if_present(page, log=log)
                            time.sleep(2)
                            continue
                        if not page.query_selector("#password_password"):
                            break
                    time.sleep(4)

            TP._solve_captcha_if_present(page, log=log)
            log(f"  [browser] after sign-in: {page.url}")
            log(f"  [browser] text: {page.inner_text('body')[:200].replace(chr(10), ' | ')}")

            # approve: the page may need an explicit confirmation
            for label in ("Authorize", "Confirm", "Continue", "Allow", "Agree", "Grant",
                          "Sign in", "Select"):
                try:
                    page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=2000)
                    log(f"  [browser] clicked {label!r}")
                    time.sleep(2.5)
                    break
                except Exception:
                    continue
            time.sleep(3)
            log(f"  [browser] final: {page.url} | {page.inner_text('body')[:160].replace(chr(10), ' | ')}")
            state = "approved"
            if keep:
                log("  [browser] kept open — Ctrl+C to stop")
                while True:
                    time.sleep(1)
        except Exception as e:  # noqa: BLE001
            state = f"error: {e}"
        finally:
            if not keep:
                browser.close()
    return state


def run(email: str, password: str, keep: bool = False, log=print) -> dict:
    out: dict = {"email": email, "started": datetime.now(timezone.utc).isoformat()}
    out["plan_before"] = _plan_via_web(email, password, log=log)
    log(f"[cli-test] plan before: {out['plan_before'].get('tier')}")

    # 1. start the device flow
    proc = subprocess.Popen([str(CLI), "login"], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    url = None
    t0 = time.time()
    buf = ""
    while time.time() - t0 < 40:
        line = proc.stdout.readline()
        if not line:
            break
        buf += line
        m = re.search(r"https://qoder\.com/device/[^\s]+", line)
        if m:
            url = m.group(0)
            break
    if not url:
        out["error"] = f"no device URL in: {buf[:300]}"
        proc.kill()
        log(f"[cli-test] {out['error']}")
        return out
    out["device_url"] = url
    log(f"[cli-test] device URL acquired (TTL 5 min)")

    # 2. approve in a browser
    out["browser"] = approve_device(url, email, password, keep, log=log)

    # 3. wait for the CLI
    try:
        rest = proc.communicate(timeout=90)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        rest = "(timed out)"
    out["cli_login"] = (buf + (rest or ""))[-400:]
    log(f"[cli-test] cli login: {out['cli_login'][-160:].strip()}")

    # 4. a real turn
    for cmd in (["status"], ["-p", "reply with exactly: ok"]):
        try:
            r = subprocess.run([str(CLI)] + cmd, capture_output=True, text=True, timeout=180)
            out.setdefault("cli_runs", []).append(
                {"cmd": cmd, "rc": r.returncode,
                 "out": (r.stdout + r.stderr)[:400]})
            log(f"[cli-test] cli {' '.join(cmd)} -> {r.returncode} "
                f"{(r.stdout + r.stderr)[:120].strip()}")
        except Exception as e:  # noqa: BLE001
            out.setdefault("cli_runs", []).append({"cmd": cmd, "rc": -1, "out": str(e)})

    # 5. plan after
    out["plan_after"] = _plan_via_web(email, password, log=log)
    log(f"[cli-test] plan after: {out['plan_after'].get('tier')}")
    before, after = out["plan_before"].get("tier"), out["plan_after"].get("tier")
    if before and after and before != after and "TRIAL" in str(after).upper():
        out["verdict"] = "FLIPPED-to-pro-trial"
    elif after and "TRIAL" in str(after).upper():
        out["verdict"] = "already-pro-trial"
    else:
        out["verdict"] = "no-change"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--keep-browser", action="store_true")
    a = ap.parse_args()
    res = run(a.email, a.password, keep=a.keep_browser)
    RESULT.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "plan_before"}, indent=2)[:1200])
    print(f"\nverdict: {res.get('verdict')}  (detail -> {RESULT.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
