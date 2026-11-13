#!/usr/bin/env python3
"""
Qoder Pro Trial / activity claim via an account path (PAT, `pt-…`).

The desktop "claim" surface Qoder never documented: the client exchanges the
account's PAT for a job-token identity, then walks the activity-claim family.

Endpoints (intl realm):

    POST {center}/algo/api/v3/user/jobToken?Encode=1   PAT -> identity
    GET  {openapi}/algo/api/v2/service/region/endpoints
    GET  {api2}/algo/api/v2/activity                   activity list
    GET  {openapi}/api/v2/activity/claim/eligibility   what is claimable
    POST {openapi}/api/v2/activity/claim?activityId=…  claim it
    GET  {openapi}/sash/api/v1/me/campaigns            daily-credit campaigns
    GET  {openapi}/api/v2/activity/quota/reset/latest  quota window

Signing (COSY):
    key        = 16 random chars, used as both AES-128-CBC key and IV
    info       = base64(AES-CBC(sorted-compact(identity JSON)))
    cosyKey    = base64(RSA-PKCS1v15(key))
    payload    = base64(sorted-compact({version:"v1", requestId, info,
                                        cosyVersion, ideVersion:""}))
    signature  = md5(payload \\n cosyKey \\n date \\n body \\n sigPath)
    Authorization: Bearer COSY.<payload>.<signature>
    sigPath    = URL path with a leading "/algo" stripped

Request bodies are alphabet-scrambled then base64-rotated (`transform_body`).

Usage:
    python qoder_claim.py --path pt-xxxxxxxx
    python qoder_claim.py --path pt-… --realm cn
    python qoder_claim.py --path pt-… --claim        # actually POST the claim
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import string
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"[claim] missing dependency: {e}\n"
                     f"  pip install requests cryptography")

# ─────────────────────────── constants ────────────────────────

QODER_STANDARD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
QODER_ALPHABET = "_doRTgHZBKcGVjlvpC,@aFSx#DPuNJme&i*MzLOEn)sUrthbf%Y^w.(kIQyXqWA!"

QODER_RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDA8iMH5c02LilrsERw9t6Pv5Nc
4k6Pz1EaDicBMpdpxKduSZu5OANqUq8er4GM95omAGIOPOh+Nx0spthYA2BqGz+l
6HRkPJ7S236FZz73In/KVuLnwI8JJ2CbuJap8kvheCCZpmAWpb/cPx/3Vr/J6I17
XcW+ML9FoCI6AOvOzwIDAQAB
-----END PUBLIC KEY-----"""

QODER_APPCODE = "cosy"
QODER_SIG_SECRET = "d2FyLCB3YXIgbmV2ZXIgY2hhbmdlcw=="
QODER_VERSION = os.environ.get("QODER_VERSION", "1.1.64")
QODER_MACHINE_OS = os.environ.get("QODER_MACHINE_OS", "aarch64_macos")

REALMS = {
    "intl": {
        "center": "https://center.qoder.sh",
        "openapi": "https://center.qoder.sh",
        "infer": "https://api2.qoder.sh",
        "website": "https://qoder.com",
    },
    "cn": {
        "center": "https://center.qoder.com.cn",
        "openapi": "https://center.qoder.com.cn",
        "infer": "https://api2.qoder.com.cn",
        "website": "https://qoder.com.cn",
    },
}

BASE_DIR = Path(__file__).parent
CLAIM_LOG = BASE_DIR / "qoder_claim_log.txt"
CLAIM_RESULT = BASE_DIR / "qoder_claim_result.json"

TIMEOUT = 25


def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with CLAIM_LOG.open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ─────────────────────────── crypto ───────────────────────────

def md5_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("latin-1")
    return hashlib.md5(data).hexdigest()


def sorted_compact(mapping: dict) -> str:
    """COSY canonical JSON: keys sorted, no whitespace, None -> ""."""
    parts = []
    for k in sorted(mapping):
        v = mapping[k]
        if v is None:
            v = ""
        parts.append(f"{json.dumps(k, separators=(',', ':'))}:{json.dumps(v, separators=(',', ':'))}")
    return "{" + ",".join(parts) + "}"


