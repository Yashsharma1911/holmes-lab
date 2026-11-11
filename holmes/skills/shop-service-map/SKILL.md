---
name: shop-service-map
description: Service map, key metrics and answer format for the shop namespace (checkout-api, postgres, receipts, loadgen). Use for any question or alert about namespace shop.
---

## Service map
loadgen -> checkout-api (Deployment, 2 replicas) -> postgres (Deployment, data on PVC postgres-data, DigitalOcean block storage).
receipts is a StatefulSet with one PVC per pod.

## Key Prometheus metrics
- Checkout latency: checkout_request_duration_seconds_bucket (histogram)
- Checkout outcomes: checkout_requests_total, status ok or error
- Node CPU: node_cpu_seconds_total from node-exporter (instance label is node IP:9100)
- Container CPU: container_cpu_usage_seconds_total
- Volume space: kubelet_volume_stats_available_bytes and kubelet_volume_stats_capacity_bytes by persistentvolumeclaim

## Answer format
Keep the final answer short enough for one screen: the root cause in one sentence first, then at most 6 evidence bullets and at most 3 fix steps.
