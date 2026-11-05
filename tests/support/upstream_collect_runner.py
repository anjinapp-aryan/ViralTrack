"""Run the REAL upstream `POST /api/collect/niche` route offline, with every YouTube call replaced by a fake.

NOT a test and NOT imported by ViralTrack; started by `tests/support/upstream.py` with the interpreter
named by VT_TEST_UPSTREAM_PYTHON. It exercises the real route, the real `collecting.collect_niche`, the real
period parser
and the real storage, and replaces only what would reach YouTube:

  * `infrastructure.youtube.client.search_videos`, `videos_list`, `channels_list` -> deterministic fakes that
    record
    their arguments (the `published_after` the foundation would have sent to search.list);
  * the text-embedding model -> none (no model download).

Safety: `requests` (the only library upstream uses to reach YouTube) is replaced by a guard that counts and
refuses every call, and the parent asserts zero attempts. The key set below is a placeholder that satisfies
the route's
"is a key configured" check; because every YouTube function is replaced it is never sent anywhere.

stdin JSON: {"calls": [{"body": {...}}, ...], "pages_available": 3, "per_page": 2}
stdout last line: RESULT:{"results": [...], "niches": [...], "network_attempts": n}
"""

import json
import os
import sys
import time

os.environ["YOUTUBE_API_KEY"] = "offline-test-placeholder-not-a-real-key"
os.environ.pop("NF_MULTI_USER", None)

ATTEMPTS = []


def _refuse(*args, **kwargs):
    ATTEMPTS.append(str(args[:1]))
    raise RuntimeError("network access is forbidden in offline collection tests")


import requests  # noqa: E402

requests.get = requests.post = requests.request = _refuse
requests.Session.request = _refuse
requests.sessions.Session.request = _refuse

sys.path.insert(0, sys.argv[1])

import api  # noqa: E402
import infrastructure.postgres as db  # noqa: E402
import infrastructure.youtube.client as yt  # noqa: E402
from application import collecting  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

payload = json.loads(sys.stdin.read())
PAGES = int(payload.get("pages_available", 1))
PER_PAGE = int(payload.get("per_page", 2))
STUB_CALLS = []


def vid(n: int) -> str:
    return f"D2V{n:08d}"  # 11 characters, like a real video id


def fake_search_videos(
    api_key,
    query,
    published_after=None,
    published_before=None,
    relevance_language=None,
    region_code=None,
    video_category_id=None,
    order="viewCount",
    max_results=50,
    page_token=None,
    video_duration=None,
    channel_id=None,
):
    STUB_CALLS.append(
        {
            "fn": "search_videos",
            "query": query,
            "published_after": published_after,
            "published_before": published_before,
            "order": order,
            "region_code": region_code,
            "relevance_language": relevance_language,
            "page_token": page_token,
            "video_category_id": video_category_id,
            "video_duration": video_duration,
            "max_results": max_results,
        }
    )
    page = int(page_token or 0)
    start = page * (PER_PAGE - 1)  # each later page repeats the previous page's last id
    items = [{"id": {"videoId": vid(start + i)}} for i in range(PER_PAGE)]
    out = {"items": items}
    if page + 1 < PAGES:
        out["nextPageToken"] = str(page + 1)
    return out


def fake_videos_list(api_key, video_ids, parts=None, **kwargs):
    STUB_CALLS.append({"fn": "videos_list", "count": len(video_ids)})
    return [
        {
            "id": v,
            "snippet": {
                "title": f"Synthetic {v}",
                "description": "",
                "channelId": "UCD2C" + "0" * 19,
                "publishedAt": "2026-10-30T12:00:00Z",
                "categoryId": "27",
            },
            "statistics": {"viewCount": "1000", "likeCount": "10", "commentCount": "1"},
            "contentDetails": {"duration": "PT10M"},
        }
        for v in video_ids
    ]


def fake_channels_list(api_key, channel_ids, parts=None, **kwargs):
    STUB_CALLS.append({"fn": "channels_list", "count": len(channel_ids)})
    return [
        {
            "id": c,
            "snippet": {"title": "Synthetic channel"},
            "statistics": {"subscriberCount": "500", "videoCount": "5", "viewCount": "5000"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UUsynthetic"}},
        }
        for c in channel_ids
    ]


class NoEmbeddings:
    """`store_videos` embeds titles unless told not to; keep the model out of the offline run."""

    @staticmethod
    def embed(text):
        return None

    @staticmethod
    def to_blob(vec):
        return None


yt.search_videos = fake_search_videos
yt.videos_list = fake_videos_list
yt.channels_list = fake_channels_list
collecting._EMB = NoEmbeddings

client = TestClient(api.app, base_url="http://127.0.0.1", raise_server_exceptions=False)
results = []
for call in payload["calls"]:
    mark = len(STUB_CALLS)
    before = time.time()
    resp = client.post("/api/collect/niche", json=call["body"])
    after = time.time()
    try:
        body = resp.json()
    except ValueError:
        body = None
    results.append(
        {
            "status": resp.status_code,
            "body": body,
            "before": before,
            "after": after,
            "stub_calls": STUB_CALLS[mark:],
        }
    )

conn = db.get_conn()
niches = [dict(r) for r in conn.execute("SELECT slug, query, label FROM niches ORDER BY slug").fetchall()]
for n in niches:
    n["videos"] = conn.execute(
        "SELECT count(*) AS c FROM video_niches WHERE niche_slug = ?", (n["slug"],)
    ).fetchone()["c"]
conn.close()
print(
    "RESULT:" + json.dumps({"results": results, "niches": niches, "network_attempts": len(ATTEMPTS)}),
    flush=True,
)
