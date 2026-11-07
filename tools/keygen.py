"""Generate a PAN-OS API key. Reads PAN_HOST, PAN_USER, PAN_PASSWORD from the environment.
Prints only the key on success. Called by setup.ps1; you don't run this directly."""
import os
import sys
import xml.etree.ElementTree as ET

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fail(msg):
    print(msg)  # stdout, so setup.ps1 shows it as a plain message
    sys.exit(1)


host = os.environ["PAN_HOST"]
try:
    r = requests.post(f"https://{host}/api/",
                      data={"type": "keygen", "user": os.environ["PAN_USER"],
                            "password": os.environ["PAN_PASSWORD"]},
                      verify=False, timeout=30)
except requests.RequestException as e:
    fail(f"Cannot reach https://{host}: {e}")
try:
    root = ET.fromstring(r.text)
except ET.ParseError:
    fail(f"Unexpected reply (HTTP {r.status_code}): {r.text[:200]}")
key = root.findtext(".//key")
if root.get("status") != "success" or not key:
    fail("Key generation failed: " + (root.findtext(".//msg") or r.text[:200]))
print(key)
