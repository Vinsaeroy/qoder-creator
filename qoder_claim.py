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
        "cosy-machineos": "linux",
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
    verdict: str = "unknown"

    def as_dict(self) -> dict:
        return {"realm": self.realm, "userId": self.user_id, "userName": self.user_name,
                "userType": self.user_type, "activityIds": self.activity_ids,
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


def claim_pro_trial(pat: str, realm: str = "intl", do_claim: bool = False,
                    proxy: str | None = None, log=print) -> ClaimReport:
    """Exchange the PAT and walk every documented claim surface."""
    cfg = REALMS.get(realm, REALMS["intl"])
    rep = ClaimReport(realm=realm)
    auth = exchange_pat(pat, realm, proxy=proxy, log=log)
    rep.user_id, rep.user_name, rep.user_type = auth.user_id, auth.user_name, auth.user_type
    log(f"  [*] identity: {auth.user_id} / {auth.user_name or '-'} / {auth.user_type}")

    _call(rep, auth, "region", "GET",
          f"{cfg['openapi']}/algo/api/v2/service/region/endpoints", proxy=proxy, log=log)
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
    elif rep.activity_ids:
        rep.verdict = "claimable-not-claimed"
    elif credit_campaigns:
        rep.verdict = "campaign-visible"
    else:
        rep.verdict = "no-claim-provisioned"
    return rep


def claim_menu(input_fn=input, print_fn=print) -> None:
    """Interactive entry used by main.py."""
    path = input_fn("  Account path (pt-…): ").strip()
    if not path:
        print_fn("  [!] path kosong")
        return
    realm = (input_fn("  Realm [intl/cn] (default intl): ").strip() or "intl").lower()
    do_claim = (input_fn("  Kirim claim sekarang? (y/n) [y]: ").strip().lower() or "y") == "y"
    proxy = input_fn("  Proxy (kosongkan jika tidak ada): ").strip() or None

    print_fn(f"\n[🎁] Claim Pro Trial — realm={realm}, claim={do_claim}")
    try:
        rep = claim_pro_trial(path, realm=realm, do_claim=do_claim, proxy=proxy,
                              log=print_fn)
    except Exception as e:  # noqa: BLE001
        _log(f"claim failed: {e}")
        print_fn(f"  [!] gagal: {e}")
        return

    print_fn(f"\n  Akun   : {rep.user_name or '-'} ({rep.user_id}) [{rep.user_type}]")
    print_fn(f"  Hasil  : {rep.verdict}")
    print_fn(f"  Activity ids : {', '.join(rep.activity_ids) or '(tidak ada)'}")
    print_fn(f"  Claimed      : {', '.join(rep.claimed) or '(tidak ada)'}")
    for c in rep.campaigns:
        print_fn(f"   • {c.get('campaignKey')} status={c.get('claimStatus')} "
                 f"benefit={(c.get('benefit') or {}).get('kind')}")
    CLAIM_RESULT.write_text(json.dumps(rep.as_dict(), indent=2))
    print_fn(f"  📄 detail -> {CLAIM_RESULT.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Qoder Pro Trial claim via account path (PAT)")
    ap.add_argument("--path", required=True, help="Qoder account path / PAT (pt-…)")
    ap.add_argument("--realm", default="intl", choices=["intl", "cn"])
    ap.add_argument("--claim", action="store_true", help="actually POST the claim")
    ap.add_argument("--proxy", default=None)
    a = ap.parse_args()

    rep = claim_pro_trial(a.path, realm=a.realm, do_claim=a.claim, proxy=a.proxy)
    print(json.dumps(rep.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
