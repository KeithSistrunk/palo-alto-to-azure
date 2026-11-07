"""Read-only PAN-OS security rule audit via the XML API.
Run through run-audit.ps1 (or the VS Code task), which supplies the key."""
import csv
import datetime
import os
import sys
import xml.etree.ElementTree as ET

import requests
import urllib3

HOST = os.environ.get("PAN_HOST", "192.168.1.100")
KEY = os.environ.get("PAN_KEY")
VERIFY = os.environ.get("PAN_CA_BUNDLE") or False  # path to the PA mgmt cert, or False in the lab
RULES_XPATH = ("/config/devices/entry[@name='localhost.localdomain']"
               "/vsys/entry[@name='vsys1']/rulebase/security/rules")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

if not VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def api(params):
    """Call the XML API and return the parsed <response>, or exit with the reason."""
    try:
        resp = requests.get(f"https://{HOST}/api/", params={**params, "key": KEY},
                            verify=VERIFY, timeout=30)
    except requests.RequestException as e:
        sys.exit(f"Cannot reach https://{HOST}: {e}")
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        sys.exit(f"Unexpected reply (HTTP {resp.status_code}): {resp.text[:200]}")
    if root.get("status") != "success":
        msg = root.findtext(".//msg") or root.findtext(".//line") or resp.text[:300]
        sys.exit(f"API error: {msg}")
    return root


def members(rule, tag):
    return [m.text for m in rule.findall(f"./{tag}/member")]


def audit(rule):
    """Return (name, action, findings) for one rule."""
    name = rule.get("name")
    action = rule.findtext("action", "allow")
    findings = []
    if rule.findtext("disabled") == "yes":
        findings.append("disabled")
    if action == "allow":
        if members(rule, "application") == ["any"]:
            findings.append("application any")
        if members(rule, "service") == ["any"]:
            findings.append("service any (use application-default)")
        if members(rule, "source") == ["any"] and members(rule, "destination") == ["any"]:
            findings.append("source and destination both any")
    if rule.findtext("log-end", "yes") == "no":
        findings.append("no log at session end")
    if not rule.findtext("description"):
        findings.append("no description")
    return name, action, findings


def main():
    if not KEY:
        sys.exit("No API key. Run setup first.")

    info = api({"type": "op", "cmd": "<show><system><info></info></system></show>"})
    print(f"Connected: {info.findtext('.//hostname')}  PAN-OS {info.findtext('.//sw-version')}")

    # action=show reads the RUNNING config; action=get would read the candidate config
    rules = api({"type": "config", "action": "show", "xpath": RULES_XPATH}).findall(".//rules/entry")
    print(f"{len(rules)} security rules\n")

    rows = []
    for rule in rules:
        name, action, findings = audit(rule)
        flag = "; ".join(findings) if findings else "OK"
        print(f"{name:<30} {action:<6} {flag}")
        rows.append({"rule": name, "action": action,
                     "from": ",".join(members(rule, "from")), "to": ",".join(members(rule, "to")),
                     "source": ",".join(members(rule, "source")),
                     "destination": ",".join(members(rule, "destination")),
                     "applications": ",".join(members(rule, "application")),
                     "findings": flag})

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"rule_audit_{datetime.datetime.now():%Y%m%d_%H%M}.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rule", "action", "from", "to", "source", "destination", "applications", "findings"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
