# Lab 4: GlobalProtect remote access

**Goal:** remote-access VPN from a laptop on the home network into the lab LAN, without a GlobalProtect subscription.

## Build

| Item | Value |
| --- | --- |
| Portal and gateway | ethernet1/1, 192.168.1.2 (internal-only by design: no port forward) |
| Certificates | Lab root CA; server certificate with IP SAN 192.168.1.2 |
| Auth | Local database user via authentication profile |
| Tunnel | tunnel.2, zone `gp`, pool 10.100.50.0/24 |
| Split tunnel | 10.100.1.0/24 and loopback 10.100.99.1/32 |
| Policy | `gp-to-trust`: ping, ssh, ms-rdp |

## Issues found and fixed

| Problem | Cause | Fix |
| --- | --- | --- |
| Connected, ping to the PA's LAN IP failed | Management profile is evaluated on the ingress interface (tunnel.2) | `allow-ping` on tunnel.2 |
| Policy allowed, host didn't reply | Windows Firewall blocked ICMP (Ethernet on the Public profile) | Allow ICMP from 10.100.50.0/24 only |
| Commit failed: missing IP pool for config 'Loopback' | A second Client Settings entry was created instead of editing the existing one | Edited the existing entry; the first matching entry wins |
| Certificate without SAN still accepted | This app version falls back to the CN | Always include the SAN; test with a mismatched CN instead |

## Takeaways

- Portal hands out configuration; the gateway builds the tunnel.
- Basic portal/gateway VPN needs no subscription; HIP checks, mobile apps and app-based split tunneling do.
- Without PAN-OS updates, keep GlobalProtect off the internet.
