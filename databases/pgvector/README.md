# PGVector with Podman

Spin up a local PostgreSQL instance with the pgvector extension using Podman.

## Quick start

1. Adjust `.env` if you want different credentials than the defaults in `.env.example`.
2. Start the container:
   ```sh
   podman compose up -d
   ```
3. Check that it is healthy:
   ```sh
   podman ps --filter name=pgvector
   podman logs -f pgvector
   ```
4. Connect and confirm the extension is available:
   ```sh
   podman exec -it pgvector psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
   -- inside psql
   \\dx
   ```

## Usage snippets (for your RAG agent)

- Connection: host `localhost`, port `5432`, db `$POSTGRES_DB`, user `$POSTGRES_USER`, password `$POSTGRES_PASSWORD`.
- Create a table for embeddings (example 1536-dim OpenAI):
  ```sql
  CREATE TABLE docs (
    id bigserial PRIMARY KEY,
    content text,
    embedding vector(1536)
  );
  CREATE INDEX docs_embedding_idx ON docs USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
  ```
- Insert data:
  ```sql
  INSERT INTO docs (content, embedding)
  VALUES ('hello world', '[0.01, 0.02, ...]');
  ```
- Similarity search:
  ```sql
  SELECT id, content
  FROM docs
  ORDER BY embedding <-> '[0.01, 0.02, ...]'
  LIMIT 5;
  ```
- psql one-liners:
  ```sh
  podman exec -it pgvector psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "SELECT COUNT(*) FROM docs;"
  ```
- Reset data (drops volume): `podman compose down -v && podman volume ls` (to confirm removal).

## Notes

- Image: `docker.io/pgvector/pgvector:pg17`
- Defaults: `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=vector` (set in `.env`)
- Data persists in the `pgvector-data` volume managed by Compose; find/remove it with `podman volume ls` and `podman volume rm <name>` (likely `pgvector_pgvector-data`).
- The `initdb/01_enable_pgvector.sql` script runs on first start to enable the extension in the default database.
