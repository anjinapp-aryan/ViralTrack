"""AI Content Intelligence: classifier, format, country dimensions, corpus filters, opportunities, the
provider's read-only signal and market reads, the market collection, and the /api/v1/ai routes. Offline:
every foundation answer comes from synthetic fixtures through a mock transport; nothing can reach YouTube or
spend quota.
"""

from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import load_fixture
from viraltrack.api import create_app, guard
from viraltrack.api.settings import load_api_settings
from viraltrack.config import load_settings
from viraltrack.domain import Exposure, IngestionDisabled, Platform
from viraltrack.intelligence import corpus, opportunities
from viraltrack.intelligence.classifier import CLASSIFIER_VERSION, classify, classify_format, is_gaming
from viraltrack.intelligence.country import dimensions, market_label, market_of_slug
from viraltrack.intelligence.taxonomy import (
    AIStatus,
    Confidence,
    ContentCategory,
    ContentSignals,
    FormatType,
)
from viraltrack.providers.youtube import YouTubeProvider
from viraltrack.providers.youtube.metric_policy import RULES

NOW = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
INSPECT = load_fixture("ai_inspect.json")
NICHE_VIDEOS = load_fixture("ai_niche_videos.json")
UPSTREAM_ONLY = {
    "acceleration",
    "baselineMedianViews",
    "baselineMedianViewsPeriod",
    "estimatedRpm",
    "estimatedRpmRange",
    "isShort",
    "outlierBand",
    "outlierScore",
    "outlierScoreAgeAdjusted",
    "outlierScoreNexlev",
    "outlierScorePeriod",
    "outlierScoreRolling",
    "projected30dViews",
    "viewsPerSubscriber",
    "viralScore",
    "vph24h",
    "viewsGained24h",
    "snapshots",
    "quotaUsed",
    "containsSyntheticMedia",
    "tags",
    "fetchedFromApi",
}
ALL_STATUSES = "&".join(f"status={s.value}" for s in AIStatus)


def c(title, tags=(), category=None, seconds=None, signals=None):
    return classify(
        title=title,
        tags=tuple(tags),
        platform_category=category,
        duration_seconds=seconds,
        signals=signals,
        now=NOW,
    )


# ---- A. AI status ----------------------------------------------------------------------------------------


def test_platform_disclosure_confirms_ai_even_without_any_wording():
    r = c("Amma nanna jeeva", signals=ContentSignals(found=True, synthetic_disclosure=True))
    assert (r.status, r.confidence) == (AIStatus.CONFIRMED_AI, Confidence.HIGH)
    assert "platform_disclosure" in r.evidence_sources


def test_the_disclosure_flag_off_is_not_evidence_of_human_made_content():
    r = c("Morning routine vlog", signals=ContentSignals(found=True, synthetic_disclosure=False))
    assert r.status is AIStatus.UNKNOWN and r.category is ContentCategory.UNKNOWN
    assert any("off by default" in e for e in r.evidence)


def test_creator_statement_with_a_tool_is_confirmed_and_alone_is_likely():
    both = c("AI generated song made with #suno")
    assert (both.status, both.confidence) == (AIStatus.CONFIRMED_AI, Confidence.HIGH)
    alone = c("This video was made with AI")
    assert (alone.status, alone.confidence) == (AIStatus.LIKELY_AI, Confidence.HIGH)


@pytest.mark.parametrize(
    "title",
    [
        "AI will change every job",  # the word AI only
        "Top 10 facts about AI",  # the word AI only
        "Suno Na Sajna | Romantic song",  # Hindi "suno" (listen), not the tool
        "Sora's birthday party",  # a name, not the tool
        "Luma the cat",
    ],
)
def test_the_word_ai_or_an_ambiguous_tool_word_alone_is_never_enough(title):
    r = c(title)
    assert r.status is AIStatus.UNKNOWN
    assert r.confidence is Confidence.NONE


