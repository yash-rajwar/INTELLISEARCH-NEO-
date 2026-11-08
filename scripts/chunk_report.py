import random, statistics
from collections import defaultdict
from pathlib import Path
import requests

END_CHARS = ".!?\"')]\u201d\u2019"

def read_env():
    values = {}
    p = Path(".env")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values

env = read_env()
url = env.get("ES_URL", "http://localhost:9200").rstrip("/")
index = env.get("CORPUS_INDEX", "intellisearch_corpus_v1")
s = requests.Session()
s.trust_env = False
s.auth = (env.get("ES_USER", "elastic"), env.get("ES_PASSWORD", ""))

body = {"size": 1000, "sort": ["_doc"], "query": {"match_all": {}},
        "_source": ["title", "page_number", "chunk_index", "content"]}
r = s.post(f"{url}/{index}/_search?scroll=2m", json=body, timeout=60)
r.raise_for_status()
data = r.json()
sid = data["_scroll_id"]
docs = defaultdict(list)
while data["hits"]["hits"]:
    for h in data["hits"]["hits"]:
        docs[h["_source"]["title"]].append(h["_source"])
    r = s.post(f"{url}/_search/scroll", json={"scroll": "2m", "scroll_id": sid}, timeout=60)
    r.raise_for_status()
    data = r.json()
    sid = data.get("_scroll_id", sid)

random.seed(7)
print(f"{'document':42} {'n':>5} {'min':>5} {'med':>5} {'max':>5} {'<400':>5} {'no-end':>6} {'lower-start':>11}")
for title, chunks in sorted(docs.items()):
    texts = [c["content"].strip() for c in chunks]
    lens = [len(t) for t in texts]
    short = sum(1 for n in lens if n < 400)
    no_end = sum(1 for t in texts if t and t[-1] not in END_CHARS)
    lower = sum(1 for t in texts if t and t[0].islower())
    print(f"{title[:42]:42} {len(texts):5} {min(lens):5} {int(statistics.median(lens)):5} {max(lens):5} {short:5} {no_end:6} {lower:11}")

print("\nSamples (start ... end of 2 random chunks per document):")
for title, chunks in sorted(docs.items()):
    for c in random.sample(chunks, min(2, len(chunks))):
        t = c["content"].strip().replace("\r", " ").replace("\n", " ")
        print(f"- {title[:30]} p{c.get('page_number')} #{c.get('chunk_index')}: {t[:110]} ... {t[-80:]}")