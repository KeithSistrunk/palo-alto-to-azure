"""Create (or remove) the apiwriter account on the PA using a one-time admin login.

Called by bootstrap-writer.ps1. Reads from the environment:
  PAN_HOST, PAN_ADMIN_USER, PAN_ADMIN_PASSWORD, and for create: PAN_WRITER_PASSWORD
Nothing is written to disk. The admin key exists only in memory for this run.

Builds from objects you already have, using the firewall's own schema:
  role    api-change   = copy of api-readonly with XML API Commit enabled
  admin   apiwriter    = copy of apiuser with profile api-change
  user    apiwriter    in the same local user database as apiuser
  allow   apiwriter    added to the admin-local authentication profile
"""
import argparse
import html
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = os.environ.get("PAN_HOST", "192.168.1.100")
ADMIN = os.environ.get("PAN_ADMIN_USER", "admin")
WRITER, ROLE, SRC_ROLE, SRC_ADMIN, AUTH_PROFILE = "apiwriter", "api-change", "api-readonly", "apiuser", "admin-local"
VSYS = "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']"
KEY = None


def fail(msg):
    print(msg)
    sys.exit(1)


def call(params, allow_error=False):
    data = dict(params)
    if KEY:
        data["key"] = KEY
    try:
        r = requests.post(f"https://{HOST}/api/", data=data, verify=False, timeout=60)
    except requests.RequestException as e:
        fail(f"Cannot reach https://{HOST}: {e}")
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        fail(f"Unexpected reply (HTTP {r.status_code}): {r.text[:200]}")
    if root.get("status") != "success" and not allow_error:
        fail("API error: " + " ".join(t.strip() for t in root.itertext() if t.strip())[:300])
    return root


def get(xpath):
    """Return the first child element under <result> of a candidate-config read, or None."""
    res = call({"type": "config", "action": "get", "xpath": xpath}, allow_error=True).find("result")
    return None if res is None or len(res) == 0 else res[0]


def clean(el):
    """Strip bookkeeping attributes (admin, dirtyId, time, ...) so the copy can be pushed back."""
    for e in el.iter():
        for attr in [a for a in e.attrib if a != "name"]:
            del e.attrib[attr]
    return el


def first_found(paths):
    for p in paths:
        if get(p) is not None:
            return p
    return None


def wait_job(job):
    print(f"Commit job {job}", end="", flush=True)
    for _ in range(90):
        time.sleep(2)
        j = call({"type": "op", "cmd": f"<show><jobs><id>{job}</id></jobs></show>"})
        print(".", end="", flush=True)
        if j.findtext(".//job/status") == "FIN":
            print()
            if j.findtext(".//job/result") == "OK":
                print(f"Commit {job}: OK")
                return True
            print(f"Commit {job}: FAILED")
            for line in j.findall(".//job/details/line")[:15]:
                print("  " + (line.text or ""))
            return False
    print("\nCommit still running after 3 minutes. Check Tasks in the GUI.")
    return False


