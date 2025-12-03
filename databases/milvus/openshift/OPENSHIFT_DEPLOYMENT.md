# Milvus Deployment on OpenShift (Helm)

This document covers deploying Milvus on OpenShift using the official Helm chart in standalone mode. This approach is simpler than the operator-based deployment and provides more direct control over configuration.

## Prerequisites

- OpenShift cluster with cluster-admin access (for SCC grants)
- Helm 3.x installed locally
- `oc` CLI configured with cluster access

## Quick Deploy (TL;DR)

```bash
# Create namespace
oc new-project advanced-rag || oc project advanced-rag

# CRITICAL: Grant SCC permissions BEFORE deploying
oc adm policy add-scc-to-user anyuid -z default -n advanced-rag
oc adm policy add-scc-to-user anyuid -z milvus-minio -n advanced-rag

# Add Helm repo
helm repo add milvus https://zilliztech.github.io/milvus-helm/
helm repo update milvus

# Install Milvus standalone with OpenShift-compatible values
helm install milvus milvus/milvus -n advanced-rag -f values-openshift.yaml

# Wait for pods
oc wait --for=condition=Ready pod -l app.kubernetes.io/instance=milvus -n advanced-rag --timeout=600s
```

## Full Installation Steps

### Step 1: Create Namespace

```bash
oc new-project advanced-rag || oc project advanced-rag
```

### Step 2: Grant OpenShift SCC Permissions (CRITICAL)

OpenShift's SecurityContextConstraints require explicit permissions for pods to run as specific users. **This must be done BEFORE deploying Milvus.**

```bash
# Grant anyuid SCC to service accounts that Milvus components will use
oc adm policy add-scc-to-user anyuid -z default -n advanced-rag
oc adm policy add-scc-to-user anyuid -z milvus-minio -n advanced-rag
```

### Step 3: Add Helm Repository

```bash
helm repo add milvus https://zilliztech.github.io/milvus-helm/
helm repo update milvus

# Verify chart availability
helm search repo milvus/milvus --versions | head -5
```

### Step 4: Create Values File

Create `values-openshift.yaml` with OpenShift-compatible settings:

```yaml
# Standalone mode (single-node deployment)
cluster:
  enabled: false

# etcd configuration
etcd:
  replicaCount: 1
  persistence:
    enabled: true
    size: 10Gi

# MinIO configuration (object storage)
minio:
  mode: standalone
  persistence:
    enabled: true
    size: 20Gi

# Disable Pulsar/Kafka messaging (not needed for standalone)
pulsar:
  enabled: false
pulsarv3:
  enabled: false
kafka:
  enabled: false

# Enable streaming with embedded woodpecker (lightweight alternative)
streaming:
  enabled: true
  woodpecker:
    embedded: true
    storage:
      type: minio

# OpenShift security contexts
securityContext:
  runAsNonRoot: true

containerSecurityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault

# Resource limits (adjust based on workload)
standalone:
  resources:
    requests:
      cpu: "1"
      memory: 4Gi
    limits:
      cpu: "4"
      memory: 8Gi
```

### Step 5: Deploy Milvus

```bash
# Install with custom values
helm install milvus milvus/milvus \
  -n advanced-rag \
  -f values-openshift.yaml

# Or install with inline values (no file needed)
helm install milvus milvus/milvus -n advanced-rag \
  --set cluster.enabled=false \
  --set etcd.replicaCount=1 \
  --set etcd.persistence.size=10Gi \
  --set minio.mode=standalone \
  --set minio.persistence.size=20Gi \
  --set pulsar.enabled=false \
  --set pulsarv3.enabled=false \
  --set kafka.enabled=false \
  --set streaming.enabled=true \
  --set streaming.woodpecker.embedded=true \
  --set streaming.woodpecker.storage.type=minio \
  --set securityContext.runAsNonRoot=true \
  --set containerSecurityContext.allowPrivilegeEscalation=false \
  --set 'containerSecurityContext.capabilities.drop[0]=ALL' \
  --set containerSecurityContext.seccompProfile.type=RuntimeDefault
```

### Step 6: Monitor Deployment

```bash
# Watch pods come up (typically takes 3-5 minutes)
oc get pods -n advanced-rag -w

# Expected pods:
# - milvus-etcd-0              (StatefulSet)
# - milvus-minio-*             (Deployment or StatefulSet)
# - milvus-standalone-*        (Deployment - Milvus server)

# Check Helm release status
helm status milvus -n advanced-rag

# View all resources created
helm get manifest milvus -n advanced-rag | oc get -f -
```

### Step 7: Verify Deployment

