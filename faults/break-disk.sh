#!/bin/sh
# Case 2: something fills the Postgres volume (a runaway export written next to PGDATA).
set -e
kubectl exec -n shop deploy/postgres -- sh -c 'dd if=/dev/zero of=/var/lib/postgresql/data/sales-export.tmp bs=4M 2>/dev/null || true; sync; df -h /var/lib/postgresql/data | tail -1'
