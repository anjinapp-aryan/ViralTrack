"""ViralTrack HTTP API, version 1 (D5).

Every request goes through the same layers as Python callers: `PlatformProvider` (validation, the approved
sorts, the 1,000,000 follower bound, the duration filter), the normalized model (`Content` refuses metrics
that are not ALLOWED) and `serialize` (only the v1 fields). `GuardedJSONResponse` then inspects the body
once more before it is sent. The API never calls the foundation directly, never exposes a foundation route,
spends no quota (no ingestion route exists here) and writes nothing.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from viraltrack.api import guard, schemas, serialize
from viraltrack.api.settings import ApiSettings, load_api_settings
from viraltrack.config import Settings, load_settings
from viraltrack.domain import (
    Capability,
    ConfigError,
    NotFound,
    Platform,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimited,
    RestrictedMetric,
    UnsupportedCapability,
)
from viraltrack.providers.base import DiscoveryQuery, PlatformProvider, SearchQuery
from viraltrack.providers.registry import build_providers
from viraltrack.providers.youtube.mapping import ORIGINS
from viraltrack.providers.youtube.metric_policy import RULES
from viraltrack.providers.youtube.provider import MAX_CREATOR_FOLLOWERS

API_VERSION = "1.0.0"
PAGE_SIZE_MAX = 100
# The provider returns one window of at most 1000 items (the foundation has no offset). Pages are cut from it.
RESULT_WINDOW = 1000
PERIOD_PATTERN = r"^(all|[1-9][0-9]{0,3}[hd])$"

log = logging.getLogger("viraltrack.api")

UNAVAILABLE = {
    Platform.INSTAGRAM: "No approved data source. Phase 0 found no legitimate discovery API for Instagram; "
    "the official Graph API covers only known professional accounts.",
    Platform.TIKTOK: "No approved data source. Phase 0 found no legitimate commercial discovery API "
    "for TikTok.",
}
CREATOR_SIZE = {
    "any": MAX_CREATOR_FOLLOWERS,
    "up_to_10k": 10_000,
    "up_to_100k": 100_000,
    "up_to_1m": MAX_CREATOR_FOLLOWERS,
}
DURATION = {"any": None, "up_to_3_min": True, "over_3_min": False}
APPROVED_SORTS = ("views", "published_at")
NOT_AVAILABLE_SORTS = {
    "engagement_rate": "the foundation orders hidden like counts as zero",
    "views_per_hour_lifetime": "the foundation ranks undated videos by a fabricated rate",
    "views_per_hour_24h": "no snapshot time is reported, so the recency of the rate is unknown",
    "views_gained_24h": "no snapshot time is reported, so the recency of the rate is unknown",
}
# Public capabilities of the v1 API (ingestion and other internal operations are not listed).
PUBLIC_CAPABILITIES = {
    Capability.DISCOVER_CONTENT: "Videos in the collected corpus, filtered by raw values",
    Capability.SEARCH_CONTENT: "Text search in the collected corpus",
    Capability.GET_CREATOR: "Creators already collected",
    Capability.SHORT_FORM: "Duration filter (at most 180 seconds); not the platform's Shorts classification",
    Capability.ENGAGEMENT_METRICS: "Likes and comments where the platform reports them",
    Capability.GLOBAL_TRENDING: "A platform-wide trending feed",
    Capability.HASHTAGS: "Hashtags",
    Capability.AUDIO: "Trending audio",
}

Sort = Literal["views", "published_at"]
Duration = Literal["any", "up_to_3_min", "over_3_min"]
CreatorSize = Literal["any", "up_to_10k", "up_to_100k", "up_to_1m"]


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None, headers=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details, self.headers = details or [], headers


class GuardedJSONResponse(JSONResponse):
    """Every body is checked by `guard.check` before it is encoded (fail closed)."""

    def render(self, content) -> bytes:
        guard.check(content)
        return super().render(content)


def _error(status: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    body = schemas.ErrorOut(error=schemas.ErrorBody(code=code, message=message, details=details or []))
    return GuardedJSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


_ERROR = {"model": schemas.ErrorOut}
ERRORS = {
    422: {**_ERROR, "description": "Invalid or unsupported request"},
    502: {**_ERROR, "description": "The provider answered with something unusable"},
    503: {**_ERROR, "description": "The provider is unavailable"},
    504: {**_ERROR, "description": "The provider timed out"},
}


def create_app(
    settings: Settings | None = None,
    api_settings: ApiSettings | None = None,
    providers: dict[Platform, PlatformProvider] | None = None,
    db_check: Callable[[], bool] | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    api_settings = api_settings or load_api_settings(environment=settings.environment)
    owned = providers is None
    providers = build_providers(settings) if owned else providers
    origin = ORIGINS[settings.youtube.data_origin]
    db_check = db_check or _database_check(settings)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if owned:
            for p in providers.values():
                p.close()

    app = FastAPI(
        title="ViralTrack API",
        version=API_VERSION,
        lifespan=lifespan,
        default_response_class=GuardedJSONResponse,
        description="Platform-neutral discovery over provider data. Only metrics the ViralTrack "
        "metric policy allows are part of this contract; unknown values are null.",
    )
    if api_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(api_settings.cors_origins),
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type", "X-Request-ID"],
            allow_credentials=False,
        )

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid = rid if len(rid) <= 64 and rid.isalnum() else uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        # path only: query strings may carry user search text
        log.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            )
        )
        return response

    _install_error_handlers(app)

    def provider_for(platform: str) -> PlatformProvider:
        p = Platform(platform)
        if p in UNAVAILABLE:
            raise ApiError(422, "platform_unavailable", f"{p.value} is not available: {UNAVAILABLE[p]}")
        if p not in providers:
            raise ApiError(503, "platform_disabled", f"{p.value} is disabled on this deployment")
        return providers[p]

    def meta(page_no, page_size, items, window, fetched, total, notes, sort) -> schemas.PageMeta:
        if len(items) > window:
            has_more = True
        elif fetched >= RESULT_WINDOW and len(items) >= RESULT_WINDOW:
            has_more = None
        else:
            has_more = False
        returned = len(items[(page_no - 1) * page_size : window])
        return schemas.PageMeta(
            platform="youtube",
            sort=sort,
            page=page_no,
            page_size=page_size,
            returned=returned,
            has_more=has_more,
            total=total,
            data_origin=origin.value,
            demo=serialize.is_demo(origin),
            notes=list(notes),
        )

    def window_of(page_no: int, page_size: int) -> tuple[int, int]:
        window = page_no * page_size
        if window > RESULT_WINDOW:
            raise ApiError(
                422,
                "page_out_of_range",
                f"page x page_size must be at most {RESULT_WINDOW}; narrow the filters instead",
                [schemas.ErrorDetail(field="page", message=f"at most {RESULT_WINDOW // page_size}")],
            )
        return window, min(window + 1, RESULT_WINDOW)

    def video_page(result, page_no, page_size, window, fetched, sort):
        items = list(result.items)
        data = [serialize.video(c) for c in items[(page_no - 1) * page_size : window]]
        return schemas.Page[schemas.Video](
            data=data, meta=meta(page_no, page_size, items, window, fetched, result.total, result.notes, sort)
        )

    # ---- health ----

    @app.get(
        "/api/v1/health",
        response_model=schemas.HealthOut,
        tags=["health"],
        summary="Liveness: the API process answers. Checks no dependency.",
    )
    def health():
        return schemas.HealthOut(status="ok", service="viraltrack-api", version=API_VERSION)

    @app.get(
        "/api/v1/health/ready",
        response_model=schemas.HealthOut,
        tags=["health"],
        responses={503: {"model": schemas.HealthOut, "description": "A required dependency is down"}},
        summary="Readiness: the providers' backends and, if configured, the database answer.",
    )
    def ready():
        checks = {}
        for platform, p in providers.items():
            try:
                ok = p.check_ready()
            except Exception:  # any failure means not ready; details go to the log only
                log.warning(json.dumps({"event": "readiness_failed", "check": platform.value}))
                ok = False
            checks[platform.value] = schemas.CheckOut(
                status="not_configured" if ok is None else "ok" if ok else "unavailable", required=True
            )
        checks["database"] = schemas.CheckOut(status=db_check_status(db_check), required=False)
        good = bool(providers) and all(c.status == "ok" for c in checks.values() if c.required)
        body = schemas.HealthOut(
            status="ready" if good else "not_ready",
            service="viraltrack-api",
            version=API_VERSION,
            checks=checks,
        )
        return GuardedJSONResponse(body.model_dump(mode="json"), status_code=200 if good else 503)

    # ---- capabilities ----

    @app.get(
        "/api/v1/capabilities",
        response_model=schemas.CapabilitiesOut,
        tags=["capabilities"],
        summary="Platforms, filters, sorts and metrics this deployment supports.",
    )
    def capabilities():
        platforms = []
        for p in Platform:
            if p in UNAVAILABLE:
                platforms.append(
                    schemas.PlatformOut(
                        platform=p.value,
                        available=False,
                        reason=UNAVAILABLE[p],
                        data_origin=None,
                        capabilities=[],
                    )
                )
                continue
            provider = providers.get(p)
            caps = provider.capabilities() if provider else None
            platforms.append(
                schemas.PlatformOut(
                    platform=p.value,
                    available=provider is not None,
                    reason=None if provider else "disabled on this deployment",
                    data_origin=origin.value if provider else None,
                    capabilities=[
                        schemas.CapabilityOut(name=c.value, supported=caps.supports(c), description=d)
                        for c, d in PUBLIC_CAPABILITIES.items()
                    ]
                    if caps
                    else [],
                )
            )
        return schemas.CapabilitiesOut(
            api_version="v1",
            platforms=platforms,
            filters=_filters(),
            page_size_max=PAGE_SIZE_MAX,
            result_window_max=RESULT_WINDOW,
            sorts=[schemas.SortOut(name=s, available=True) for s in APPROVED_SORTS]
            + [schemas.SortOut(name=s, available=False, reason=r) for s, r in NOT_AVAILABLE_SORTS.items()],
            metrics=_metrics(),
        )

    # ---- discovery ----

    @app.get(
        "/api/v1/discover",
        response_model=schemas.Page[schemas.Video],
        tags=["content"],
        responses=ERRORS,
        summary="Discover videos in the collected corpus, ordered by an approved raw sort.",
    )
    def discover(
        query: str | None = Query(
            None,
            min_length=1,
            max_length=200,
            description="optional topic text; uses text search (creator_size, "
            "min_views and region are then not supported)",
        ),
        period: str = Query("7d", pattern=PERIOD_PATTERN, description="all, or 1-9999 hours (h) or days (d)"),
        niche: str | None = Query(None, min_length=1, max_length=100),
        creator_size: CreatorSize = Query("any", description="maximum follower count; any = up to 1,000,000"),
        duration: Duration = Query("any", description="up_to_3_min: known length of at most 180 s"),
        region: str | None = Query(None, pattern=r"^[A-Z]{2}$"),
        min_views: int | None = Query(None, ge=0, le=10**12),
        sort: Sort = Query("views"),
        platform: schemas.PlatformName = Query("youtube"),
        page: int = Query(1, ge=1, le=RESULT_WINDOW),
        page_size: int = Query(24, ge=1, le=PAGE_SIZE_MAX),
    ):
        provider = provider_for(platform)
        window, fetched = window_of(page, page_size)
        if query is not None:
            unsupported = [
                n
                for n, v in (
                    ("creator_size", creator_size != "any"),
                    ("min_views", min_views),
                    ("region", region),
                )
                if v
            ]
            if unsupported:
                raise ApiError(
                    422,
                    "filter_not_supported_with_query",
                    "text search does not support these filters",
                    [schemas.ErrorDetail(field=n, message="not supported with query") for n in unsupported],
                )
            result = provider.search_content(
                SearchQuery(
                    text=query,
                    period=period,
                    limit=fetched,
                    short_form=DURATION[duration],
                    niche=niche,
                    sort=sort,
                )
            )
        else:
            result = provider.discover_content(
                DiscoveryQuery(
                    period=period,
                    limit=fetched,
                    short_form=DURATION[duration],
                    region=region,
                    niche=niche,
                    max_creator_followers=CREATOR_SIZE[creator_size],
                    min_views=min_views,
                    sort=sort,
                )
            )
        return video_page(result, page, page_size, window, fetched, sort)

    @app.get(
        "/api/v1/search",
        response_model=schemas.Page[schemas.Video],
        tags=["content"],
        responses=ERRORS,
        summary="Search videos in the collected corpus by topic text.",
    )
    def search(
        query: str = Query(..., min_length=1, max_length=200),
        period: str = Query("all", pattern=PERIOD_PATTERN),
        niche: str | None = Query(None, min_length=1, max_length=100),
        duration: Duration = Query("any"),
        sort: Sort = Query("views"),
        platform: schemas.PlatformName = Query("youtube"),
        page: int = Query(1, ge=1, le=RESULT_WINDOW),
        page_size: int = Query(24, ge=1, le=PAGE_SIZE_MAX),
    ):
        provider = provider_for(platform)
        window, fetched = window_of(page, page_size)
        result = provider.search_content(
            SearchQuery(
                text=query.strip() or query,
                period=period,
                limit=fetched,
                short_form=DURATION[duration],
                niche=niche,
                sort=sort,
            )
        )
        return video_page(result, page, page_size, window, fetched, sort)

    # ---- creators ----

    @app.get(
        "/api/v1/creators",
        response_model=schemas.Page[schemas.CreatorSummary],
        tags=["creators"],
        responses=ERRORS,
        summary="Creators of the discovered videos (the first 1000 videos by views for these filters).",
    )
    def creators(
        period: str = Query("30d", pattern=PERIOD_PATTERN),
        niche: str | None = Query(None, min_length=1, max_length=100),
        creator_size: CreatorSize = Query("any"),
        region: str | None = Query(None, pattern=r"^[A-Z]{2}$"),
        platform: schemas.PlatformName = Query("youtube"),
        page: int = Query(1, ge=1, le=RESULT_WINDOW),
        page_size: int = Query(24, ge=1, le=PAGE_SIZE_MAX),
    ):
        provider = provider_for(platform)
        window, _ = window_of(page, page_size)
        result = provider.discover_content(
            DiscoveryQuery(
                period=period,
                limit=RESULT_WINDOW,
                region=region,
                niche=niche,
                max_creator_followers=CREATOR_SIZE[creator_size],
                sort="views",
            )
        )
        seen: dict[str, list] = {}
        for c in result.items:
            seen.setdefault(c.creator.creator_id, []).append(c)
        groups = list(seen.values())
        full = len(result.items) >= RESULT_WINDOW
        notes = list(result.notes) + [
            "Creators are listed in the order of their most viewed video in the result; videos_in_result "
            "counts "
            "their videos among the discovered videos considered, not their whole channel."
        ]
        if full:
            notes.append(f"Only the first {RESULT_WINDOW} discovered videos were considered.")
        data = [
            schemas.CreatorSummary(creator=serialize.creator(g[0].creator), videos_in_result=len(g))
            for g in groups[(page - 1) * page_size : window]
        ]
        has_more = True if len(groups) > window else (None if full else False)
        m = schemas.PageMeta(
            platform="youtube",
            sort=None,
            page=page,
            page_size=page_size,
            returned=len(data),
            has_more=has_more,
            total=None if full else len(groups),
            data_origin=origin.value,
            demo=serialize.is_demo(origin),
            notes=notes,
        )
        return schemas.Page[schemas.CreatorSummary](data=data, meta=m)

    @app.get(
        "/api/v1/creators/{creator_id}",
        response_model=schemas.Item[schemas.CreatorDetail],
        tags=["creators"],
        responses={**ERRORS, 404: {**_ERROR, "description": "Unknown creator"}},
        summary="One creator already collected.",
    )
    def creator_detail(
        creator_id: str = Path(..., pattern=r"^[A-Za-z0-9_-]{1,64}$"),
        platform: schemas.PlatformName = Query("youtube"),
    ):
        provider = provider_for(platform)
        c = provider.get_creator(creator_id)
        detail = schemas.CreatorDetail(
            creator=serialize.creator(c),
            origin=origin.value,
            demo=serialize.is_demo(origin),
            notes=[
                "Listing a creator's videos is not available yet: the provider has no per-creator video "
                "list. Use /api/v1/discover or /api/v1/search."
            ],
        )
        return schemas.Item[schemas.CreatorDetail](data=detail)

    return app


def db_check_status(check: Callable[[], bool] | None) -> str:
    if check is None:
        return "not_configured"
    try:
        return "ok" if check() else "unavailable"
    except Exception:
        log.warning(json.dumps({"event": "readiness_failed", "check": "database"}))
        return "unavailable"


def _database_check(settings: Settings) -> Callable[[], bool] | None:
    """`SELECT 1` on the foundation database through the existing `viraltrack.database` connection code, when
    DATABASE_URL is set. The API reads no table; this only reports whether the store answers."""
    if not settings.database.url:
        return None

    def check() -> bool:
        from viraltrack.database import connect

        conn = connect(settings.database, attempts=1)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() == (1,)
        finally:
            conn.close()

    return check


def _filters() -> list[schemas.FilterOut]:
    both, disc = ["discover", "search"], ["discover", "creators"]
    return [
        schemas.FilterOut(
            name="query",
            type="string",
            description="topic text, 1 to 200 characters",
            applies_to=["search", "discover"],
        ),
        schemas.FilterOut(
            name="period",
            type="string",
            description="all, or 1-9999 hours (h) or days (d)",
            default="7d",
            applies_to=both + ["creators"],
        ),
        schemas.FilterOut(
            name="niche", type="string", description="a collection label", applies_to=both + ["creators"]
        ),
        schemas.FilterOut(
            name="creator_size",
            type="enum",
            values=list(CREATOR_SIZE),
            default="any",
            maximum=MAX_CREATOR_FOLLOWERS,
            description="maximum follower count; never unlimited",
            applies_to=disc,
        ),
        schemas.FilterOut(
            name="duration",
            type="enum",
            values=list(DURATION),
            default="any",
            description="known length of at most 180 s, or longer; not a Shorts classification",
            applies_to=both,
        ),
        schemas.FilterOut(
            name="region", type="string", description="ISO 3166-1 alpha-2 code", applies_to=disc
        ),
        schemas.FilterOut(
            name="min_views", type="integer", minimum=0, description="raw view count", applies_to=["discover"]
        ),
        schemas.FilterOut(
            name="page",
            type="integer",
            minimum=1,
            default=1,
            description=f"page x page_size at most {RESULT_WINDOW}",
            applies_to=both + ["creators"],
        ),
        schemas.FilterOut(
            name="page_size",
            type="integer",
            minimum=1,
            maximum=PAGE_SIZE_MAX,
            default=24,
            description="items per page",
            applies_to=both + ["creators"],
        ),
    ]


def _metrics() -> list[schemas.MetricOut]:
    rules = {r.name: r for r in RULES}
    raw = [
        ("views", "views as reported by the platform"),
        ("likes", "null when hidden by the creator"),
        ("comments", "comments as reported"),
        ("followers", "creator followers; null when hidden"),
        ("content_count", "creator uploads as reported"),
    ]
    out = [schemas.MetricOut(name=n, kind="raw", sortable=n == "views", description=d) for n, d in raw]
    out += [
        schemas.MetricOut(name=n, kind="derived", sortable=False, description=rules[n].basis)
        for n in serialize.DERIVED_FIELDS
    ]
    return out


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request, exc: ApiError):
        return _error(exc.status, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request, exc: StarletteHTTPException):
        # unknown paths and methods get the same envelope (and the same guard) as every other answer
        codes = {404: ("not_found", "not found"), 405: ("method_not_allowed", "method not allowed")}
        code, message = codes.get(exc.status_code, ("http_error", "request failed"))
        return _error(exc.status_code, code, message, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def invalid(_request, exc: RequestValidationError):
        # the offending input is not echoed back
        details = [
            schemas.ErrorDetail(
                field=".".join(str(x) for x in e.get("loc", ())[1:]) or None, message=e.get("msg", "invalid")
            )
            for e in exc.errors()
        ]
        return _error(422, "invalid_request", "the request parameters are invalid", details)

    @app.exception_handler(RestrictedMetric)
    async def restricted(_request, exc: RestrictedMetric):
        return _error(422, "restricted", "this value is not available under the metric policy")

    @app.exception_handler(UnsupportedCapability)
    async def unsupported(_request, exc: UnsupportedCapability):
        return _error(501, "unsupported", "the provider does not support this operation")

    @app.exception_handler(NotFound)
    async def not_found(_request, exc: NotFound):
        return _error(404, "not_found", "not found")

    @app.exception_handler(RateLimited)
    async def rate_limited(_request, exc: RateLimited):
        headers = {"Retry-After": str(exc.retry_after)} if getattr(exc, "retry_after", None) else None
        return _error(429, "rate_limited", "the provider asked to wait", headers=headers)

    @app.exception_handler(ProviderTimeout)
    async def timeout(_request, exc: ProviderTimeout):
        _log_provider(exc)
        return _error(504, "provider_timeout", "the provider did not answer in time")

    @app.exception_handler(ProviderUnavailable)
    async def unavailable(_request, exc: ProviderUnavailable):
        _log_provider(exc)
        return _error(503, "provider_unavailable", "the provider is unavailable")

    @app.exception_handler(ProviderError)
    async def provider_error(_request, exc: ProviderError):
        _log_provider(exc)
        return _error(502, "provider_error", "the provider returned an unusable answer")

    @app.exception_handler(ValidationError)
    async def schema_error(_request, exc: ValidationError):
        # a provider value that does not fit the v1 contract: a server-side problem, never echoed
        log.error(json.dumps({"event": "response_schema_error", "errors": exc.error_count()}))
        return _error(500, "internal_error", "internal error")

    @app.exception_handler(ValueError)
    async def value_error(_request, exc: ValueError):
        # raised by provider validation before any request; the text is ViralTrack's own
        return _error(422, "invalid_parameter", str(exc)[:300])

    @app.exception_handler(guard.PolicyViolation)
    async def violation(_request, exc: guard.PolicyViolation):
        log.error(json.dumps({"event": "policy_violation_blocked", "detail": str(exc)[:200]}))
        return _error(500, "policy_violation", "the response was withheld by the metric policy")

    @app.exception_handler(ConfigError)
    async def config_error(_request, exc: ConfigError):
        log.error(json.dumps({"event": "config_error"}))
        return _error(500, "configuration_error", "the service is misconfigured")

    @app.exception_handler(Exception)
    async def unexpected(_request, exc: Exception):
        log.error(json.dumps({"event": "unhandled_error", "type": type(exc).__name__}))
        return _error(500, "internal_error", "internal error")


def _log_provider(exc: ProviderError) -> None:
    # the message may name internal hosts; it stays in the server log
    log.warning(
        json.dumps(
            {
                "event": "provider_error",
                "type": type(exc).__name__,
                "provider": getattr(exc, "provider", None),
                "status": getattr(exc, "status", None),
            }
        )
    )