@pytest.mark.parametrize(
    "title", ["Night city #sora", "Made with Sora - neon city", "Veo 3 dragon flight", "Kling AI dance"]
)
def test_an_unambiguous_tool_mention_is_likely(title):
    r = c(title)
    assert r.status is AIStatus.LIKELY_AI and r.confidence is Confidence.MEDIUM
    assert any(e.startswith("generation tool named") for e in r.evidence)


def test_one_label_is_possible_two_labels_are_likely():
    one = c("Winter story #aimusic")
    assert (one.status, one.confidence) == (AIStatus.POSSIBLY_AI, Confidence.LOW)
    two = c("Winter story #aimusic #aianimation")
    assert two.status is AIStatus.LIKELY_AI


def test_a_tutorial_about_ai_tools_is_only_possibly_ai():
    r = c("How to make AI songs with Suno AI - full tutorial")
    assert r.status is AIStatus.POSSIBLY_AI and "about AI tools" in r.reason


def test_a_creator_negation_is_not_ai_and_contradictions_stay_unknown():
    neg = c("Real singer, no AI used - acoustic")
    assert (neg.status, neg.category) == (AIStatus.NOT_AI, ContentCategory.NORMAL_NON_AI)
    mixed = c("No AI used #aimusic #suno")
    assert mixed.status is AIStatus.UNKNOWN and "contradictory" in mixed.reason


def test_creator_tags_are_evidence_and_are_attributed_to_tags():
    r = c("Amma", signals=ContentSignals(found=True, tags=("ai generated", "suno ai")))
    assert r.status is AIStatus.CONFIRMED_AI
    assert "creator_tags" in r.evidence_sources and "title" not in r.evidence_sources


def test_every_classification_carries_version_time_reason_and_sources():
    r = c("Dragon #aivideo #runway", seconds=200)
    assert r.classifier_version == CLASSIFIER_VERSION and r.classified_at == NOW
    assert r.reason and r.category_reason and r.evidence_sources and r.evidence


# ---- B. content category ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, category, expected",
    [
        ("AI music video made with Kling AI", "Music", ContentCategory.AI_MUSIC_VIDEO),
        ("Lo-fi beats 1 hour - AI generated instrumental", "Music", ContentCategory.AI_MUSIC_AUDIO),
        ("New track #suno #aisong", None, ContentCategory.AI_MUSIC_AUDIO),
        (
            "AI short film with epic background music #aivideo",
            "Film & Animation",
            ContentCategory.AI_VIDEO_WITH_MUSIC,
        ),
        ("Why cats purr - AI generated animation", "Education", ContentCategory.AI_NORMAL_VIDEO),
        ("ಹೊಸ ಹಾಡು AI generated #aimusic", None, ContentCategory.UNKNOWN),
    ],
)
def test_categories(title, category, expected):
    r = c(title, category=category)
    assert r.status in (AIStatus.CONFIRMED_AI, AIStatus.LIKELY_AI)
    assert r.category is expected, r.category_reason


def test_unknown_status_never_gets_an_ai_category():
    assert c("Morning vlog", category="Music").category is ContentCategory.UNKNOWN


# ---- C. format -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seconds, live, title, expected, confidence",
    [
        (19, None, "Clip #shorts", FormatType.SHORT_FORM, Confidence.MEDIUM),
        (120, None, "Clip", FormatType.SHORT_FORM, Confidence.LOW),
        (180, None, "Clip", FormatType.SHORT_FORM, Confidence.LOW),
        (181, None, "Clip #shorts", FormatType.LONG_FORM, Confidence.HIGH),
        (3600, None, "Mix", FormatType.LONG_FORM, Confidence.HIGH),
        (None, None, "Clip", FormatType.UNKNOWN, Confidence.NONE),
        (0, None, "Clip", FormatType.UNKNOWN, Confidence.NONE),
        (None, "live", "Radio", FormatType.LIVE, Confidence.HIGH),
        (60, "upcoming", "Premiere", FormatType.LIVE, Confidence.HIGH),
    ],
)
def test_format(seconds, live, title, expected, confidence):
    f = classify_format(seconds, live, title, ())
    assert (f.format_type, f.format_confidence) == (expected, confidence)
    assert "Shorts flag" in f.reason or expected is not FormatType.SHORT_FORM


