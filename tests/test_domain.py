from datetime import datetime, timezone

import pytest

from viraltrack.domain import (
    Content,
    ContentType,
    Creator,
    Metric,
    MetricKind,
    Platform,
    Provenance,
)

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
RAW = Provenance("youtube", "youtube-data-api", NOW, MetricKind.RAW)
DERIVED = Provenance("youtube", "niche-finder", NOW, MetricKind.DERIVED)


def make(metrics=(), derived=()):
    return Content(platform=Platform.YOUTUBE, content_id="v1", content_type=ContentType.VIDEO,
                   url="https://www.youtube.com/watch?v=v1",
                   creator=Creator(Platform.YOUTUBE, "c1"), metrics=metrics, derived=derived)


def test_raw_and_derived_kept_apart():
    c = make(metrics=(Metric("views", 10, RAW),), derived=(Metric("outlier_score", 2.5, DERIVED),))
    assert c.metric("views").provenance.kind is MetricKind.RAW
    assert c.metric("outlier_score").provenance.source == "niche-finder"


def test_derived_metric_cannot_pose_as_raw():
    with pytest.raises(ValueError, match="not raw"):
        make(metrics=(Metric("outlier_score", 2.5, DERIVED),))


def test_raw_metric_cannot_pose_as_derived():
    with pytest.raises(ValueError, match="not derived"):
        make(derived=(Metric("views", 10, RAW),))


@pytest.mark.parametrize("platform", list(Platform))
def test_model_is_platform_neutral(platform):
    c = Content(platform=platform, content_id="x", content_type=ContentType.SHORT,
                url="https://example.invalid/x", creator=Creator(platform, "y"),
                hashtags=("a", "b"))
    assert c.platform is platform
