# holmes-lab

Demo lab for the KubeCon NA 2026 talk *Following the Evidence with HolmesGPT*.
A small shop app on DigitalOcean Kubernetes with three planted faults.

## Setup

```bash
cp .env.example .env              # fill in the DO token and inference key
cp /path/to/kubeconfig.yaml kubeconfig.yaml
source .env
python3.12 -m venv .venv && .venv/bin/pip install holmesgpt==0.46.0
```

### Cluster (once)

```bash
# monitoring on the ops pool
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm install kps prometheus-community/kube-prometheus-stack --version 93.1.2 -n monitoring --create-namespace -f monitoring/prom-values.yaml
helm install loki grafana/loki --version 7.6.0 -n monitoring -f monitoring/loki-values.yaml
helm install promtail grafana/promtail --version 6.17.1 -n monitoring -f monitoring/promtail-values.yaml
kubectl apply -f monitoring/shop-dashboard.yaml

# the app: label two shop nodes, then deploy
kubectl label node <shop-node-1> demo.holmes/role=hot
kubectl label node <shop-node-2> demo.holmes/role=receipts
kubectl apply -f shop/shop.yaml
kubectl create configmap checkout-code -n shop --from-file=shop/checkout.py
make stage-volumes                # 15 receipts volumes; takes a few minutes
```

## Every session

```bash
# tab 1, leave running
source .env && make forward

# tab 2
source .env
kubectl get pods -n shop          # 19 pods, all Running
```

Grafana: http://localhost:3000/d/shop-checkout (admin / holmes-demo)

## Case 1: Postgres volume full

```bash
make break-disk
kubectl logs -n shop deploy/checkout-api --since=30s
# wait ~75s
holmes ask "checkout is failing in namespace shop. Find the root cause." --refresh-toolsets --no-interactive
make reset-disk
```

## Case 2: noisy neighbor

```bash
make break-neighbor
# wait ~2 min for CheckoutHighLatency
holmes ask "checkout-api in namespace shop got slow in the last few minutes and every pod is Running. Why?" --refresh-toolsets --no-interactive
make reset-neighbor
```

## Case 3: per-node volume limit

```bash
make break-volumes
kubectl get pods -n shop receipts-15
make alerts                       # repeat until FIRING ReceiptsPodStuckPending (~80s)
holmes investigate alertmanager --alertmanager-alertname ReceiptsPodStuckPending
make reset-volumes
```

## Health check and reset

```bash
kubectl get pods -n shop
kubectl get sts receipts -n shop
kubectl logs -n shop deploy/checkout-api --since=30s   # empty = healthy
make alerts
make reset
```

## Recordings

```bash
python3 recordings/humanize.py recordings/case*.src
vhs recordings/case1.tape
```