def transform_body(plaintext: str) -> bytes:
    """Qoder's base64 alphabet scramble + third-rotation."""
    b64 = base64.b64encode(plaintext.encode()).decode()
    third = len(b64) // 3
    if third:
        reordered = b64[-third:] + b64[third:len(b64) - third] + b64[:third]
    else:
        reordered = b64
    out = []
    for ch in reordered:
        if ch == "=":
            out.append("$")
        else:
            idx = QODER_STANDARD_ALPHABET.find(ch)
            out.append(QODER_ALPHABET[idx] if idx >= 0 else ch)
    return "".join(out).encode("latin-1")


def _public_key():
    return serialization.load_pem_public_key(QODER_RSA_PUBLIC_KEY.encode())


def _rsa_encrypt_b64(key: bytes) -> str:
    enc = _public_key().encrypt(key, asym_padding.PKCS1v15())
    return base64.b64encode(enc).decode()


def _aes_cbc_b64(key: bytes, data: bytes) -> str:
    """AES-128-CBC with PKCS#7 padding (Node's createCipheriv pads by default)."""
    pad = 16 - (len(data) % 16)
    data = data + bytes([pad]) * pad
    cipher = Cipher(algorithms.AES(key), modes.CBC(key))
    enc = cipher.encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode()


def _sig_path(url: str) -> str:
    path = urlparse(url).path
    return path[5:] if path.startswith("/algo") else path


# ─────────────────────────── identity ─────────────────────────

@dataclass
class QoderAuth:
    user_id: str = ""
    user_name: str = ""
    user_type: str = "personal_standard"
    security_oauth_token: str = ""
    refresh_token: str = ""
    machine_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def is_pat(secret: str) -> bool:
    return secret.startswith("pt-")


def static_headers(machine_id: str, version: str = QODER_VERSION) -> dict[str, str]:
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {
        "cosy-machinetoken": machine_id,
        "cosy-machinetype": "5",
        "cosy-machineid": machine_id,
        "cosy-clienttype": "5",
        "cosy-version": version,
        "login-version": "v2",
        "appcode": QODER_APPCODE,
        "accept": "application/json",
        "accept-encoding": "identity",
        "date": date,
        "signature": md5_hex(f"{QODER_APPCODE}&{QODER_SIG_SECRET}&{date}"),
        "content-type": "application/json",
        "user-agent": "Go-http-client/2.0",
    }


def cosy_headers(auth: QoderAuth, url: str, body: str = "",
                 version: str = QODER_VERSION) -> dict[str, str]:
    key = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(16)).encode()
    identity = sorted_compact({
        "name": auth.user_name,
        "aid": auth.user_id,
        "uid": auth.user_id,
        "yx_uid": "",
        "organization_id": "",
        "organization_name": "",
        "user_type": auth.user_type,
        "security_oauth_token": auth.security_oauth_token,
        "refresh_token": auth.refresh_token,
    })
    info = _aes_cbc_b64(key, identity.encode())
    cosy_key = _rsa_encrypt_b64(key)
    payload = base64.b64encode(sorted_compact({
        "version": "v1",
        "requestId": str(uuid.uuid4()),
        "info": info,
        "cosyVersion": version,
        "ideVersion": "",
    }).encode()).decode()
    date = str(int(time.time()))
    body_bytes = body.encode("latin-1") if body else b""
    signature = md5_hex(
        f"{payload}\n{cosy_key}\n{date}\n{body_bytes.decode('latin-1')}\n{_sig_path(url)}")
    now_utc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {
        "authorization": f"Bearer COSY.{payload}.{signature}",
        "cosy-data-policy": "agree",
        "cosy-machinetype": "5",
        "cosy-machineos": QODER_MACHINE_OS,
        "cosy-clienttype": "5",
        "cosy-date": date,
        "cosy-user": auth.user_id,
        "cosy-key": cosy_key,
        "cosy-bodyhash": md5_hex(body_bytes),
        "cosy-bodylength": str(len(body_bytes)),
        "cosy-sigpath": _sig_path(url),
        "cosy-organization-id": "",
        "cosy-organization-tags": "",
        "x-request-id": str(uuid.uuid4()),
        "cosy-business-product": "cli",
        "cosy-business-type": "agent",
        "cosy-business-version": version,
        "cosy-scene": "assistant",
        "cosy-version": version,
        "login-version": "v2",
        "appcode": QODER_APPCODE,
        "accept": "application/json",
        "accept-encoding": "identity",
        "date": now_utc,
        "signature": md5_hex(f"{QODER_APPCODE}&{QODER_SIG_SECRET}&{now_utc}"),
        "content-type": "application/json",
        "user-agent": "Go-http-client/2.0",
    }


