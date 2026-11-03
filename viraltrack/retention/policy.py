"""Data classification and retention rules for the niche-finder database.

niche-finder keeps everything it collects ("Nothing is deleted", upstream
backend/application/freshness.py). YouTube API Services Developer Policies
III.E.4 do not allow that: non-authorized statistics may be stored for at most
30 days, and other API data must be refreshed or deleted after 30 days. With an
accepted "Analytics & Reporting" amendment, statistics may be kept for 36
months, but titles, names and descriptions still follow the 30-day rule.

Every upstream table is classified below. `tests/test_retention_policy.py`
fails when the pinned upstream schema gains a table this file does not cover,
so an upstream upgrade cannot silently add unmanaged data.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DataClass(str, Enum):
    RAW_PROVIDER_DATA = "RAW_PROVIDER_DATA"
    DERIVED_DATA = "DERIVED_DATA"
    IDENTIFIER = "IDENTIFIER"
    CACHE = "CACHE"
    TEMPORARY_DATA = "TEMPORARY_DATA"
    USER_GENERATED_DATA = "USER_GENERATED_DATA"


class Window(str, Enum):
    STATS = "stats"   # 30 days, or 36 months with the accepted amendment
    TEXT = "text"     # always 30 days


class Action(str, Enum):
    PURGE = "purge"          # the retention job deletes or strips rows by age
    CASCADE = "cascade"      # deleted together with the video/channel it belongs to
    KEEP = "keep"            # not provider data, or owned by another rule
    REVIEW = "review"        # kept for now; open compliance question (see DATA_RETENTION_POLICY.md)


@dataclass(frozen=True)
class TableRule:
    classes: tuple[DataClass, ...]
    action: Action
    reason: str


R, D, IDN, C, T, U = (DataClass.RAW_PROVIDER_DATA, DataClass.DERIVED_DATA, DataClass.IDENTIFIER,
                    DataClass.CACHE, DataClass.TEMPORARY_DATA, DataClass.USER_GENERATED_DATA)

TABLES: dict[str, TableRule] = {
    # --- YouTube API data ---------------------------------------------------
    "videos": TableRule((R, D, IDN), Action.PURGE,
                        "Titles, descriptions, tags and counts from videos.list; embeddings and "
                        "labels derived from them. Row deleted once not refreshed for 30 days."),
    "channels": TableRule((R, D, IDN), Action.PURGE,
                          "Channel profile and counts from channels.list; LLM labels derived. "
                          "Row deleted once not refreshed for 30 days."),
    "video_stats_history": TableRule((R,), Action.PURGE,
                                     "View/like/comment snapshots (stats window); the title and "
                                     "thumbnail copies in each row follow the text window."),
    "channel_stats_history": TableRule((R,), Action.PURGE, "Subscriber/view snapshots (stats window)."),
    "chart_snapshots": TableRule((R,), Action.PURGE, "chart=mostPopular captures (stats window)."),
    "chart_entries": TableRule((R,), Action.PURGE, "Chart ranks and view counts (stats window)."),
    "video_changes": TableRule((R,), Action.PURGE, "Old and new titles/thumbnails (text window)."),
    "video_categories": TableRule((R,), Action.PURGE, "Category names from videoCategories.list."),
    "thumbnail_archive": TableRule((R,), Action.PURGE,
                                   "Stored thumbnail image bytes (text window)."),
    "video_niches": TableRule((IDN, U), Action.CASCADE, "Links videos to user niches."),
    # --- derived from API data ----------------------------------------------
    "video_insights": TableRule((D, C), Action.PURGE, "LLM analyses of videos/comments."),
    "video_sponsors": TableRule((D, R), Action.PURGE,
                                "Brands found in descriptions; `evidence` quotes the description."),
    "sponsor_scan": TableRule((T,), Action.CASCADE, "Scan bookkeeping per video."),
    "niche_clusters": TableRule((D,), Action.PURGE, "k-means niche map with outlier aggregates."),
    "video_tags": TableRule((D, U), Action.CASCADE, "Manual and LLM tags on a video."),
    "llm_cache": TableRule((C, D), Action.PURGE, "Cached LLM results built from API data."),
    "events": TableRule((D,), Action.PURGE, "Alerts; payload holds titles and counts."),
    "alert_deliveries": TableRule((T,), Action.PURGE, "Which alerts were sent."),
    "gone_items": TableRule((IDN, T), Action.PURGE,
                            "Videos/channels the API stopped returning. Confirmed items have "
                            "their stored data deleted; the marker itself ages out."),
    "meta": TableRule((T, C), Action.REVIEW,
                      "Quota counters, schema version and short-lived caches. Keys are not "
                      "documented upstream; audit before production."),
    # --- the user's own channel (OAuth, Authorized Data) --------------------
    "own_channels": TableRule((IDN, U), Action.REVIEW,
                              "Connected channel + encrypted refresh token. Authorized Data: kept "
                              "while authorization is valid; must be re-verified every 30 days."),
    "own_channel_daily": TableRule((R,), Action.REVIEW, "YouTube Analytics data (authorized)."),
    "own_video_metrics": TableRule((R,), Action.REVIEW, "YouTube Analytics data (authorized)."),
    "own_oauth_pending": TableRule((T,), Action.KEEP, "Expiring OAuth state, upstream cleans it."),
    # --- user content -------------------------------------------------------
    "saved_items": TableRule((U, R), Action.PURGE,
                             "The user's saved item is kept; the metrics `payload` snapshot is "
                             "removed after the text window."),
    "drafts": TableRule((U,), Action.REVIEW,
                        "User drafts; `review` holds a snapshot of corpus statistics."),
    "tracked_channels": TableRule((U, IDN), Action.KEEP, "The user's watchlist (channel ids)."),
    "niches": TableRule((U,), Action.KEEP, "User-defined niche queries."),
    "user_topics": TableRule((U,), Action.KEEP, "Topics the user watches."),
    "cost_profiles": TableRule((U,), Action.KEEP, "User cost settings."),
    "transcript_requests": TableRule((U,), Action.KEEP, "User requests for transcripts."),
    "transcripts": TableRule((U,), Action.REVIEW,
                             "Transcripts pasted by the user from YouTube's UI (not API data)."),
    "transcript_chunks": TableRule((U, D), Action.REVIEW, "Chunks + embeddings of transcripts."),
    # --- accounts, billing, operations (not provider data) ------------------
    "users": TableRule((U,), Action.KEEP, "Accounts."),
    "email_tokens": TableRule((T,), Action.KEEP, "Expiring e-mail tokens."),
    "audit_log": TableRule((T,), Action.KEEP, "Security log, upstream NF_AUDIT_RETENTION_DAYS."),
    "sessions": TableRule((T,), Action.KEEP, "Sign-in sessions."),
    "login_attempts": TableRule((T,), Action.KEEP, "Rate-limit bookkeeping."),
    "user_settings": TableRule((U,), Action.KEEP, "User settings."),
    "user_prefs": TableRule((U,), Action.KEEP, "User preferences."),
    "api_tokens": TableRule((U,), Action.KEEP, "Personal API tokens (hashed)."),
    "event_reads": TableRule((U,), Action.KEEP, "Which alerts a user has read."),
    "plans": TableRule((U,), Action.KEEP, "Tariff definitions."),
    "user_plans": TableRule((U,), Action.KEEP, "User tariff assignments."),
    "plan_changes": TableRule((U,), Action.KEEP, "Tariff history."),
    "manual_runs": TableRule((T,), Action.KEEP, "Manual-run rate limiting."),
    "llm_usage": TableRule((T,), Action.KEEP, "LLM spend per day."),
    "llm_reservations": TableRule((T,), Action.KEEP, "In-flight LLM budget holds."),
    "user_totp": TableRule((U,), Action.KEEP, "2FA secrets."),
    "user_backup_codes": TableRule((U,), Action.KEEP, "2FA backup codes (hashed)."),
    "mfa_challenges": TableRule((T,), Action.KEEP, "Pending 2FA challenges."),
    "nf_rls_key": TableRule((T,), Action.KEEP, "Row-level-security key material."),
}

# Tables holding one row (or more) per video / channel, deleted with it.
VIDEO_DEPENDENTS = ("video_niches", "video_stats_history", "chart_entries", "video_changes",
                    "video_tags", "video_insights", "thumbnail_archive", "video_sponsors",
                    "sponsor_scan")
CHANNEL_DEPENDENTS = ("channel_stats_history",)


@dataclass(frozen=True)
class AgeRule:
    """Delete (or strip columns of) rows whose timestamp is older than a window."""
    name: str
    table: str
    timestamp: str          # SQL expression of the row's timestamp column(s)
    window: Window
    strip: tuple[str, ...] = ()   # non-empty = UPDATE ... SET col = NULL instead of DELETE
    where: str = "TRUE"
    # True when the rows this rule targets are already deleted by a stats-window rule on the
    # same table whenever the text window is not shorter than the stats window.
    covered_by_stats: bool = False


AGE_RULES: tuple[AgeRule, ...] = (
    AgeRule("video_stats_history.rows", "video_stats_history", "captured_at", Window.STATS),
    AgeRule("video_stats_history.text", "video_stats_history", "captured_at", Window.TEXT,
            strip=("title", "thumbnail"), where="(title IS NOT NULL OR thumbnail IS NOT NULL)",
            covered_by_stats=True),
    AgeRule("channel_stats_history.rows", "channel_stats_history", "captured_at", Window.STATS),
    AgeRule("video_changes.rows", "video_changes", "changed_at", Window.TEXT),
    AgeRule("thumbnail_archive.rows", "thumbnail_archive", "captured_at", Window.TEXT),
    AgeRule("video_categories.rows", "video_categories", "updated_at", Window.TEXT),
    AgeRule("video_insights.rows", "video_insights", "created_at", Window.TEXT),
    AgeRule("video_sponsors.rows", "video_sponsors", "detected_at", Window.TEXT),
    AgeRule("niche_clusters.rows", "niche_clusters", "created_at", Window.TEXT),
    AgeRule("llm_cache.rows", "llm_cache", "created_at", Window.TEXT),
    AgeRule("events.rows", "events", "created_at", Window.TEXT),
    AgeRule("alert_deliveries.rows", "alert_deliveries", "sent_at", Window.TEXT),
    AgeRule("saved_items.payload", "saved_items", "created_at", Window.TEXT,
            strip=("payload",), where="payload IS NOT NULL"),
    AgeRule("gone_items.rows", "gone_items", "last_missing_at", Window.TEXT),
)
