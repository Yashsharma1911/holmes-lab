# Holmes lab: demo runbook

Cluster: DOKS `weekend-project` (nyc3). Six `s-2vcpu-2gb` nodes: 3 in `ops` (monitoring), 3 in `shop`.

| Node | Role |
|---|---|
| `shop-3e12ej` | "hot" node: `checkout-api` x2 and `postgres` (1 GB DO volume) |
| `shop-3e12eo` | `receipts` StatefulSet, 15 pods with 15 DO volumes (the per-node limit), plus `loadgen` |
| `ops-*` | Prometheus, Alertmanager, Grafana (admin / holmes-demo), Loki, Promtail |

`loadgen` sends about 8 to 9 checkouts/sec. Healthy baseline: p50 about 40ms, p99 0.1 to 0.2s, 0 errors.

## Setup (once per terminal)

```bash
cd holmes-lab
source .env              # kubeconfig, DO token, MODEL, LLM key, holmes on PATH, config dir
make forward             # in its own tab: Prometheus :9090, Alertmanager :9093, Loki :3100, Grafana :3000
```

Before going on stage: `make reset`, then check that `kubectl get pods -n shop` shows 15 receipts pods, all Running.

## Model and tested runs (Nov 10, late evening)

- **LLM:** DigitalOcean serverless inference, model `anthropic-claude-sonnet-5.5`. It's called through LiteLLM's OpenAI-compatible path (`MODEL=openai/anthropic-claude-sonnet-5.5`, `OPENAI_API_BASE=https://inference.do-ai.run/v1`). All of this is set in `.env`.
- **Plain `holmes` commands, no wrapper.** `.env` sets `MODEL` (HolmesGPT reads it) and `HOLMES_CONFIGPATH_DIR=holmes`, so `holmes/config.yaml` is the default config. That config holds the toolsets, the custom DO toolset, the skills path and `alertmanager_url`. `holmes ask` still needs `--refresh-toolsets` in 0.46. Without it the Prometheus toolset shows as enabled from cache, but its query tools aren't loaded, so the model gets "could not find tool execute_prometheus_instant_query" (seen in rehearsal). `holmes investigate alertmanager` rejects that flag; case 3 doesn't need Prometheus.
- **`holmes/skills/shop-service-map/SKILL.md`** is a HolmesGPT skill: the service map, the key metric names and the answer format. It's the kind of runbook a team gives its agent. HolmesGPT loads it when a question is about namespace `shop`. Without that context the model guesses metric names.
- **bash tool:** HolmesGPT tried `kubectl exec ... df` and the CLI **denied it**, because unapproved commands are refused in non-interactive mode. That's the real-world proof for the "read-only" guardrail.
- **gpt-oss-120b** (the first key's only model) misdiagnosed the disk case (case 1) and then hung. Don't use it.

| Case | Command | Time | Result |
|---|---|---|---|
| 1 disk | `holmes ask "checkout is failing in namespace shop. Find the root cause." --refresh-toolsets --no-interactive`, about 75s after the break | 79s, 18 tools | Correct: PVC `postgres-data` full (kubelet_volume_stats_available_bytes = 0), errors in both checkout and postgres logs, ~780 MB jump, other PVCs fine. Fix: expand the PVC. May speculate about report-batch, because Loki still has logs from the noisy-neighbor runs (labelled unconfirmed). |
| 3 volumes | `holmes investigate alertmanager --alertmanager-alertname ReceiptsPodStuckPending`, once `ReceiptsPodStuckPending` fires (~80s) | 23s, 7 tools | Correct: nodeSelector allows only shop-3e12eo, CSINode allocatable 15, 15 receipts PVCs in use, autoscaler NotTriggerScaleUp, and the custom `doks_node_pools` tool shows the pool fixed at 3 nodes with no autoscaling. Fixes: label another node, add or autoscale nodes, redesign the volumes. |
| 2 neighbor | `holmes ask "checkout-api in namespace shop got slow ..." --refresh-toolsets --no-interactive`, once `CheckoutHighLatency` fires (~140s) | 58s, 15 tools | Correct: the report-batch CronJob (1 CPU request, no limit, 4 busy loops) is starving checkout on shop-3e12ej, and checkout CPU falls from ~0.14 to ~0.06 cores. That run had no service map; rerun with it for a recording that shows latency. |

Saved outputs are in `runs/` (`case*-sonnet.txt`, `case2-final.txt`).

## Case 1: Postgres volume fills up (live, first demo)

`make break-disk` writes `sales-export.tmp` into the Postgres volume until it is 100% full.

- Tested: about 75% of checkouts fail with `could not extend file ... No space left on device`. Within about 1 minute Postgres PANICs on checkpoint and loops in crash recovery. The container stays Running but goes NotReady, so you see `0/1 Running` and 0 restarts.
- Alerts: `CheckoutErrorRate` fires. `KubePersistentVolumeFillingUp` and `KubePodNotReady` go pending.
- Ask: `holmes ask "checkout is failing in namespace shop. Find the root cause." --refresh-toolsets --no-interactive`
- Expected trail: checkout error logs in Loki or the pod logs, then Postgres logs (No space left on device / PANIC), then `kubelet_volume_stats_available_bytes{persistentvolumeclaim="postgres-data"}` = 0, then the PVC is 1Gi on `do-block-storage`. Fix: expand the PVC (the DO storage class allows volume expansion) and find what wrote the file.
- Note: kubelet volume stats refresh every 1 to 2 minutes, so wait about 60 seconds after the break before asking.
- Reset: `make reset-disk` (about 8 seconds, back to 0 errors)

## Case 2: noisy neighbor (played as a video)

`make break-neighbor`. The CronJob `report-batch` starts at the next full minute. It requests 1 CPU, has no limit, and burns 4 cores next to checkout.

- Tested: p99 went from about 0.1s to 2.4s and p50 to 0.67s. The hot node's CPU reached 99%. `CheckoutHighLatency` fired after about 1 minute. Every checkout pod stayed Running.
- Ask: `holmes ask "checkout-api in namespace shop got slow in the last few minutes and every pod is Running. Why?" --refresh-toolsets --no-interactive`
- Expected trail: checkout latency metrics, then the checkout pods are on `shop-3e12ej`, then node CPU is about 100%, then the `report-batch` pod on the same node with a 1-CPU request and no limit, then a CronJob running every minute.
- On stage: play `recordings/case2-noisy-neighbor.mp4` (97s, embedded in the deck). Hidden slide 15 has the live commands if you want to run it instead (3 to 4 minutes).
- Reset: `make reset-neighbor`

## Case 3: per-node volume limit (live, alert-driven)

`make break-volumes` scales `receipts` from 15 to 16.

- Tested: `receipts-15` stays Pending. The PodScheduled condition says "0/6 nodes are available: **1 node(s) exceed max volume count**, 5 node(s) didn't match Pod's node affinity/selector". `kubectl get csinode shop-3e12eo` shows allocatable 15 for `dobs.csi.digitalocean.com`. VolumeAttachments show 15 attached to that node.
- Caveat: `kubectl describe pod` only shows the earlier "unbound immediate PersistentVolumeClaims" event, because the event is deduplicated. The real reason is in `.status.conditions`. HolmesGPT reading that is a nice moment.
- `ReceiptsPodStuckPending` fires after about 1 minute. Then run `holmes investigate alertmanager --alertmanager-alertname ReceiptsPodStuckPending` (the Alertmanager URL comes from the config).
- Expected trail: the alert, then the pod condition, then the CSINode limit, then VolumeAttachments on `shop-3e12eo`, then `doks_node_pools` (custom DO toolset) shows the `shop` pool is fixed at 3 nodes with autoscaling off. Fix: spread receipts across nodes (drop the nodeSelector, add topology spread), use fewer and larger volumes, or add nodes.
- Reset: `make reset-volumes` (deletes PVC 15 and its DO volume)

## Things to know

- **The DO token only has the Kubernetes scope.** Droplet and volume API calls return 403. That's why the custom toolset reads node pools, and the VolumeAttachment objects stand in for the volume API.
- **The API server dropped connections (EOF) during the Helm installs.** It might happen again on stage. Keep the recordings ready.
- **Teardown:** destroy the cluster, delete leftover DO volumes (Volumes page), and delete both API tokens (API, then Tokens).

## Recordings

`recordings/case*.src` are the scripts and `python3 recordings/humanize.py recordings/case*.src` turns them into VHS tapes, with uneven typing speed, pauses and the odd corrected typo. Then `vhs recordings/caseN.tape`. Waits for alerts and volume stats are cut.
