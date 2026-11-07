"""Add (or remove) an address object through the PAN-OS XML API, then commit it.

Dry run by default: shows what would change and touches nothing.
  python push_change.py --name lab-loopback --ip 10.100.99.1/32            (dry run)
  python push_change.py --name lab-loopback --ip 10.100.99.1/32 --apply    (create + commit)
  python push_change.py --name lab-loopback --remove --apply               (delete + commit)

Uses a partial commit, so only this API user's changes are committed,
never another admin's pending work. Run through run-push.ps1, which supplies the key.
"""
import argparse
import ipaddress
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests
import urllib3

HOST = os.environ.get("PAN_HOST", "192.168.1.100")
KEY = os.environ.get("PAN_KEY")
USER = os.environ.get("PAN_USER", "apiwriter")
VERIFY = os.environ.get("PAN_CA_BUNDLE") or False
ADDR_XPATH = ("/config/devices/entry[@name='localhost.localdomain']"
              "/vsys/entry[@name='vsys1']/address")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")

if not VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def api(params, allow_error=False):
    try:
        resp = requests.post(f"https://{HOST}/api/", data={**params, "key": KEY},
                             verify=VERIFY, timeout=60)
    except requests.RequestException as e:
        sys.exit(f"Cannot reach https://{HOST}: {e}")
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        sys.exit(f"Unexpected reply (HTTP {resp.status_code}): {resp.text[:200]}")
    if root.get("status") != "success" and not allow_error:
        msg = " ".join(t.strip() for t in root.itertext() if t.strip())[:300]
        sys.exit(f"API error: {msg}")
    return root


def entry_xpath(name):
    return f"{ADDR_XPATH}/entry[@name='{name}']"


def find_object(name, running=False):
    """Return the <entry> element if the object exists (candidate config by default)."""
    root = api({"type": "config", "action": "show" if running else "get",
                "xpath": entry_xpath(name)}, allow_error=True)
    return root.find(".//entry")


def commit_and_wait():
    cmd = f"<commit><partial><admin><member>{USER}</member></admin></partial></commit>"
    root = api({"type": "commit", "action": "partial", "cmd": cmd})
    job = root.findtext(".//job")
    if not job:
        print("Nothing to commit: " + " ".join(t.strip() for t in root.itertext() if t.strip()))
        return True
    print(f"Commit job {job} started (partial commit, admin {USER})", end="", flush=True)
    for _ in range(90):  # up to ~3 minutes
        time.sleep(2)
        j = api({"type": "op", "cmd": f"<show><jobs><id>{job}</id></jobs></show>"})
        status, result = j.findtext(".//job/status"), j.findtext(".//job/result")
        print(".", end="", flush=True)
        if status == "FIN":
            print()
            details = [l.text for l in j.findall(".//job/details/line") if l.text]
            if result == "OK":
                print(f"Commit {job}: OK")
                return True
            print(f"Commit {job}: {result}")
            for line in details[:15]:
                print("  " + line)
            return False
    print("\nCommit still running after 3 minutes. Check Tasks in the GUI.")
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True, help="address object name")
    p.add_argument("--ip", help="IP or subnet, e.g. 10.100.99.1/32")
    p.add_argument("--description", default="Created by API (pan-api-lab)")
    p.add_argument("--remove", action="store_true", help="delete the object instead of creating it")
    p.add_argument("--apply", action="store_true", help="actually make the change and commit")
    a = p.parse_args()

    if not KEY:
        sys.exit("No API key. Run setup with -KeyName writer first.")
    if not NAME_RE.match(a.name):
        sys.exit("Name must be 1-63 letters, digits, dot, dash or underscore, starting with a letter or digit.")
    desc = re.sub(r"[<>&\"']", "", a.description)[:255]

    existing = find_object(a.name)
    mode = "APPLY" if a.apply else "DRY RUN (nothing will change; add --apply to make it)"
    print(f"Firewall {HOST} as {USER}  |  {mode}\n")

    if a.remove:
        if existing is None:
            sys.exit(f"'{a.name}' does not exist. Nothing to remove.")
        print(f"Will delete address object '{a.name}' "
              f"({existing.findtext('ip-netmask') or existing.findtext('fqdn') or 'other type'}) and commit.")
        if not a.apply:
            return
        api({"type": "config", "action": "delete", "xpath": entry_xpath(a.name)})
    else:
        if not a.ip:
            sys.exit("--ip is required when creating an object.")
        try:
            net = ipaddress.ip_network(a.ip, strict=False)
        except ValueError:
            sys.exit(f"'{a.ip}' is not a valid IP or subnet.")
        value = str(net)
        if existing is not None:
            current = existing.findtext("ip-netmask")
            sys.exit(f"'{a.name}' already exists ({current}). Nothing changed. Use --remove first to replace it.")
        print(f"Will create address object '{a.name}' = {value}, description '{desc}', and commit.")
        if not a.apply:
            return
        element = (f"<entry name='{a.name}'><ip-netmask>{value}</ip-netmask>"
                   f"<description>{desc}</description></entry>")
        api({"type": "config", "action": "set", "xpath": ADDR_XPATH, "element": element})

    print("Change staged in the candidate config.")
    if not commit_and_wait():
        sys.exit("Commit failed. The change is still in the candidate config; "
                 "revert it in the GUI (Config > Revert Changes) or fix the error and rerun.")

    now = find_object(a.name, running=True)
    if a.remove:
        print("Verified: object is gone from the running config." if now is None
              else "WARNING: object still present in the running config.")
    else:
        print(f"Verified in running config: {a.name} = {now.findtext('ip-netmask')}" if now is not None
              else "WARNING: object not found in the running config.")


if __name__ == "__main__":
    main()