```bash
# Check health via port-forward
oc port-forward svc/milvus 9091:9091 -n advanced-rag &
curl http://localhost:9091/healthz        # Should return: OK
curl http://localhost:9091/api/v1/health  # Should return: {"status":"ok"}
kill %1

# Quick connectivity test with pymilvus
python3 -c "
from pymilvus import connections
connections.connect(host='localhost', port='19530')
print('Connected to Milvus!')
connections.disconnect('default')
"
```

## Troubleshooting

### Pods stuck in Pending / CreateContainerConfigError

**Symptom**: Events show SCC validation errors:
```
unable to validate against any security context constraint
```

**Solution**: Grant anyuid SCC to the affected service account:
```bash
# Check which service account the pod uses
oc get pod <pod-name> -n advanced-rag -o jsonpath='{.spec.serviceAccountName}'

# Grant SCC
oc adm policy add-scc-to-user anyuid -z <service-account-name> -n advanced-rag

# Delete the stuck pod to trigger recreation
oc delete pod <pod-name> -n advanced-rag
```

### etcd fails to start

**Symptom**: etcd pod in CrashLoopBackOff with permission errors.

**Solution**: The etcd StatefulSet may need the anyuid SCC:
```bash
oc adm policy add-scc-to-user anyuid -z milvus-etcd -n advanced-rag
oc delete pod milvus-etcd-0 -n advanced-rag
```

### MinIO fails with permission denied

**Symptom**: MinIO pod cannot write to data directory.

**Solution**: Ensure the minio service account has anyuid:
```bash
oc adm policy add-scc-to-user anyuid -z milvus-minio -n advanced-rag
```

### Check Pod Logs

```bash
# Milvus standalone
oc logs deployment/milvus-standalone -n advanced-rag --tail=100

# etcd
oc logs milvus-etcd-0 -n advanced-rag --tail=100

# MinIO
oc logs -l app.kubernetes.io/name=minio -n advanced-rag --tail=100
```

### Helm Rollback

If deployment fails, rollback to previous state:
```bash
helm rollback milvus 1 -n advanced-rag
```

## Service Endpoints

With Helm deployment, service names are simpler than operator-based deployment:

| Service | Internal URL | Port |
|---------|-------------|------|
| Milvus gRPC | `milvus.advanced-rag.svc.cluster.local` | 19530 |
| Milvus Metrics | `milvus.advanced-rag.svc.cluster.local` | 9091 |
| etcd | `milvus-etcd.advanced-rag.svc.cluster.local` | 2379 |
| MinIO | `milvus-minio.advanced-rag.svc.cluster.local` | 9000 |

**Note**: The main Milvus service is named `milvus`, NOT `milvus-standalone-milvus` (which is the operator naming convention).

## Environment Variables for Clients

```bash
export MILVUS_HOST="milvus.advanced-rag.svc.cluster.local"
export MILVUS_PORT="19530"
# Or as URI
export MILVUS_URI="http://milvus.advanced-rag.svc.cluster.local:19530"
```

## Upgrade

```bash
# Update Helm repo
helm repo update milvus

# Upgrade with new values
helm upgrade milvus milvus/milvus -n advanced-rag -f values-openshift.yaml

# Or upgrade to specific version
helm upgrade milvus milvus/milvus -n advanced-rag \
  --version 4.2.0 \
  -f values-openshift.yaml
```

## Cleanup

```bash
# Uninstall Milvus (keeps PVCs by default)
helm uninstall milvus -n advanced-rag

# Delete PVCs if you want to remove all data
oc delete pvc -l app.kubernetes.io/instance=milvus -n advanced-rag

# Delete namespace entirely
oc delete project advanced-rag

# Remove SCC grants (optional, cleaned up with namespace deletion)
oc adm policy remove-scc-from-user anyuid -z default -n advanced-rag
oc adm policy remove-scc-from-user anyuid -z milvus-minio -n advanced-rag
```

## Version Information

Tested with:
- OpenShift 4.14+
- Milvus Helm Chart 5.0.8
- Milvus 2.6.6
- etcd (bundled with chart)
- MinIO (bundled with chart)

## Comparison: Helm vs Operator

| Aspect | Helm Chart | Milvus Operator |
|--------|-----------|-----------------|
| Complexity | Simpler | More complex |
| Service naming | `milvus` | `<cr-name>-milvus` |
| Upgrades | `helm upgrade` | Modify CR, operator reconciles |
| Dependencies | Bundled in chart | Operator manages separately |
| cert-manager | Not required | Required |
| Best for | Standalone, simple setups | Multi-tenant, managed lifecycle |

This repository uses the Helm approach for simplicity and predictable service naming.
