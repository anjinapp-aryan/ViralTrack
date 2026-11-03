from datetime import datetime, timezone

import pytest

from viraltrack.domain import (
    Content,
    ContentType,
    Creator,
    DataOrigin,
    Exposure,
    Metric,
    MetricKind,
    MetricPolicy,
    MetricRule,
    Platform,
    Provenance,
    RestrictedMetric,
)

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
T = DataOrigin.TEST


def prov(kind, exposure=Exposure.ALLOWED, origin=T, source="youtube-data-api"):
    return Provenance("youtube", source, NOW, kind, origin=origin, adapter="test",
                      exposure=exposure)


RAW, DERIVED = prov(MetricKind.RAW), prov(MetricKind.DERIVED, source="niche-finder")


def make(metrics=(), derived=(), origin=T):
    return Content(platform=Platform.YOUTUBE, content_id="v1", content_type=ContentType.VIDEO,
                   url="https://www.youtube.com/watch?v=v1",
                   creator=Creator(Platform.YOUTUBE, "c1"), origin=origin,
                   metrics=metrics, derived=derived)


def test_raw_and_derived_kept_apart():
    c = make(metrics=(Metric("views", 10, RAW),), derived=(Metric("views_per_hour_24h", 2.5, DERIVED),))
    assert c.metric("views").provenance.kind is MetricKind.RAW
    assert c.metric("views_per_hour_24h").provenance.source == "niche-finder"


def test_derived_metric_cannot_pose_as_raw():
    with pytest.raises(ValueError, match="not raw"):
        make(metrics=(Metric("views_per_hour_24h", 2.5, DERIVED),))


def test_raw_metric_cannot_pose_as_derived():
    with pytest.raises(ValueError, match="not derived"):
        make(derived=(Metric("views", 10, RAW),))


@pytest.mark.parametrize("exposure", [Exposure.RESTRICTED, Exposure.INTERNAL_ONLY])
def test_content_rejects_unexposable_metrics(exposure):
    with pytest.raises(ValueError, match="cannot be part of user-facing content"):
        make(derived=(Metric("outlier_score", 9.0, prov(MetricKind.DERIVED, exposure)),))


def test_creator_metrics_are_checked_too():
    bad = Metric("followers", 5, prov(MetricKind.RAW, Exposure.RESTRICTED))
    with pytest.raises(ValueError):
        Content(platform=Platform.YOUTUBE, content_id="v", content_type=ContentType.VIDEO, url="u",
                creator=Creator(Platform.YOUTUBE, "c", followers=bad), origin=T)


def test_demo_metric_cannot_sit_in_real_content():
    demo = Metric("views", 10, prov(MetricKind.RAW, origin=DataOrigin.DEMO))
    with pytest.raises(ValueError, match="origin"):
        make(metrics=(demo,), origin=DataOrigin.REAL_PROVIDER_DATA)


@pytest.mark.parametrize("platform", list(Platform))
def test_model_is_platform_neutral(platform):
    c = Content(platform=platform, content_id="x", content_type=ContentType.SHORT,
                url="https://example.invalid/x", creator=Creator(platform, "y"), origin=T,
                hashtags=("a", "b"))
    assert c.platform is platform


def test_metric_policy_decisions():
    policy = MetricPolicy([
        MetricRule("a", Exposure.ALLOWED, "x"),
        MetricRule("r", Exposure.RESTRICTED, "x", requires="approval"),
        MetricRule("i", Exposure.INTERNAL_ONLY, "x"),
    ])
    assert policy.exposable("a")
    assert not policy.exposable("r") and not policy.exposable("i")
    assert not policy.exposable("unknown")          # denied by default
    with pytest.raises(RestrictedMetric):
        policy.require("r")
    approved = MetricPolicy(list(policy.rules.values()), frozenset({"approval"}))
    assert approved.exposable("r") and not approved.exposable("i")


def test_restricted_rule_must_name_its_approval():
    with pytest.raises(ValueError):
        MetricPolicy([MetricRule("r", Exposure.RESTRICTED, "x")])
