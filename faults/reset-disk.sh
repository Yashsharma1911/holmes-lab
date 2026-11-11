#!/bin/sh
# Remove the filler file. If postgres is crash-looping, use a helper pod on the same node.
if kubectl exec -n shop deploy/postgres -- rm -f /var/lib/postgresql/data/sales-export.tmp 2>/dev/null; then
  echo "removed filler via postgres pod"
else
  kubectl run disk-fix -n shop --rm -i --restart=Never --image=busybox:1.36 \
    --overrides='{"spec":{"nodeSelector":{"demo.holmes/role":"hot"},"containers":[{"name":"disk-fix","image":"busybox:1.36","command":["rm","-f","/data/sales-export.tmp"],"volumeMounts":[{"name":"d","mountPath":"/data"}]}],"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"postgres-data"}}]}}'
fi
kubectl rollout restart deploy/postgres -n shop >/dev/null; kubectl rollout status deploy/postgres -n shop --timeout=3m
