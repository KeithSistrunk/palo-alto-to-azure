# Lab 1: Firewall baseline and App-ID

**Goal:** take a factory-reset PA-440 to a working edge firewall behind a home router, then replace a port-based allow rule with App-ID policy.

## Design

| Port | Zone | Address |
| --- | --- | --- |
| MGT | n/a | 192.168.1.100 (admin only) |
| ethernet1/1 | untrust | 192.168.1.2 (behind the home router, double NAT) |
| ethernet1/2 | trust | 10.100.1.1/24, DHCP to lab hosts |

- Source NAT (dynamic IP and port) from trust to untrust.
- Default route 0.0.0.0/0 to the home router.

## App-ID policy

Replaced an allow-any rule with `trust-to-internet-appid`: `dns`, `ssl`, `web-browsing`, `ping`, `ntp`, `google-base`, service **application-default**. Logging was enabled on `interzone-default` so denies are visible.

## Content updates

Updated App-ID content from 8990-9489 (June 2025) to 9169-10340 (November 2026). Before installing, reviewed the new and modified App-IDs for policy impact; afterward, watched the deny logs for newly identified apps.

## Issues found and fixed

| Symptom | Cause | Fix |
| --- | --- | --- |
| Home-network hosts reachable, internet not | Static default route had destination `0.0.0.0` instead of `0.0.0.0/0` | Corrected the route |
| google.com blocked, other sites fine | Google traffic is identified as `google-base`, not `ssl` | Added the App-ID by name rather than allowing TCP 443 |

## Takeaways

- Allow applications, not ports: `application-default` restricts each app to its standard ports without breaking DNS or NTP.
- New build: default deny plus App-ID rules. Migration: keep port rules and convert with Policy Optimizer.