def exchange_pat(pat: str, realm: str = "intl", session: requests.Session | None = None,
                 proxy: str | None = None, log=print) -> QoderAuth:
    """PAT (`pt-…`) -> job-token identity."""
    cfg = REALMS.get(realm, REALMS["intl"])
    auth = QoderAuth()
    inner = json.dumps({
        "personalToken": pat,
        "securityOauthToken": "",
        "refreshToken": "",
        "needRefresh": False,
        "authInfo": {},
    }, separators=(",", ":"))
    body = json.dumps({"payload": inner, "encodeVersion": "1"}, separators=(",", ":"))
    encoded = transform_body(body)
    url = f"{cfg['center']}/algo/api/v3/user/jobToken?Encode=1"
    headers = static_headers(auth.machine_id)
    headers["content-length"] = str(len(encoded))

    s = session or requests
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = s.post(url, headers=headers, data=encoded, timeout=TIMEOUT, proxies=proxies)
    log(f"  [*] PAT exchange -> HTTP {r.status_code}")
    if r.status_code != 200:
        raise RuntimeError(f"PAT exchange failed: HTTP {r.status_code} {r.text[:200]}")
    j = r.json()
    if not j.get("id") or not j.get("securityOauthToken"):
        raise RuntimeError(f"PAT exchange incomplete: {str(j)[:200]}")
    auth.user_id = str(j["id"])
    auth.user_name = str(j.get("name") or "")
    auth.user_type = str(j.get("userType") or "personal_standard")
    auth.security_oauth_token = str(j["securityOauthToken"])
    auth.refresh_token = str(j.get("refreshToken") or "")
    return auth


# ─────────────────────────── claim walk ───────────────────────

@dataclass
class ClaimReport:
    realm: str = "intl"
    user_id: str = ""
    user_name: str = ""
    user_type: str = ""
    calls: list = field(default_factory=list)     # (label, method, url, status, body)
    activity_ids: list = field(default_factory=list)
    claimed: list = field(default_factory=list)
    campaigns: list = field(default_factory=list)
    plan: dict = field(default_factory=dict)
    verdict: str = "unknown"

    def as_dict(self) -> dict:
        return {"realm": self.realm, "userId": self.user_id, "userName": self.user_name,
                "userType": self.user_type, "plan": self.plan,
                "activityIds": self.activity_ids,
                "claimed": self.claimed, "campaigns": self.campaigns,
                "verdict": self.verdict,
                "calls": [{"label": c[0], "method": c[1], "url": c[2],
                           "status": c[3], "body": c[4][:1200]} for c in self.calls]}


def _headers_for(auth: QoderAuth, url: str, body: str = "") -> dict[str, str]:
    """
    Auth depends on the host, not on the call:
      • `/algo/**` (inference hosts + center)  -> COSY signature
      • openapi/sash surfaces (center.qoder.sh, no /algo) -> Bearer job token
    The job token is the `securityOauthToken` returned by the PAT exchange.
    """
    if "/algo" in url:
        return cosy_headers(auth, url, body)
    return {
        **static_headers(auth.machine_id),
        "Authorization": f"Bearer {auth.security_oauth_token}",
        "content-type": "application/json",
    }


def _call(report: ClaimReport, auth: QoderAuth, label: str, method: str, url: str,
          body: str | None = None, session=None, proxy=None, log=print):
    headers = _headers_for(auth, url, body or "")
    if body is not None:
        encoded = transform_body(body) if "/algo" in url else body.encode()
        headers["content-length"] = str(len(encoded))
    else:
        encoded = None
    s = session or requests
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        r = s.request(method, url, headers=headers, data=encoded,
                      timeout=TIMEOUT, proxies=proxies)
        text = r.text
    except requests.RequestException as e:
        r, text = None, f"ERR {e}"
    status = r.status_code if r is not None else 0
    report.calls.append((label, method, url, status, text))
    log(f"  [{label}] {method} -> HTTP {status} :: {text[:220].replace(chr(10), ' ')}")
    return status, text