# ---- D. Gaming exclusion ---------------------------------------------------------------------------------


def test_gaming_is_excluded_by_category_or_by_gaming_tags():
    assert is_gaming("Gaming", "AI world", ())
    assert is_gaming("Entertainment", "World #minecraft", ())
    assert is_gaming(None, "World", ("Roblox",))
    assert not is_gaming("Music", "Game of hearts - AI song", ())
    assert c("Minecraft AI generated world", category="Gaming").excluded_reason


# ---- E. country dimensions -------------------------------------------------------------------------------


def test_country_dimensions_are_separate_and_never_inferred_from_language():
    d = dimensions((), None, "kn")
    assert d.creator_country is None and d.discovery_countries == () and d.language_code == "kn"
    d = dimensions(("IN", "KR", "IN", "bad"), "IN", "en-US")
    assert d.discovery_countries == ("IN", "KR") and d.discovery_source
    assert d.creator_country == "IN" and d.creator_country_confidence is Confidence.MEDIUM
    assert d.language_code == "en"
    assert dimensions((), "India", None).creator_country is None


def test_market_label_round_trips_through_the_data_source_slug_rule():
    import re

    label = market_label("IN", "kannada ai song")
    slug = re.sub(r"[^\w]+", "-", label.strip().lower()).strip("-")  # the foundation's slugify rule
    assert market_of_slug(slug) == "IN"
    assert market_of_slug("kannada-ai-song") is None
    with pytest.raises(ValueError):
        market_label("India", "x")


# ---- F. provider: read-only signals and markets, guarded market collection -------------------------------


class Foundation:
    def __init__(self):
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request):
        self.requests.append(request)
        path = request.url.path
        if path == "/api/health":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "hasApiKey": True,
                    "unitQuota": {"unitsLeft": 9000, "dailyLimit": 10000},
                    "searchQuota": {"callsLeft": 90, "dailyLimit": 100},
                },
            )
        if path == "/api/viral":
            return httpx.Response(200, json=load_fixture("ai_viral.json"))
        if path == "/api/inspect/video":
            body = INSPECT.get(request.url.params.get("video_id"))
            return httpx.Response(200, json=body) if body else httpx.Response(404, json={"detail": "nope"})
        if path == "/api/niches":
            return httpx.Response(200, json=load_fixture("ai_niches.json"))
        if path.startswith("/api/niches/") and path.endswith("/videos"):
            slug = path.split("/")[3]
            return httpx.Response(200, json=NICHE_VIDEOS.get(slug, {"videos": []}))
        if path == "/api/collect/niche":
            return httpx.Response(
                200, json={"niche": "x", "videosFound": 1, "videosStored": 1, "quotaUsed": 2}
            )
        return httpx.Response(404, json={"detail": "not here"})


def provider(nf, **env):
    s = load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "test", **env}
    )
    return YouTubeProvider(
        s.youtube, http_client=httpx.Client(transport=httpx.MockTransport(nf)), clock=lambda: NOW
    )


def test_signals_are_read_with_fetch_and_refresh_off_and_mapped():
    nf = Foundation()
    out = provider(nf).get_content_signals(["aiKnMusic03", "missingSig4", "bad id!"])
    s = out["aiKnMusic03"]
    assert s.found and s.synthetic_disclosure is True and s.creator_country == "IN"
    assert s.tags == ("emotional", "kannada song") and s.live_status == "none"
    assert out["missingSig4"].found is False and out["bad id!"].found is False
    inspected = [r for r in nf.requests if r.url.path == "/api/inspect/video"]
    assert len(inspected) == 2  # the invalid id is never sent
    assert all(
        r.method == "GET" and r.url.params["fetch"] == "false" and r.url.params["refresh"] == "false"
        for r in inspected
    )


