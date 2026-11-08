# Cluster facts

Verified on the demo laptop, November 2026.

## Elasticsearch

- Version 9.0.0, single node, running in Docker (container `es01`).
- Data lives in the Docker volume `elastic-stack_esdata`. **Never** run `docker volume rm` or `docker compose down -v`.
- Cluster health is yellow: one replica cannot be assigned on a single node. This is harmless.
- Licence: trial, active until 2026-12-07 08:02 UTC. ELSER needs a trial or paid licence.
- The `es01` container is published on `0.0.0.0:9200` and uses the default `elastic` password. Present on a trusted network or a phone hotspot. After the demo, rebind to `127.0.0.1:9200`.

## ELSER

- Inference endpoint `.elser-2-elasticsearch`, field `content_semantic` (`semantic_text`).
- First call after idle: about 30 s. Warm calls: well under 1 s, but a warm call can still time out (HTTP 408 was seen once). Open the warm-up page before presenting.
- ELSER is English-only.

## Indexes

| Index | Role | Notes |
|---|---|---|
| `intellisearch_corpus_v1` | default search scope | 7,102 passages, 18 documents; `file_type` stored as `pdf` (no dot) |
| `intellisearch_showcase_chunks_v3` | user uploads | chunks can be deleted per document from the library |
| legacy indexes | hidden unless `LEGACY_ENABLED=true` | never modified |
| `zz_elser_probe` | scratch index | delete only after explicit approval |

## Machine learning memory and rerank (checked 2026-11-08)

- Elasticsearch reported about 2,460 MB of machine-learning memory; the ELSER deployment used about 2,100 MB of it.
- The rerank inference endpoint exists, but using it failed with "Model definition truncated. Unable to deserialize
  trained model definition". Reranking is therefore off.
- Do not start extra model deployments on this cluster before the demo.

## Known behaviour

- Weighted retriever format is rejected by 9.0.0 (HTTP 400); weighted RRF is fused locally.
- A one-off test run took 94 s; normal runs take about 1 to 2 s.
- Chunk sizes in the corpus: median about 1,250 to 1,340 characters, maximum 1,399, no mid-word cuts.

## Rebuilding

The corpus can be rebuilt with `ingest.py` (about one hour). See `docs/OFFICE_SETUP.md` for setting up Elasticsearch on another machine.