def fetch_plan(auth: QoderAuth, cfg: dict | None = None, proxy: str | None = None,
               log=print) -> dict:
    """
    The account's real subscription state.

    `/api/v2/user/plan` is what the CLI reads at startup; `/api/v3/user/status`
    adds quota + the machine-readable `PLAN_TIER_*`. This — not the activity
    endpoints — is where a granted Pro Trial actually shows up.
    """
    cfg = cfg or REALMS["intl"]
    headers = {**static_headers(auth.machine_id),
               "Authorization": f"Bearer {auth.security_oauth_token}",
               "accept": "application/json"}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    out: dict = {}
    for key, path in (("plan", "/api/v2/user/plan"), ("status", "/api/v3/user/status")):
        try:
            r = requests.get(cfg["openapi"] + path, headers=headers, timeout=TIMEOUT,
                             proxies=proxies)
            out[key + "_http"] = r.status_code
            out[key] = json.loads(r.text) if r.status_code == 200 else r.text[:200]
        except Exception as e:  # noqa: BLE001
            out[key + "_http"] = 0
            out[key] = f"ERR {e}"
    st = out.get("status") if isinstance(out.get("status"), dict) else {}
    pl = out.get("plan") if isinstance(out.get("plan"), dict) else {}
    tier = str(st.get("plan") or pl.get("user_type") or "").upper()
    out["tier"] = tier
    out["is_trial"] = "TRIAL" in tier
    out["is_paid"] = bool(pl.get("is_paid_plan"))
    out["trial_end"] = st.get("nextResetAt") or pl.get("end_date") or 0
    out["quota"] = st.get("quota")
    out["quota_exceeded"] = st.get("isQuotaExceeded")
    out["user_tag"] = st.get("userTag") or pl.get("plan_tier_name") or ""
    if log:
        log(f"  [*] plan: {out['user_tag'] or tier or '?'} "
            f"(paid={out['is_paid']}, quota={out['quota']}, "
            f"exceeded={out['quota_exceeded']})")
    return out