def test_signals_are_cached_in_memory():
    nf = Foundation()
    p = provider(nf)
    p.get_content_signals(["aiKnMusic01"])
    p.get_content_signals(["aiKnMusic01"])
    assert sum(r.url.path == "/api/inspect/video" for r in nf.requests) == 1


def test_discovery_markets_come_only_from_viraltrack_market_niches():
    nf = Foundation()
    m = provider(nf).discovery_markets()
    assert m["aiKnMusic03"] == ("IN", "KR") and m["aiKoSong007"] == ("KR",)
    assert not any("/api/niches/music" in str(r.url) for r in nf.requests)


def test_market_collection_is_disabled_by_default_and_guarded():
    nf = Foundation()
    with pytest.raises(IngestionDisabled):
        provider(nf).collect_market("IN", "kannada ai song")
    assert not nf.requests
    with pytest.raises(ValueError):
        provider(nf, VT_YOUTUBE_INGESTION_ENABLED="true").collect_market("India", "x")
    assert not nf.requests


def test_market_collection_stores_under_the_market_label():
    nf = Foundation()
    p = provider(
        nf,
        VT_YOUTUBE_INGESTION_ENABLED="true",
        VT_YOUTUBE_QUOTA_FLOOR_UNITS="0",
        VT_YOUTUBE_QUOTA_FLOOR_SEARCH_CALLS="0",
    )
    p.collect_market("IN", "kannada ai song")
    body = next(r for r in nf.requests if r.url.path == "/api/collect/niche")
    import json

    sent = json.loads(body.content)
    assert sent["label"] == "vt-market-in kannada ai song" and sent["region"] == "IN"


# ---- G. corpus, filters and opportunities ----------------------------------------------------------------


@pytest.fixture
def items():
    nf = Foundation()
    p = provider(nf)
    from viraltrack.providers.base import DiscoveryQuery

    page = p.discover_content(DiscoveryQuery(period="30d", limit=500))
    contents = list(page.items)
    built = corpus.build(
        contents, p.get_content_signals([x.content_id for x in contents]), p.discovery_markets(), NOW
    )
    return built


def test_corpus_excludes_gaming_and_counts_missing_signals(items):
    kept = corpus.included(items)
    assert len(items) - len(kept) == 1
    assert not any(i.content.content_id == "gameMine009" for i in kept)
    assert sum(not i.signals_found for i in items) == 1


def test_combined_filters(items):
    kept = corpus.included(items)
    f = corpus.Filters(
        statuses=(AIStatus.CONFIRMED_AI, AIStatus.LIKELY_AI),
        categories=(ContentCategory.AI_MUSIC_VIDEO,),
        formats=(FormatType.SHORT_FORM,),
        creator_countries=("IN",),
        languages=("kn",),
    )
    got = {i.content.content_id for i in corpus.apply(kept, f)}
    assert got == {"aiKnMusic01", "aiKnMusic02", "aiKnMusic03"}
    unknown = corpus.apply(kept, corpus.Filters(creator_countries=("unknown",)))
    assert {i.content.content_id for i in unknown} == {"plainVlog10", "missingSig4"}
    kr = corpus.apply(kept, corpus.Filters(discovery_countries=("KR",)))
    assert {i.content.content_id for i in kr} == {"aiKoSong007", "aiKnMusic03"}


