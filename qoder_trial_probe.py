#!/usr/bin/env python3
"""
Qoder Pro Trial — prove *where* the grant came from, don't guess.

Three things get measured and reported separately:

  1. PLAN       `/api/v2/user/plan` + `/api/v3/user/status` — the account's
                actual tier. This is the outcome a claim is judged by.
  2. CLAIM      `/api/v2/activity/claim/eligibility`, `/sash/api/v1/me/campaigns`
                and the POST routes. Verified live: a bogus `activityId`
                answers `200 {"code":-1,"msg":"Activity not found"}`, so the
                route + auth + parameter are all accepted — only a real,
                server-provisioned id is missing.
  3. PROVISION  the acceptance flip test. The only honest way to say "the trial
                came from X" is to register a fresh account *through* X and
                watch the plan before/after. `--trial-flip` does exactly that:
                register via an invite path, poll `/api/v2/user/plan` and report
                the first observation that is no longer Free.

Why the second half needs a real mailbox: Qoder answers
`POST /api/v1/verificationCodes -> 200` but drops the mail for every
disposable domain tested (fldubai.com, arcadehearth/marchslurp, mailnesia.com,
robot-mail.com, blondmail.com, temptami.com, chapsmail.com — all empty after
3+ minutes). Set `QREG_IMAP=user@host:app-password` to read the code from a real
inbox (plus-addressing gives unlimited addresses).

Usage:
    python qoder_trial_probe.py --path pt-…                 # plan + claim state
    python qoder_trial_probe.py --path pt-… --raw           # dump every call
    python qoder_trial_probe.py --activity-id <id> --path pt-… --post
    python qoder_trial_probe.py --trial-flip --referral pt-…   # needs QREG_IMAP
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import qoder_claim as QC  # noqa: E402

PROBE_RESULT = Path(__file__).parent / "qoder_trial_probe.json"

TRIAL_TIERS = ("TRIAL", "PRO_TRIAL")


def _tier_of(plan: dict) -> str:
    st = plan.get("status") if isinstance(plan.get("status"), dict) else {}
    pl = plan.get("plan") if isinstance(plan.get("plan"), dict) else {}
    return str(st.get("plan") or pl.get("user_type") or plan.get("tier") or "").upper()


def is_pro_trial(plan: dict) -> bool:
    return any(t in _tier_of(plan) for t in TRIAL_TIERS) or bool(plan.get("is_trial"))


@dataclass
class Probe:
    path: str = ""
    user_id: str = ""
    user_name: str = ""
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    claim_calls: list = field(default_factory=list)
    posted: list = field(default_factory=list)
    verdict: str = ""
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "path": self.path, "userId": self.user_id, "userName": self.user_name,
            "before": self.before, "after": self.after,
            "claimCalls": self.claim_calls, "posted": self.posted,
            "verdict": self.verdict, "notes": self.notes,
        }


def probe_path(path: str, realm: str = "intl", proxy: str | None = None,
               activity_id: str | None = None, do_post: bool = False,
               raw: bool = False, log=print) -> Probe:
    """Plan + claim state for one account path, with optional real POST."""
    p = Probe(path=path)
    cfg = QC.REALMS.get(realm, QC.REALMS["intl"])
    auth = QC.exchange_pat(path, realm, proxy=proxy, log=log)
    p.user_id, p.user_name = auth.user_id, auth.user_name

    p.before = QC.fetch_plan(auth, cfg, proxy=proxy, log=log)
    p.verdict = "pro-trial-active" if is_pro_trial(p.before) else "free"

    def call(label: str, method: str, url: str, body: str | None = None):
        headers = QC._headers_for(auth, url, body or "")
        data = None
        if body is not None:
            data = QC.transform_body(body) if "/algo" in url else body.encode()
            headers["content-length"] = str(len(data))
        try:
            r = QC.requests.request(method, url, headers=headers, data=data, timeout=QC.TIMEOUT)
            status, text = r.status_code, r.text
        except Exception as e:  # noqa: BLE001
            status, text = 0, f"ERR {e}"
        p.claim_calls.append({"label": label, "method": method, "url": url,
                              "status": status, "body": text[:400]})
        if raw or status not in (200,):
            log(f"  [{label}] {method} -> {status} {text[:200]}")
        return status, text

    for label, url in (("eligibility", f"{cfg['openapi']}/api/v2/activity/claim/eligibility"),
                       ("campaigns", f"{cfg['openapi']}/sash/api/v1/me/campaigns"),
                       ("quota-reset", f"{cfg['openapi']}/api/v2/activity/quota/reset/latest")):
        call(label, "GET", url)

    ids: list[str] = []
    for entry in p.claim_calls:
        if entry["label"] == "eligibility":
            try:
                for d in json.loads(entry["body"]).get("data", []) or []:
                    if isinstance(d, dict):
                        ids.append(str(d.get("activityId") or d.get("id") or ""))
            except Exception:  # noqa: BLE001
                pass
    ids = [i for i in dict.fromkeys(ids) if i]
    if activity_id:
        ids.append(activity_id)

    if not ids:
        p.notes.append(
            "no server-provisioned activityId and no --activity-id: the POST route "
            "cannot be exercised against a real id. Confirmed live that the route "
            "itself accepts the request (bogus id -> code -1 'Activity not found').")
    for aid in ids:
        if do_post:
            st, txt = call(f"claim:{aid}", "POST",
                           f"{cfg['openapi']}/api/v2/activity/claim?activityId={aid}",
                           body="{}")
            p.posted.append({"activityId": aid, "status": st, "body": txt[:300]})
            if st == 200 and '"code":0' in txt.replace(" ", ""):
                p.verdict = "claimed"
        else:
            call(f"probe:{aid}", "POST",
                 f"{cfg['openapi']}/api/v2/activity/claim?activityId={aid}", body="{}")

    p.after = QC.fetch_plan(auth, cfg, proxy=proxy, log=log)
    if not p.verdict.startswith("claimed"):
        p.verdict = "pro-trial-active" if is_pro_trial(p.after) else "free"
    return p


def _read_code(address: str, timeout: int = 150) -> str | None:
    """Pull the newest Qoder code addressed to `address` out of the IMAP mailbox."""
    import qoder_register as QR

    mb = QR.Mailbox(address, QR.IMAP_ACCOUNT.split(":", 1)[1]
                    if "@" in QR.IMAP_ACCOUNT else "", kind="imap")
    return QR.wait_for_code(mb, timeout=timeout)


def web_plan(email: str, password: str, log=print) -> dict:
    """
    Sign in on qoder.com with email + password and read the plan through the
    web session. This is the only way to judge a *freshly registered* account:
    a PAT does not exist until someone mints one in the account UI.
    """
    from playwright.sync_api import sync_playwright

    out: dict = {"email": email, "login": "unknown", "plan": None}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False,
                                     args=["--disable-blink-features=AutomationControlled",
                                           "--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            # step 1: email
            page.goto("https://qoder.com/users/sign-in", wait_until="domcontentloaded")
            page.wait_for_selector("#basic_email", timeout=30_000)
            page.fill("#basic_email", email)
            page.get_by_role("button", name=re.compile("Continue", re.I)).first.click()
            time.sleep(2.5)

            # step 2a: password if the form asks for it
            pwd = page.query_selector("#basic_password")
            if pwd and pwd.is_visible():
                pwd.fill(password)
                for label in ("Sign in", "Continue", "Log in"):
                    try:
                        page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=3000)
                        break
                    except Exception:
                        continue
            else:
                # step 2b: passwordless — ask for a code and read it from the mailbox
                for label in ("Send Code", "Send code", "Get code"):
                    try:
                        page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=3000)
                        break
                    except Exception:
                        continue
                code = _read_code(email)
                if code:
                    boxes = page.query_selector_all("input[maxlength='1']")
                    if boxes:
                        boxes[0].click()
                        page.keyboard.type(code, delay=70)
                    else:
                        f = page.query_selector("input[placeholder*='code' i]")
                        if f:
                            f.fill(code)
                    time.sleep(3)
            time.sleep(6)
            r = ctx.request.get("https://qoder.com/api/v1/me/userplan",
                                headers={"Accept": "application/json"})
            out["login"] = "ok" if r.ok else f"http{r.status}"
            out["plan"] = r.json() if r.ok else r.text[:300]
        except Exception as e:  # noqa: BLE001
            out["login"] = f"error: {e}"
        finally:
            browser.close()
    log(f"  [web] login={out['login']} plan={str(out['plan'])[:160]}")
    return out


def trial_flip(referral: str, realm: str = "intl", minutes: int = 45,
               interval: int = 120, log=print) -> dict:
    """
    The acceptance test: register through `referral`, then watch the plan of the
    new account until it stops being Free. The first non-Free reading is the flip.
    """
    import qoder_register as QR

    if not QR.IMAP_ACCOUNT:
        raise SystemExit("--trial-flip needs a real mailbox: "
                         "export QREG_IMAP=user@host:app-password")
    t0 = time.time()
    out: dict = {"referral": referral, "registered": None, "before": None, "after": None,
                 "flip": None, "observations": []}
    log(f"[flip] registering a fresh account through referral_code={referral[:18]}…")
    res = QR.auto_register(count=1, referral_code=referral, headless=False,
                           mail_provider="imap", retries=4, log=log)[0]
    out["registered"] = res.as_dict()
    if not res.ok:
        out["flip"] = "not-registered"
        log("[flip] registration did not complete — nothing to poll")
        return out

    # observation 0: the plan read with the fresh account's own session
    out["before"] = res.plan_detail or res.status_detail or None
    out["after"] = out["before"]
    log(f"[flip] plan right after signup: {str(out['before'])[:240]}")
    if out["before"] and "TRIAL" in json.dumps(out["before"]).upper():
        out["flip"] = "pro-trial-granted"
        log("[flip] PLAN IS ALREADY PRO TRIAL AT SIGNUP")
        return out
    out["observations"].append({"at": datetime.now(timezone.utc).isoformat(),
                                "source": "registration-session", "plan": out["before"]})

    log(f"[flip] registered {res.email}; polling its plan for {minutes} min")
    while (time.time() - t0) / 60 < minutes:
        obs = web_plan(res.email, res.password, log=log)
        out["observations"].append({"at": datetime.now(timezone.utc).isoformat(), **obs})
        if obs.get("login") == "ok" and obs.get("plan"):
            if out["before"] is None:
                out["before"] = obs["plan"]
            out["after"] = obs["plan"]
            tier = json.dumps(obs["plan"]).upper()
            if "TRIAL" in tier or "PRO_TRIAL" in tier:
                out["flip"] = "pro-trial-granted"
                log("[flip] PLAN FLIPPED to Pro Trial")
                break
        time.sleep(interval)
    if not out["flip"]:
        out["flip"] = "still-free"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Prove where a Qoder Pro Trial grant comes from")
    ap.add_argument("--path", default=QC.DEFAULT_ACCOUNT_PATH)
    ap.add_argument("--realm", default="intl", choices=["intl", "cn"])
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--activity-id", default=None)
    ap.add_argument("--post", action="store_true", help="actually POST the claim")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--trial-flip", action="store_true",
                    help="register via --referral then poll for the plan flip")
    ap.add_argument("--referral", default=None)
    ap.add_argument("--minutes", type=int, default=45)
    a = ap.parse_args()

    if a.trial_flip:
        ref = a.referral or a.path
        out = trial_flip(ref, realm=a.realm, minutes=a.minutes)
        PROBE_RESULT.write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
        return 0

    p = probe_path(a.path, realm=a.realm, proxy=a.proxy, activity_id=a.activity_id,
                   do_post=a.post, raw=a.raw)
    PROBE_RESULT.write_text(json.dumps(p.as_dict(), indent=2))

    pl = (p.after or p.before).get("plan") or {}
    st = (p.after or p.before).get("status") or {}
    end = st.get("nextResetAt") or pl.get("end_date") or 0
    print(f"\n{'=' * 60}")
    print(f"{p.user_name}  ({p.user_id})")
    print(f"  tier      : {_tier_of(p.after or p.before) or '?'}"
          f"   tag={st.get('userTag') or pl.get('plan_tier_name') or '-'}")
    if isinstance(end, (int, float)) and end > 0:
        label = "trial ends" if is_pro_trial(p.after or p.before) else "next reset"
        print(f"  {label:10}: " + datetime.fromtimestamp(end / 1000, timezone.utc)
              .strftime("%Y-%m-%d %H:%M UTC"))
    print(f"  quota     : {st.get('quota')}  exceeded={st.get('isQuotaExceeded')}")
    print(f"  verdict   : {p.verdict}")
    for n in p.notes:
        print(f"  note      : {n}")
    for c in p.claim_calls:
        print(f"  {c['label']:14} {c['method']:4} {c['status']}  {c['body'][:90].replace(chr(10),' ')}")
    print(f"  detail    -> {PROBE_RESULT.name}")
    return 0 if p.verdict != "free" else 1


if __name__ == "__main__":
    sys.exit(main())