def claim_pro_trial(pat: str, realm: str = "intl", do_claim: bool = False,
                    proxy: str | None = None, log=print) -> ClaimReport:
    """Exchange the PAT and walk every documented claim surface."""
    cfg = REALMS.get(realm, REALMS["intl"])
    rep = ClaimReport(realm=realm)
    auth = exchange_pat(pat, realm, proxy=proxy, log=log)
    rep.user_id, rep.user_name, rep.user_type = auth.user_id, auth.user_name, auth.user_type
    log(f"  [*] identity: {auth.user_id} / {auth.user_name or '-'} / {auth.user_type}")

    rep.plan = fetch_plan(auth, cfg, proxy=proxy, log=log)
    _call(rep, auth, "region", "GET",
          f"{cfg['openapi']}/algo/api/v2/service/region/endpoints", proxy=proxy, log=log)
    # The inference-host activity LIST answers 403 "Signature invalid" for a
    # PAT-derived identity (the desktop signs it with the shared-process HMAC
    # scheme, not COSY). It is optional: the authoritative surfaces for a claim
    # decision are eligibility + campaigns below, which both answer a Bearer
    # job token.
    act_text = ""
    if os.environ.get("QODER_TRY_ACTIVITY") or do_claim:
        _, act_text = _call(rep, auth, "activity", "GET",
                            f"{cfg['infer']}/algo/api/v2/activity", proxy=proxy, log=log)
    _, elig_text = _call(rep, auth, "eligibility", "GET",
                         f"{cfg['openapi']}/api/v2/activity/claim/eligibility",
                         proxy=proxy, log=log)
    _, camp_text = _call(rep, auth, "campaigns", "GET",
                         f"{cfg['openapi']}/sash/api/v1/me/campaigns",
                         proxy=proxy, log=log)
    _call(rep, auth, "quota-reset", "GET",
          f"{cfg['openapi']}/api/v2/activity/quota/reset/latest", proxy=proxy, log=log)

    def ids_from(text: str, keys: tuple[str, ...]) -> list[str]:
        try:
            data = json.loads(text)
        except Exception:
            return []
        out: list[str] = []

        def walk(node):
            if isinstance(node, dict):
                for k in keys:
                    if isinstance(node.get(k), str) and node[k]:
                        out.append(node[k])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return out

    rep.activity_ids = list(dict.fromkeys(
        ids_from(elig_text, ("activityId", "activity_id")) +
        ids_from(act_text, ("activityId", "activity_id"))))

    try:
        rep.campaigns = json.loads(camp_text).get("campaigns", []) or []
    except Exception:
        rep.campaigns = []

    credit_campaigns = [c for c in rep.campaigns
                        if str(c.get("actionType", "")).upper() == "CLAIM_BENEFIT"
                        or str((c.get("benefit") or {}).get("kind", "")).upper() == "CREDITS"]
    for c in credit_campaigns:
        log(f"  [*] campaign {c.get('campaignKey') or c.get('campaignId')} "
            f"status={c.get('claimStatus')}")

    if do_claim:
        for cid in rep.activity_ids:
            st, text = _call(rep, auth, f"claim:{cid}", "POST",
                             f"{cfg['openapi']}/api/v2/activity/claim?activityId={cid}",
                             body="{}", proxy=proxy, log=log)
            if st == 200:
                try:
                    if json.loads(text).get("code") == 0:
                        rep.claimed.append(cid)
                except Exception:
                    pass
        for c in credit_campaigns:
            if str(c.get("claimStatus", "")).upper() != "CLAIMABLE":
                continue
            cid = c.get("campaignId")
            if not cid:
                continue
            st, text = _call(rep, auth, f"claim-campaign:{c.get('campaignKey')}", "POST",
                             f"{cfg['openapi']}/sash/api/v1/me/campaigns/{cid}/claim",
                             body="{}", proxy=proxy, log=log)
            if st == 200:
                rep.claimed.append(str(cid))

    if rep.claimed:
        rep.verdict = "claimed"
    elif rep.plan.get("is_trial"):
        rep.verdict = "pro-trial-active"
    elif rep.plan.get("is_paid"):
        rep.verdict = "paid-plan"
    elif rep.activity_ids:
        rep.verdict = "claimable-not-claimed"
    elif credit_campaigns:
        rep.verdict = "campaign-visible"
    else:
        rep.verdict = "free-no-claim-provisioned"
    return rep


def load_paths(path: str) -> list[str]:
    """One PAT per line; `EMAIL|PASSWORD|PAT` lines also accepted."""
    out: list[str] = []
    p = Path(path)
    text = p.read_text() if p.exists() else path
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cand = line.split("|")[-1].strip() if "|" in line else line
        if cand.startswith("pt-"):
            out.append(cand)
    return list(dict.fromkeys(out))


def claim_batch(paths: list[str], realm: str = "intl", do_claim: bool = False,
                proxy: str | None = None, wait_minutes: int = 0, log=print) -> list[ClaimReport]:
    """Walk every path; with wait_minutes > 0 keep re-checking until claimable."""
    reports: list[ClaimReport] = []
    deadline = time.time() + wait_minutes * 60 if wait_minutes else 0
    pending = list(paths)
    round_no = 0
    while pending:
        round_no += 1
        log(f"\n=== round {round_no}: {len(pending)} path ===")
        still: list[str] = []
        for i, pat in enumerate(pending, 1):
            log(f"[{i}/{len(pending)}] {pat[:18]}…")
            try:
                rep = claim_pro_trial(pat, realm=realm, do_claim=do_claim, proxy=proxy, log=log)
            except Exception as e:  # noqa: BLE001
                rep = ClaimReport(realm=realm, verdict="pat-invalid")
                rep.claimed.clear()
                rep.calls.append(("exchange", "POST", "", 0, str(e)))
                log(f"  [!] {e}")
            reports.append(rep)
            log(f"  => {rep.verdict}"
                + (f" | claimed={','.join(rep.claimed)}" if rep.claimed else ""))
            if rep.verdict == "no-claim-provisioned" and time.time() < deadline:
                still.append(pat)
        if not still or time.time() >= deadline:
            break
        log(f"  [*] {len(still)} belum diprovisikan — cek lagi dalam 60s (sampai "
            f"{int((deadline - time.time()) // 60)} menit lagi)")
        time.sleep(60)
        pending = still
    return reports


