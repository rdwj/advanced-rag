# Valkey

In-memory data store for caching, session management, pub/sub messaging, and rate limiting. Valkey is the Linux Foundation fork of Redis, fully API-compatible while being truly open source (BSD-3 license).

Part of [databases](../README.md).

## Why Valkey?

- **Open Source**: BSD-3 license, maintained by Linux Foundation
- **Redis Compatible**: Drop-in replacement, same commands and protocols
- **Active Development**: Community-driven with major cloud provider support
- **Same Performance**: Sub-millisecond latency, same data structures

## Features

- Sub-millisecond latency for read/write operations
- Persistent storage with AOF and RDB
- Pub/Sub messaging for real-time updates
- Data structures: strings, hashes, lists, sets, sorted sets
- TTL-based expiration for cache management

## Local Development

### Quick Start

```bash
cd local
./valkey.sh start            # Start on port 6379
./valkey.sh status           # Check status
./valkey.sh cli              # Open Valkey CLI
```

### Commands

```bash
./valkey.sh start    # Start Valkey
./valkey.sh stop     # Stop container
./valkey.sh status   # Show status
./valkey.sh logs     # View logs
./valkey.sh destroy  # Stop and remove container (keeps data)
./valkey.sh cli      # Open Valkey CLI
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Port | 6379 | Valkey port |
| Password | `dev-valkey-password` | Authentication password |
| Data Dir | `local/data` | Persistent data location |
| Image | `bitnami/valkey:latest` | Container image |

Override with environment variables:
```bash
VALKEY_PASSWORD="your-password" ./valkey.sh start
```

## OpenShift Deployment

### Quick Deploy

```bash
# Set namespace
NAMESPACE=valkey

# Create namespace
oc new-project $NAMESPACE

# Deploy using Kustomize
oc apply -k openshift/ -n $NAMESPACE

# Wait for pod
oc wait --for=condition=Ready pods -l app=valkey -n $NAMESPACE --timeout=120s

# Verify
oc get pods -l app=valkey -n $NAMESPACE
```

### Production Configuration

Update the password before production use:

```bash
oc create secret generic valkey-credentials \
  --from-literal=VALKEY_PASSWORD="your-secure-password" \
  --from-literal=VALKEY_URL="redis://:your-secure-password@valkey:6379/0" \
  -n $NAMESPACE --dry-run=client -o yaml | oc apply -f -
oc rollout restart deployment/valkey -n $NAMESPACE
```

### Connection Details

| Setting | Value |
|---------|-------|
| Host (internal) | `valkey.$NAMESPACE.svc.cluster.local` |
| Port | `6379` |
| Password | See `valkey-credentials` secret |

### Port Forward for Local Access

```bash
oc port-forward svc/valkey 6379:6379 -n $NAMESPACE &
valkey-cli -h localhost -p 6379 -a changeme-in-production
# or use redis-cli (same protocol)
redis-cli -h localhost -p 6379 -a changeme-in-production
```

## Usage Examples

### Basic Operations

```bash
# Connect with valkey-cli (or redis-cli)
valkey-cli -h localhost -p 6379 -a $VALKEY_PASSWORD

# Set/Get
SET mykey "Hello"
GET mykey

# Set with TTL (60 seconds)
SETEX cache:user:123 60 '{"name": "John"}'

# Check TTL
TTL cache:user:123
```

### Python Client

Valkey uses the same `redis` Python library:

```python
import redis

# Connect (same as Redis)
r = redis.Redis(
    host='localhost',
    port=6379,
    password='dev-valkey-password',
    decode_responses=True
)

# Basic operations
r.set('key', 'value')
value = r.get('key')

# With TTL (seconds)
r.setex('cache:result', 300, 'cached_value')

# Hash operations
r.hset('user:123', mapping={'name': 'John', 'email': 'john@example.com'})
user = r.hgetall('user:123')

# List operations (for queues)
r.lpush('task_queue', 'task1', 'task2')
task = r.rpop('task_queue')
```

### Caching Pattern for RAG

```python
import redis
import json
import hashlib

r = redis.Redis(host='valkey', port=6379, password='changeme', decode_responses=True)

def get_cached_embedding(text: str, ttl: int = 3600):
    """Cache embeddings to avoid redundant API calls."""
    cache_key = f"embedding:{hashlib.sha256(text.encode()).hexdigest()[:16]}"

    # Check cache
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    # Generate embedding (expensive operation)
    embedding = generate_embedding(text)

    # Cache with TTL
    r.setex(cache_key, ttl, json.dumps(embedding))
    return embedding

def cache_search_results(query: str, results: list, ttl: int = 300):
    """Cache search results for repeated queries."""
    cache_key = f"search:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
    r.setex(cache_key, ttl, json.dumps(results))
```

### Pub/Sub for Real-time Updates

```python
# Publisher
r.publish('rag:updates', json.dumps({'type': 'new_document', 'id': 'doc123'}))

# Subscriber
pubsub = r.pubsub()
pubsub.subscribe('rag:updates')

for message in pubsub.listen():
    if message['type'] == 'message':
        data = json.loads(message['data'])
        print(f"Received: {data}")
```

## Environment Variables

For applications connecting to Valkey:

```bash
export VALKEY_HOST=valkey
export VALKEY_PORT=6379
export VALKEY_PASSWORD=changeme-in-production
export VALKEY_URL=redis://:changeme-in-production@valkey:6379/0
```

Or use the secret in Kubernetes:

```yaml
envFrom:
  - secretRef:
      name: valkey-credentials
```

## Use Cases in RAG

1. **Embedding Cache**: Cache generated embeddings to reduce API costs
2. **Query Cache**: Cache search results for frequently asked questions
3. **Session Storage**: Store user conversation context
4. **Rate Limiting**: Implement token bucket rate limiting for APIs
5. **Task Queue**: Queue document processing jobs (with RQ or Celery)
6. **Real-time Updates**: Pub/Sub for notifying when new documents are indexed

## Migration from Redis

Valkey is a drop-in replacement for Redis:

1. **Same Protocol**: Uses `redis://` connection URLs
2. **Same Library**: Use the `redis` Python package
3. **Same Commands**: All Redis commands work unchanged
4. **Same Port**: Default port 6379

To migrate, simply change your service hostname from `redis` to `valkey`.

## Notes

- Valkey is single-threaded; scale horizontally with Valkey Cluster for high throughput
- AOF persistence is enabled by default for durability
- Memory usage scales with data size; monitor with `INFO memory`
- For production, consider Valkey Sentinel or Valkey Cluster for HA
- Default `maxmemory-policy` is `noeviction`; consider `allkeys-lru` for caches
