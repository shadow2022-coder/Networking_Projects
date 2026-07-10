# Failover Test Results — Phase 1

## Test Objective
Verify that the network correctly detects and isolates a WAN link failure between the Primary and DR data centers, and correctly recovers when the link is restored.

## Test Method
Manually shut down Router0's WAN-facing interface (`GigabitEthernet0/0/1`), which carries the sole link between Router0 (Primary) and Router1 (DR) on subnet 172.16.0.0/30. This is the only path between sites in Phase 1 (single WAN link, no redundancy — see Known Limitations below).

Commands used:
```
interface gigabitEthernet0/0/1
shutdown
```
and to restore:
```
interface gigabitEthernet0/0/1
no shutdown
```

## Before Failure

`show ip ospf neighbor` on Router0:
```
Neighbor ID     Pri   State           Dead Time   Address         Interface
172.16.0.2      1     FULL/DR         00:00:37    172.16.0.2      GigabitEthernet0/0/1
10.10.254.1     1     FULL/BDR        00:00:34    10.10.254.1     GigabitEthernet0/0/0
```
Two neighbors: local MLS0 and remote Router1.

`show ip route ospf` on Router0 (before): routes to both Primary (10.10.x.0) and DR (10.20.x.0) subnets present.

## Failure Event

Interface shutdown at approximately **01:32:05** (device uptime timestamp). OSPF log confirmed immediate adjacency drop:
```
%LINK-5-CHANGED: Interface GigabitEthernet0/0/1, changed state to administratively down
%LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/0/1, changed state to down
01:32:05: %OSPF-5-ADJCHG: Process 1, Nbr 172.16.0.2 on GigabitEthernet0/0/1 from FULL to DOWN, Neighbor Down: Interface down or detached
```

## After Failure

`show ip ospf neighbor` on Router0:
```
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.10.254.1     1     FULL/BDR        00:00:32    10.10.254.1     GigabitEthernet0/0/0
```
Only 1 neighbor remains (local MLS0). Router1 adjacency correctly removed.

`show ip route ospf` on Router0 (after):
```
O    10.10.10.0 [110/2] via 10.10.254.1, 00:39:19, GigabitEthernet0/0/0
O    10.10.20.0 [110/2] via 10.10.254.1, 00:39:19, GigabitEthernet0/0/0
O    10.10.30.0 [110/2] via 10.10.254.1, 00:39:19, GigabitEthernet0/0/0
```
Only Primary-site (10.10.x.0) routes remain. All DR-site (10.20.x.0) routes correctly disappeared — confirms isolation on failure with no residual/stale route entries.

## Recovery

Interface restored with `no shutdown`. OSPF re-negotiated through normal neighbor states:
```
%LINK-5-CHANGED: Interface GigabitEthernet0/0/1, changed state to up
%LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/0/1, changed state to up
```
`show ip ospf neighbor` immediately after showed the new neighbor in `INIT/DROTHER` state, then progressed to full adjacency:
```
01:34:34: %OSPF-5-ADJCHG: Process 1, Nbr 172.16.0.2 on GigabitEthernet0/0/1 from LOADING to FULL, Loading Done
```

**Note on timing accuracy:** the ~2.5 minute gap between the shutdown log (01:32:05) and the full-adjacency log (01:34:34) includes manual delay between typed commands during testing, not pure OSPF reconvergence time. It is not reported here as a reconvergence metric, since OSPF's actual reconvergence is governed by the hello/dead timers (default 10s/40s) and was not isolated with precise stopwatch timing in this test run. A future, more rigorous test would issue `no shutdown` and immediately loop `show ip ospf neighbor` to capture the true reconvergence interval.

## Result Summary

| Check | Result |
|---|---|
| OSPF neighbor drop on failure | Pass — dropped from 2 to 1 neighbor immediately |
| DR routes removed on failure | Pass — all 10.20.x.0 routes gone, no stale entries |
| No unintended Primary-side disruption | Pass — 10.10.x.0 routes and local MLS0 adjacency unaffected |
| OSPF re-adjacency on restore | Pass — reached FULL state after `no shutdown` |

## Known Limitation

Phase 1 has a single WAN path between Primary and DR sites. This test demonstrates **correct failure detection and clean isolation** (no black-holed or stale routes) — it does not demonstrate automatic failover to a redundant path, since no second WAN link exists yet. Redundant WAN paths and multi-area OSPF are scoped for Phase 2.