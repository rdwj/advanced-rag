# Redis

Redis is an in-memory data store used for caching, session management, pub/sub messaging, and rate limiting. Ideal for high-performance caching layers in RAG applications.

## Features

- Sub-millisecond latency for read/write operations
- Persistent storage with AOF and RDB
- Pub/Sub messaging for real-time updates
- Data structures: strings, hashes, lists, sets, sorted sets
- TTL-based expiration for cache management

## Directory Structure

```
redis/
├── local/                  # Local development setup
│   └── redis.sh            # Start/stop helper script
└── openshift/              # OpenShift deployment
    ├── kustomization.yaml  # Kustomize configuration
    ├── deployment.yaml     # Deployment manifest
    ├── service.yaml        # Service definition
    ├── secret.yaml         # Password secret
    └── pvc.yaml            # Persistent storage
```

## Local Development

### Quick Start

```bash
cd local
./redis.sh start            # Start on port 6379
./redis.sh status           # Check status
./redis.sh cli              # Open Redis CLI
```

### Commands

```bash
./redis.sh start    # Start Redis
./redis.sh stop     # Stop container
./redis.sh status   # Show status
./redis.sh logs     # View logs
./redis.sh destroy  # Stop and remove container (keeps data)
./redis.sh cli      # Open Redis CLI
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Port | 6379 | Redis port |
| Password | `dev-redis-password` | Authentication password |
| Data Dir | `local/data` | Persistent data location |
| Image | `bitnami/redis:latest` | Container image |

Override with environment variables:
```bash
REDIS_PASSWORD="your-password" ./redis.sh start
```

## OpenShift Deployment

### Quick Deploy

```bash
# Set namespace
NAMESPACE=redis

# Create namespace
oc new-project $NAMESPACE

# Deploy using Kustomize
oc apply -k openshift/ -n $NAMESPACE

# Wait for pod
oc wait --for=condition=Ready pods -l app=redis -n $NAMESPACE --timeout=120s

# Verify
oc get pods -l app=redis -n $NAMESPACE
```

### Production Configuration

Update the password before production use:

```bash
oc create secret generic redis-credentials \
  --from-literal=REDIS_PASSWORD="your-secure-password" \
  --from-literal=REDIS_URL="redis://:your-secure-password@redis:6379/0" \
  -n $NAMESPACE --dry-run=client -o yaml | oc apply -f -
oc rollout restart deployment/redis -n $NAMESPACE
```

### Connection Details

| Setting | Value |
|---------|-------|
| Host (internal) | `redis.$NAMESPACE.svc.cluster.local` |
| Port | `6379` |
| Password | See `redis-credentials` secret |

### Port Forward for Local Access

```bash
oc port-forward svc/redis 6379:6379 -n $NAMESPACE &
redis-cli -h localhost -p 6379 -a changeme-in-production
```

## Usage Examples

### Basic Operations

```bash
# Connect with redis-cli
redis-cli -h localhost -p 6379 -a $REDIS_PASSWORD

# Set/Get
SET mykey "Hello"
GET mykey

# Set with TTL (60 seconds)
SETEX cache:user:123 60 '{"name": "John"}'

# Check TTL
TTL cache:user:123
```

### Python Client

```python
import redis

# Connect
r = redis.Redis(
    host='localhost',
    port=6379,
    password='dev-redis-password',
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

r = redis.Redis(host='redis', port=6379, password='changeme', decode_responses=True)

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

For applications connecting to Redis:

```bash
export REDIS_HOST=redis
export REDIS_PORT=6379
export REDIS_PASSWORD=changeme-in-production
export REDIS_URL=redis://:changeme-in-production@redis:6379/0
```

Or use the secret in Kubernetes:

```yaml
envFrom:
  - secretRef:
      name: redis-credentials
```

## Use Cases in RAG

1. **Embedding Cache**: Cache generated embeddings to reduce API costs
2. **Query Cache**: Cache search results for frequently asked questions
3. **Session Storage**: Store user conversation context
4. **Rate Limiting**: Implement token bucket rate limiting for APIs
5. **Task Queue**: Queue document processing jobs (with RQ or Celery)
6. **Real-time Updates**: Pub/Sub for notifying when new documents are indexed

## Notes

- Redis is single-threaded; scale horizontally with Redis Cluster for high throughput
- AOF persistence is enabled by default for durability
- Memory usage scales with data size; monitor with `INFO memory`
- For production, consider Redis Sentinel or Redis Cluster for HA
- Default `maxmemory-policy` is `noeviction`; consider `allkeys-lru` for caches