def test_opportunities_need_enough_items_and_cite_recurring_themes(items):
    ai = corpus.apply(
        corpus.included(items), corpus.Filters(statuses=(AIStatus.CONFIRMED_AI, AIStatus.LIKELY_AI))
    )
    found = opportunities.find(ai, "creator", 3)
    assert len(found) == 1
    o = found[0]
    assert (o.category, o.format_type, o.language_code, o.country) == (
        ContentCategory.AI_MUSIC_VIDEO,
        FormatType.SHORT_FORM,
        "kn",
        "IN",
    )
    assert o.item_count == 3 and dict(o.themes)["amma"] == 3 and dict(o.themes)["emotional"] == 3
    assert "Kannada" in o.summary and "collected corpus" in o.summary
    brief = o.brief
    assert brief["generated_by"] == "template" and len(brief["rights_checklist"]) >= 5
    text = " ".join(str(v) for v in brief.values())
    for e in o.evidence:  # no supporting title is copied into the brief
        assert e.content.title not in text


def test_opportunities_by_discovery_market(items):
    ai = corpus.apply(corpus.included(items), corpus.Filters(statuses=tuple(AIStatus)))
    found = opportunities.find(ai, "discovery", 3)
    assert [(o.country, o.item_count) for o in found] == [("IN", 3)]


# ---- H. API ----------------------------------------------------------------------------------------------


def client(origin="test"):
    s = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": origin})
    nf = Foundation()
    http = httpx.Client(transport=httpx.MockTransport(nf))
    providers = {Platform.YOUTUBE: YouTubeProvider(s.youtube, http_client=http, clock=lambda: NOW)}
    app = create_app(s, load_api_settings({}), providers=providers, db_check=lambda: None)
    return TestClient(app, raise_server_exceptions=False), nf


def keys(body):
    if isinstance(body, dict):
        return set(body) | set().union(*(keys(v) for v in body.values()))
    if isinstance(body, list):
        return set().union(*(keys(v) for v in body)) if body else set()
    return set()


AI_URLS = [
    "/api/v1/ai/content?period=30d",
    f"/api/v1/ai/content?period=30d&{ALL_STATUSES}",
    f"/api/v1/ai/summary?period=30d&{ALL_STATUSES}",
    "/api/v1/ai/countries?period=30d",
    "/api/v1/ai/countries?period=30d&basis=discovery",
    "/api/v1/ai/opportunities?period=30d&min_items=2",
]


@pytest.mark.parametrize("url", AI_URLS)
def test_no_restricted_or_upstream_only_key_reaches_an_ai_response(url):
    tc, nf = client()
    r = tc.get(url)
    assert r.status_code == 200, r.text
    found = keys(r.json())
    assert not found & UPSTREAM_ONLY
    assert not found & {x.name for x in RULES if x.exposure is not Exposure.ALLOWED}
    guard.check(r.json())
    # read-only: every foundation request is a GET, and inspection never fetches from YouTube
    assert all(q.method == "GET" for q in nf.requests)
    assert all(
        q.url.params.get("fetch") == "false" for q in nf.requests if q.url.path == "/api/inspect/video"
    )


def test_ai_content_defaults_to_confirmed_and_likely_and_excludes_gaming():
    tc, _ = client()
    body = tc.get("/api/v1/ai/content?period=30d&page_size=100").json()
    statuses = {v["classification"]["status"] for v in body["data"]}
    assert statuses <= {"CONFIRMED_AI", "LIKELY_AI"}
    ids = {v["video"]["id"] for v in body["data"]}
    assert "gameMine009" not in ids and "tutSunoAi12" not in ids
    assert body["meta"]["excluded_gaming"] == 1 and body["meta"]["signals_missing"] == 1
    assert body["meta"]["total"] == len(ids) == 7


def test_ai_content_combined_filters_and_sort():
    tc, _ = client()
    url = (
        "/api/v1/ai/content?period=30d&category=AI_MUSIC_VIDEO&format=short_form&creator_country=IN"
        "&language=kn&sort=published_at"
    )
    data = tc.get(url).json()["data"]
    assert [v["video"]["id"] for v in data] == ["aiKnMusic03", "aiKnMusic02", "aiKnMusic01"]
    first = data[0]
    assert first["country"]["discovery_countries"] == ["IN", "KR"]
    assert first["country"]["creator_country_source"] == "creator_declared_channel_country"
    assert first["format"]["format_type"] == "short_form" and first["classification"]["evidence"]


