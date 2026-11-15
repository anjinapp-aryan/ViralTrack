"""Run the pinned upstream niche-finder API in-process, offline, against a test schema.

NOT a test and NOT imported by ViralTrack. `tests/support/upstream.py` starts it with the interpreter
named by VT_TEST_UPSTREAM_PYTHON (a Python that has the upstream requirements installed).

Contract: stdin is JSON {"paths": ["/api/viral?period=all", ...]}; every path is requested with GET
through FastAPI's in-process TestClient (no socket, no uvicorn). stdout ends with one line
`RESULT:<json>` holding {"responses": [{"status", "body"}...], "network_attempts": n}.

Safety: YOUTUBE_API_KEY is removed, and `requests` (the only library upstream uses to reach YouTube) is
replaced by a guard that counts and refuses every call. A spending call would also fail on the missing key.
The upstream source is read, never written (PYTHONDONTWRITEBYTECODE is set by the caller).

Text embeddings: a search with a query embeds the query text with a local model that is downloaded on first
use. The offline job cannot download it, and a model cached on a developer machine made the result depend on
that machine. So `fastembed_provider.embed` is replaced by a fixed unit vector (no model, no download), as the
collect runner does. The seeded corpus stores no video embeddings, so upstream's similarity value stays null
either way and the response is the one the real model would give.
"""

import json
import os
import sys

os.environ.pop("YOUTUBE_API_KEY", None)
os.environ.pop("NF_MULTI_USER", None)

ATTEMPTS = []


def _refuse(*args, **kwargs):
    ATTEMPTS.append(str(args[:1]))
    raise RuntimeError("network access is forbidden in offline discovery tests")


import requests  # noqa: E402

requests.get = requests.post = requests.request = _refuse
requests.Session.request = _refuse
requests.sessions.Session.request = _refuse

backend = sys.argv[1]
sys.path.insert(0, backend)

import api  # noqa: E402  (creates/migrates the schema named by NICHE_DB_SCHEMA)
import infrastructure.embeddings.fastembed_provider as emb  # noqa: E402
import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _offline_embed(texts):
    vec = np.zeros(384, dtype=np.float32)  # the model's dimension; a unit vector, so cosine stays defined
    vec[0] = 1.0
    return vec.copy() if isinstance(texts, str) else [vec.copy() for _ in texts]


emb.embed = _offline_embed
emb._model = None  # any other path that would load the model now fails loudly instead of downloading it

payload = json.loads(sys.stdin.read())
client = TestClient(api.app, base_url="http://127.0.0.1")
responses = []
for path in payload["paths"]:
    if not path.startswith("/api/"):
        raise SystemExit(f"refusing non-API path {path!r}")
    resp = client.get(path)  # GET only: no route that spends quota is a GET
    try:
        body = resp.json()
    except ValueError:
        body = None
    responses.append({"status": resp.status_code, "body": body})
identity = {k: getattr(os, k)() if hasattr(os, k) else None for k in ("geteuid", "getegid")}
out = {"responses": responses, "network_attempts": len(ATTEMPTS),
       "uid": identity["geteuid"], "gid": identity["getegid"]}
print("RESULT:" + json.dumps(out), flush=True)
