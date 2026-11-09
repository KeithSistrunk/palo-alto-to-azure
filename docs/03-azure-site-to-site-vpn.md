# Lab 3: Site-to-site IPsec VPN to Azure

**Goal:** route-based IKEv2 tunnel from the PA-440 (behind NAT) to an Azure VPN gateway, with static routing, then troubleshoot real failures from the logs.

## Design

| Item | Value |
| --- | --- |
| PA local address / ID | 192.168.1.2 / `<home-public-ip>` |
| Azure | VpnGw1AZ gateway, hub `10.0.0.0/16` (Southeast Asia), connection mode ResponderOnly |
| Spoke | East Asia VNet `10.1.0.0/16`, peered with gateway transit (VM capacity was unavailable in the hub region) |
| Crypto | IKEv2, AES-256, SHA-256, DH14, PFS group 14, lifetimes 28800 / 27000 s |
| Routing | Static `10.0.0.0/15` via tunnel.1 (covers hub and spoke) |
| Policy | `trust-to-azure` and `azure-to-trust`, zone `vpn` |

Azure side built with the Azure CLI; VM template exported from the portal for reuse.

## Troubleshooting log

### 1. Pre-shared key mismatch (Phase 1)

```text
ikev2-nego-ike-fail  IKEv2 IKE SA negotiation is failed as initiator, non-rekey.
                     Failed SA: 192.168.1.2[4500]-<azure-gw-ip>[4500]
ike-recv-notify      IKE protocol notification message received: received notify type AUTHENTICATION_FAILED
```

Packets reached Azure over NAT-T (UDP 4500) and the proposals matched, so *received* AUTHENTICATION_FAILED pointed to the PSK. Reset the key on both sides with an alphanumeric value.

### 2. Phase 2 encryption mismatch (3DES vs AES-256)

```text
ikev2-nego-child-st  IKEv2 child SA negotiation is started as initiator, non-rekey.
ike-recv-notify      received notify type NO_PROPOSAL_CHOSEN
ike-generic-event    message lacks IDr payload
ikev2-nego-ike-fail  IKEv2 IKE SA negotiation is failed as initiator, non-rekey.
```

In IKEv2 the first child SA is negotiated inside IKE_AUTH, so a Phase 2 mismatch fails the whole exchange.

### 3. PFS mismatch that didn't break the tunnel

With no-PFS on the PA and PFS2048 on Azure, the tunnel still came up: the first child SA reuses IKE SA keys and skips PFS. Clearing Phase 2 made the PA rebuild a new IKE SA (non-rekey) each time, so PFS was never exercised. A PFS mismatch surfaces only at a Phase 2 rekey, as a tunnel that drops at a regular interval.

### 4. Tunnel up, no traffic

Encap counters at 0 while pinging: the security rule had the wrong source zone (`vpn` instead of `trust`), and the route had to widen to `10.0.0.0/15` to reach the spoke.

## Takeaways

- Read the system log first: `show log system direction equal backward subtype equal vpn`.
- Change one variable at a time; a PSK failure hides any Phase 2 problem behind it.
- Committing a change to an IKE gateway resets its tunnel on PAN-OS.