def claim_menu(input_fn=input, print_fn=print) -> None:
    """Interactive entry used by main.py."""
    mode = (input_fn("  Mode [1] satu path  [2] batch file  [3] tunggu sampai claimable [1]: ")
            .strip() or "1")
    realm = (input_fn("  Realm [intl/cn] (default intl): ").strip() or "intl").lower()
    do_claim = (input_fn("  Kirim claim sekarang? (y/n) [y]: ").strip().lower() or "y") == "y"
    proxy = input_fn("  Proxy (kosongkan jika tidak ada): ").strip() or None

    paths: list[str] = []
    wait_minutes = 0
    if mode == "2":
        src = input_fn("  File / daftar path (1 per baris, EMAIL|PASS|PATH juga boleh): ").strip()
        paths = load_paths(src)
        if not paths:
            print_fn("  [!] tidak ada path pt-… ditemukan")
            return
    elif mode == "3":
        paths = [input_fn("  Account path (pt-…): ").strip()]
        raw = input_fn("  Tunggu maksimal berapa menit? [30]: ").strip() or "30"
        wait_minutes = max(1, int(raw)) if raw.isdigit() else 30
    else:
        paths = [input_fn("  Account path (pt-…): ").strip()]
    paths = [p for p in paths if p]
    if not paths:
        print_fn("  [!] path kosong")
        return

    print_fn(f"\n[🎁] Claim Pro Trial — {len(paths)} path, realm={realm}, "
             f"claim={do_claim}, wait={wait_minutes}m")
    reports = claim_batch(paths, realm=realm, do_claim=do_claim, proxy=proxy,
                          wait_minutes=wait_minutes, log=print_fn)

    print_fn("\n  ── ringkasan ──")
    tally: dict[str, int] = {}
    for r in reports:
        tally[r.verdict] = tally.get(r.verdict, 0) + 1
        end = r.plan.get("trial_end") or 0
        when = ""
        if isinstance(end, (int, float)) and end > 0:
            when = " until " + datetime.fromtimestamp(end / 1000, timezone.utc).strftime("%Y-%m-%d")
        print_fn(f"   • {r.user_name or r.user_id or '(?)':22} {r.verdict:26}"
                 f" [{r.plan.get('user_tag') or '-'}{when}]"
                 + (f" claimed={','.join(r.claimed)}" if r.claimed else ""))
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print_fn(f"   {v}× {k}")
    CLAIM_RESULT.write_text(json.dumps([r.as_dict() for r in reports], indent=2))
    print_fn(f"  📄 detail -> {CLAIM_RESULT.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Qoder Pro Trial claim via account path (PAT)")
    ap.add_argument("--path", action="append", default=[],
                    help="Qoder account path / PAT (pt-…); repeatable")
    ap.add_argument("--paths", help="file with one path per line (EMAIL|PASS|PATH ok)")
    ap.add_argument("--realm", default="intl", choices=["intl", "cn"])
    ap.add_argument("--claim", action="store_true", help="actually POST the claim")
    ap.add_argument("--wait-minutes", type=int, default=0,
                    help="re-check unprovisioned accounts until claimable")
    ap.add_argument("--proxy", default=None)
    a = ap.parse_args()

    paths = list(a.path)
    if a.paths:
        paths += load_paths(a.paths)
    paths = [p for p in dict.fromkeys(paths) if p]
    if not paths:
        ap.error("need --path pt-… or --paths <file>")

    reports = claim_batch(paths, realm=a.realm, do_claim=a.claim, proxy=a.proxy,
                          wait_minutes=a.wait_minutes)
    CLAIM_RESULT.write_text(json.dumps([r.as_dict() for r in reports], indent=2))
    for r in reports:
        status = "OK " if r.claimed else "   "
        print(f"[{status}] {r.user_name or r.user_id} -> {r.verdict}"
              + (f" claimed={','.join(r.claimed)}" if r.claimed else ""))
    return 0 if all(r.verdict != "pat-invalid" for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
