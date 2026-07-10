# Enterprise Data Center Failover Simulation (Cisco Packet Tracer)

A simulated enterprise network with two data centers — a **Primary** site and a **Disaster Recovery (DR)** site — built to demonstrate core routing, VLAN segmentation, gateway redundancy, and access control concepts at a CCNA-associate level. Built as a portfolio project for entry-level networking/IT roles.

## What this demonstrates
- Multilayer switching and inter-VLAN routing
- Single-area OSPF dynamic routing between two sites
- First-hop gateway redundancy with HSRP
- Access control between VLANs (management vs. workstation segmentation)
- A controlled link-failure test showing OSPF's detection and route-withdrawal behavior

## Topology

```
Primary DC:  Router0 (ISR4321) -- MLS0 (3560-24PS) -- Switch0 (2960-24TT) -- PC0, PC1, PC2
DR DC:       Router1 (ISR4321) -- MLS1 (3560-24PS) -- Switch1 (2960-24TT) -- PC3, PC4, PC5
WAN link:    Router0 <-> Router1 (single link, 172.16.0.0/30)
```

See `screenshots/topology-overview.png` for the full layout.

## IP Addressing

| VLAN / Link | Primary DC | DR DC |
|---|---|---|
| VLAN 10 – Servers | 10.10.10.0/24 | 10.20.10.0/24 |
| VLAN 20 – Workstations | 10.10.20.0/24 | 10.20.20.0/24 |
| VLAN 30 – Management | 10.10.30.0/24 | 10.20.30.0/24 |
| Switch↔MLS uplink | trunk (VLANs 10,20,30) | trunk (VLANs 10,20,30) |
| MLS↔Router routed link | 10.10.254.0/30 | 10.20.254.0/30 |
| Router↔Router WAN link | 172.16.0.0/30 (shared) | — |

Gateway IPs use HSRP virtual addresses (`.1` per VLAN) rather than the multilayer switch's own SVI address (`.2`), so PCs point at the redundant virtual gateway.

## What was built

1. **VLAN segmentation** — three VLANs (Servers, Workstations, Management) per site, trunked from access switch to multilayer switch.
2. **Inter-VLAN routing** — SVIs on each multilayer switch route between VLANs locally.
3. **OSPF (single area 0)** — dynamic routing between both sites over the routed MLS↔Router and Router↔Router links. Verified full adjacency across all four Layer 3 devices.
4. **HSRP** — a virtual gateway IP configured per VLAN per site, giving PCs a stable default gateway independent of the physical switch's own IP (sets up the pattern for a redundant second device in Phase 2).
5. **ACLs** — Workstation VLAN is blocked from reaching the Management VLAN, at both the local site and across the WAN to the other site's Management VLAN. Verified with both a blocked ping and an allowed ping, and confirmed via ACL hit counters.
6. **Failure test** — the WAN link between Router0 and Router1 was manually shut down to simulate a link failure. OSPF correctly dropped the neighbor adjacency and withdrew all DR-side routes from Router0's table, with no stale or black-holed routes. The link was restored and OSPF re-established full adjacency. Full detail and real log output in `results/failover-metrics.md`.

## Verification performed
- `show ip ospf neighbor` — confirmed 2 neighbors per router, 1 per multilayer switch, all FULL state
- `show ip route ospf` — confirmed cross-site routes present before failure, correctly removed after
- Cross-site ping (Primary VLAN10 → DR VLAN10) — succeeded with 0% loss after ARP resolution
- `show standby brief` — confirmed HSRP Active state on all VLAN interfaces, both sites
- `show access-lists` — confirmed nonzero deny-rule hit counts matching the blocked test traffic

## Repository structure
```
dc-failover-simulation/
├── README.md
├── topology.pkt
├── screenshots/
│   ├── topology-overview.png
│   ├── ospf-neighbors.png
│   ├── cross-site-ping.png
│   ├── standby-brief-before-failover.png
│   ├── acl-counters-blocked.png
│   ├── ospf-neighbors-after-failover.png
│   └── routing-table-before-failover.png / routing-table-after-failover.png
├── configs/
│   ├── router0.txt
│   ├── router1.txt
│   ├── multilayer-switch0.txt
│   └── multilayer-switch1.txt
└── results/
    └── failover-metrics.md
```

## Honest scope note
This is a **Phase 1** build, and it's scoped intentionally, not incompletely:
- **Single-area OSPF only** — everything runs in area 0. No multi-area design, no route summarization.
- **Single-gateway HSRP** — HSRP is configured on one multilayer switch per site, not a redundant pair. This sets up the correct virtual-IP addressing pattern, but there is currently no second device to fail over to if the multilayer switch itself goes down.
- **Single WAN path** — there is one physical link between Primary and Router1. The failure test in this repo demonstrates correct failure *detection and isolation* (OSPF drops the route cleanly, no stale entries), not automatic failover to a redundant path, since no second path exists yet.

A Phase 2 (redundant HSRP pairs, a second WAN path, multi-area OSPF) is a possible future extension but is out of scope for this build.

## Tools used
Cisco Packet Tracer.