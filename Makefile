# Holmes lab: the three failure cases. Run `source .env` first.
.PHONY: status break-neighbor reset-neighbor break-disk reset-disk stage-volumes break-volumes reset-volumes reset forward alerts

status:
	kubectl get pods -n shop -o wide

# Case 2: noisy neighbor (CPU); shown as a video on stage
break-neighbor:  ## starts on the next whole minute
	kubectl apply -f faults/neighbor.yaml
reset-neighbor:
	-kubectl delete cronjob report-batch -n shop --ignore-not-found
	-kubectl delete job -n shop -l app=report-batch --ignore-not-found

# Case 1: Postgres volume fills up
break-disk:
	./faults/break-disk.sh
reset-disk:
	./faults/reset-disk.sh

# Case 3: per-node volume limit (15 on DOKS). Stage 15 BEFORE the talk; attaching takes minutes.
stage-volumes:
	kubectl scale sts/receipts -n shop --replicas=15
	kubectl rollout status sts/receipts -n shop --timeout=20m
break-volumes:
	kubectl scale sts/receipts -n shop --replicas=16
reset-volumes:
	kubectl scale sts/receipts -n shop --replicas=15
	-kubectl delete pvc data-receipts-15 -n shop --ignore-not-found

reset: reset-neighbor reset-volumes
	-./faults/reset-disk.sh

# Port-forwards HolmesGPT uses (Prometheus 9090, Alertmanager 9093, Loki 3100, Grafana 3000)
forward:
	kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-prometheus 9090 & \
	kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-alertmanager 9093 & \
	kubectl port-forward -n monitoring svc/loki 3100 & \
	kubectl port-forward -n monitoring svc/kps-grafana 3000:80 & \
	wait

# HolmesGPT: on stage, type these commands directly (they are what these targets run).
# .env puts holmes on PATH and sets HOLMES_CONFIGPATH_DIR, so holmes/config.yaml is the default config.
# holmes ask needs --refresh-toolsets in 0.46 or the Prometheus tools are missing; investigate rejects the flag.
ask-neighbor:
	holmes ask "checkout-api in namespace shop got slow in the last few minutes and every pod is Running. Why?" --refresh-toolsets --no-interactive
ask-disk:
	holmes ask "checkout is failing in namespace shop. Find the root cause." --refresh-toolsets --no-interactive
investigate-alerts:
	holmes investigate alertmanager --alertmanager-alertname ReceiptsPodStuckPending

# Firing alerts for the shop namespace (from Alertmanager via make forward)
alerts:
	@curl -s localhost:9093/api/v2/alerts | jq -r '.[] | select(.labels.namespace=="shop" or (.labels.alertname|test("Receipts|Checkout"))) | "FIRING  \(.labels.alertname)  \(.annotations.summary // "")"'
