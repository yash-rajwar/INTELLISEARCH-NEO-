# Office computer setup

Do this before the demo day, not on the morning. Keep the laptop as the primary machine.

1. Install Docker Desktop and Python 3.12. Give Docker 6 GB or more of memory.
2. Start Elasticsearch 9.0.0 (same version as the laptop). Choose a NEW password and bind to 127.0.0.1:
   `docker run -d --name es01 -p 127.0.0.1:9200:9200 -m 6g -e discovery.type=single-node -e ELASTIC_PASSWORD=<your-password> -e xpack.security.http.ssl.enabled=false docker.elastic.co/elasticsearch/elasticsearch:9.0.0`
3. Start the trial license: `POST _license/start_trial?acknowledge=true` (a trial is per cluster; this machine needs its own).
4. Create the ELSER endpoint `.elser-2-elasticsearch`. This needs internet once, and the first call takes about 30 s to 5 min.
5. Clone the repo, then `py -3.12 -m venv venv`, activate it, `pip install -r requirements-lock.txt` (exact versions; `requirements.txt` lists the direct ones).
   If pip fails on certificates, clear SSL_CERT_FILE, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE and PIP_CERT in that terminal.
6. Create `.env` with ES_URL, ES_USER, ES_PASSWORD. Never commit it.
7. `python scripts\download_corpus.py` (checks checksums).
8. `python ingest.py --path corpus\files --tier 1`, then tier 2 and 3 if time allows. Tier 1 took about 17 minutes on the laptop, the full corpus about an hour (about 2 chunks per second).
9. `python scripts\smoke_corpus.py` to check counts and the three search modes.
10. `python app.py`, then open http://127.0.0.1:5003 and rehearse the full script once.

## Fallback
If setup fails, present from the laptop, or show the recording and `/evaluation`.
