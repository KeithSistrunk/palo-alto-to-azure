# Lab 2: SSL forward proxy decryption

**Goal:** decrypt outbound HTTPS from the lab LAN, exclude sensitive sites, and verify certificate validation.

## Build

- **Forward Trust CA** (installed on the lab host) and a separate **Forward Untrust CA** (deliberately not trusted), so bad server certificates still warn the user.
- Decryption profile: block expired certificates and untrusted issuers, minimum TLS 1.2.
- Rule order: `no-decrypt-sensitive` (custom URL list of banking domains) above `decrypt-lab-laptop`.
- QUIC blocked so browsers fall back to TCP TLS, which can be decrypted.

## Validation

| Test | Result |
| --- | --- |
| Normal HTTPS site | Issuer shows the lab Forward Trust CA; traffic log Decrypted = yes |
| `expired.badssl.com` | Blocked by the firewall's certificate error page: status *expired*, reason *expired certificate* |
| Banking site (excluded) | Decryption log: policy `no-decrypt-sensitive`, proxy type *No Decrypt*; App-ID stays `ssl` |

## Takeaways

- Without a URL Filtering license, exclusions use a custom URL list; in production, exclude by category (financial services, health) with legal and HR sign-off.
- Decryption breaks certificate-pinned apps; exclude them.
- Logs record metadata, not credentials. Packet captures of decrypted traffic do contain plaintext and need strict access control.