def test_unknown_country_and_language_can_be_selected():
    tc, _ = client()
    data = tc.get(f"/api/v1/ai/content?period=30d&creator_country=unknown&{ALL_STATUSES}").json()["data"]
    assert {v["video"]["id"] for v in data} == {"plainVlog10", "missingSig4"}


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/ai/content?creator_country=India",
        "/api/v1/ai/content?language=Kannada",
        "/api/v1/ai/content?status=AI",
        "/api/v1/ai/content?category=GAMING",
        "/api/v1/ai/content?format=shorts",
        "/api/v1/ai/content?sort=engagement_rate",
        "/api/v1/ai/content?sort=views_per_hour_lifetime",
        "/api/v1/ai/countries?basis=audience",
        "/api/v1/ai/opportunities?min_items=1",
    ],
)
def test_invalid_ai_requests_are_refused_before_the_foundation_is_asked(url):
    tc, nf = client()
    assert tc.get(url).status_code == 422
    assert not nf.requests


def test_summary_counts_the_corpus_by_every_dimension():
    tc, _ = client()
    s = tc.get("/api/v1/ai/summary?period=30d").json()
    by = {k: {c["key"]: c["count"] for c in s[k]} for k in s if k.startswith("by_")}
    assert s["matching"] == 7
    assert by["by_status"]["UNKNOWN"] >= 3 and "gameMine009" not in str(s)
    assert by["by_category"]["AI_MUSIC_VIDEO"] == 3
    assert by["by_format"] == {"short_form": 5, "long_form": 2}
    assert by["by_creator_country"]["IN"] == 3 and by["by_discovery_country"]["unknown"] == 3
    assert any("not the platform" in n for n in s["meta"]["notes"])
    assert s["recent"][0]["video"]["id"] == "aiKoSong007"


def test_countries_by_creator_and_by_discovery_market():
    tc, _ = client()
    rows = {r["country"]: r for r in tc.get("/api/v1/ai/countries?period=30d").json()["data"]}
    assert rows["IN"]["items"] == 3 and {c["key"] for c in rows["IN"]["by_language"]} == {"kn"}
    market = tc.get("/api/v1/ai/countries?period=30d&basis=discovery&country=KR").json()["data"]
    assert [(r["country"], r["items"]) for r in market] == [("KR", 2)]


def test_opportunities_endpoint_returns_a_brief_and_evidence():
    tc, _ = client()
    body = tc.get("/api/v1/ai/opportunities?period=30d").json()
    assert len(body["data"]) == 1
    o = body["data"][0]
    assert o["item_count"] == 3 and o["brief"]["language_code"] == "kn"
    assert {e["id"] for e in o["evidence"]} == {"aiKnMusic01", "aiKnMusic02", "aiKnMusic03"}
    assert o["evidence"][0]["views"]["kind"] == "raw"


@pytest.mark.parametrize("origin, demo", [("test", True), ("demo", True)])
def test_synthetic_data_is_labelled(origin, demo):
    tc, _ = client(origin)
    meta = tc.get("/api/v1/ai/summary?period=30d").json()["meta"]
    assert meta["demo"] is demo and meta["data_origin"] == origin


def test_ai_routes_are_documented_in_openapi():
    tc, _ = client()
    paths = tc.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/ai/content", "/api/v1/ai/summary", "/api/v1/ai/countries", "/api/v1/ai/opportunities"):
        assert set(paths[p]) == {"get"}
        assert {"200", "422", "502", "503", "504"} <= set(paths[p]["get"]["responses"])
    sort = {x["name"]: x for x in paths["/api/v1/ai/content"]["get"]["parameters"]}["sort"]
    assert sort["schema"]["enum"] == ["views", "published_at"]