def main():
    global KEY
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()

    # 1. Admin key, in memory only
    r = call({"type": "keygen", "user": ADMIN, "password": os.environ.get("PAN_ADMIN_PASSWORD", "")}, allow_error=True)
    KEY = r.findtext(".//key")
    if not KEY:
        fail(f"Admin login failed for '{ADMIN}': " + (r.findtext(".//msg") or "check the password"))

    # 2. Refuse to run on top of someone's uncommitted GUI work (a partial commit would include it)
    pend = call({"type": "op", "cmd": "<check><pending-changes></pending-changes></check>"}, allow_error=True)
    if (pend.findtext(".//result") or "").strip().lower() == "yes":
        fail("There are uncommitted changes on the firewall. Commit or revert them in the GUI first, then rerun.")

    # 3. Locate existing objects
    role_base = "/config/shared/admin-role"
    admin_base = "/config/mgt-config/users"
    lud_base = first_found([f"/config/shared/local-user-database/user/entry[@name='{SRC_ADMIN}']",
                            f"{VSYS}/local-user-database/user/entry[@name='{SRC_ADMIN}']"])
    lud_base = lud_base.rsplit("/entry", 1)[0] if lud_base else None
    auth_xp = first_found([f"/config/shared/authentication-profile/entry[@name='{AUTH_PROFILE}']",
                           f"{VSYS}/authentication-profile/entry[@name='{AUTH_PROFILE}']"])

    plan = []
    if a.remove:
        if get(f"{admin_base}/entry[@name='{WRITER}']") is not None:
            plan.append(("delete", f"{admin_base}/entry[@name='{WRITER}']", None, f"admin account {WRITER}"))
        if auth_xp and get(f"{auth_xp}/allow-list/member[text()='{WRITER}']") is not None:
            plan.append(("delete", f"{auth_xp}/allow-list/member[text()='{WRITER}']", None, f"{WRITER} from {AUTH_PROFILE} allow list"))
        if lud_base and get(f"{lud_base}/entry[@name='{WRITER}']") is not None:
            plan.append(("delete", f"{lud_base}/entry[@name='{WRITER}']", None, f"local user {WRITER}"))
        if get(f"{role_base}/entry[@name='{ROLE}']") is not None:
            plan.append(("delete", f"{role_base}/entry[@name='{ROLE}']", None, f"admin role {ROLE}"))
        if not plan:
            print("Nothing to remove: apiwriter and api-change are not on the firewall.")
            return
    else:
        missing = [n for n, ok in [(f"role {SRC_ROLE}", get(f"{role_base}/entry[@name='{SRC_ROLE}']") is not None),
                                   (f"admin {SRC_ADMIN}", get(f"{admin_base}/entry[@name='{SRC_ADMIN}']") is not None),
                                   (f"local user {SRC_ADMIN}", lud_base is not None),
                                   (f"authentication profile {AUTH_PROFILE}", auth_xp is not None)] if not ok]
        if missing:
            fail("Can't build from existing objects; missing: " + ", ".join(missing) + ". Finish the Part 1 setup first.")
        if get(f"{admin_base}/entry[@name='{WRITER}']") is not None:
            fail(f"Admin '{WRITER}' already exists. Run the remove task first if you want to rebuild it.")
        pw = os.environ.get("PAN_WRITER_PASSWORD", "")
        if len(pw) < 8:
            fail("The apiwriter password must be at least 8 characters.")

        # Password hash generated by the firewall itself
        h = call({"type": "op", "cmd": "<request><password-hash><password>"
                  f"{html.escape(pw)}</password></password-hash></request>"}).findtext(".//phash")
        if not h:
            fail("The firewall didn't return a password hash.")

        role = clean(get(f"{role_base}/entry[@name='{SRC_ROLE}']"))
        role.set("name", ROLE)
        xmlapi = next((e for e in role.iter() if e.tag == "xmlapi"), None)
        if xmlapi is None:
            fail(f"Couldn't find the XML API section in role {SRC_ROLE}.")
        commit_el = xmlapi.find("commit")
        if commit_el is None:
            commit_el = ET.SubElement(xmlapi, "commit")
        commit_el.text = "enable"

        admin = clean(get(f"{admin_base}/entry[@name='{SRC_ADMIN}']"))
        admin.set("name", WRITER)
        prof = next((e for e in admin.iter() if e.tag == "profile"), None)
        if prof is None:
            fail(f"Couldn't find the role profile on admin {SRC_ADMIN}.")
        prof.text = ROLE
        for tag, val in (("authentication-profile", AUTH_PROFILE), ("phash", h)):
            el = admin.find(tag)
            if el is None:
                el = ET.SubElement(admin, tag)
            el.text = val

        plan = [
            ("set", role_base, ET.tostring(role, encoding="unicode"), f"admin role {ROLE} (copy of {SRC_ROLE} + XML API Commit)"),
            ("set", lud_base, f"<entry name='{WRITER}'><phash>{h}</phash></entry>", f"local user {WRITER}"),
            ("set", f"{auth_xp}/allow-list", f"<member>{WRITER}</member>", f"{WRITER} added to {AUTH_PROFILE} allow list"),
            ("set", admin_base, ET.tostring(admin, encoding="unicode"), f"admin account {WRITER} (role {ROLE}, auth {AUTH_PROFILE})"),
        ]

    print(f"\nPlanned changes on {HOST} (committed as '{ADMIN}', partial commit):")
    for action, _, _, desc in plan:
        print(f"  {action:<6} {desc}")
    if input("\nApply these changes? (y/N) ").strip().lower() != "y":
        print("Cancelled. Nothing was changed.")
        sys.exit(2)

    for action, xp, element, desc in plan:
        params = {"type": "config", "action": action, "xpath": xp}
        if element:
            params["element"] = element
        call(params)
        print(f"  done: {action} {desc}")

    cmd = f"<commit><partial><admin><member>{ADMIN}</member></admin></partial></commit>"
    job = call({"type": "commit", "action": "partial", "cmd": cmd}).findtext(".//job")
    if job and not wait_job(job):
        fail("Commit failed. The changes are still pending: revert them in the GUI (Config > Revert Changes).")

    exists = call({"type": "config", "action": "show",
                   "xpath": f"{admin_base}/entry[@name='{WRITER}']"}, allow_error=True).find(".//entry") is not None
    if a.remove:
        print("Verified: apiwriter removed." if not exists else "WARNING: apiwriter still in the running config.")
    else:
        print("Verified: apiwriter is in the running config." if exists else "WARNING: apiwriter not found after commit.")
        if not exists:
            sys.exit(1)


if __name__ == "__main__":
    main()
