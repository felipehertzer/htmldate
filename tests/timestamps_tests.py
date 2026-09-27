"""Regression cases for JSON quote corruption and publication time precision."""

import json

import pytest

from htmldate import find_date

URL = "https://example.org/story"


def script(value):
    return '<script type="application/ld+json">' + json.dumps(value) + "</script>"


def metadata(content, **config):
    return find_date(
        "<html><head>" + content + "</head><body/></html>",
        url=URL,
        **{
            "preserve_timestamp": True,
            "original_date": True,
            "max_date": "2026-09-27",
            **config,
        },
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-09-26T22:00:00+00:00",
        "2026-09-26T22:01:02.123000+10:00",
        "2026-09-26T22:00:00",
    ],
)
def test_explicit_precision_and_offset(timestamp):
    content = f'<meta property="article:published_time" content="{timestamp}">'
    assert metadata(content) == timestamp
    assert metadata(content, preserve_timestamp=False) == "2026-09-26"


def test_jsonld_ignores_related_stories_and_live_updates():
    content = script(
        {
            "@graph": [
                {
                    "@type": "NewsArticle",
                    "url": "https://example.org/related",
                    "datePublished": "2020-01-01T00:00:00Z",
                },
                {
                    "@type": "NewsArticle",
                    "mainEntityOfPage": {"@id": URL},
                    "datePublished": "2026-09-26T22:00:00Z",
                    "liveBlogUpdate": {
                        "@type": "BlogPosting",
                        "datePublished": "2026-09-27T01:00:00Z",
                    },
                },
            ]
        }
    )
    assert metadata(content) == "2026-09-26T22:00:00+00:00"


def test_canonical_main_entity_and_type_list():
    content = '<link rel="canonical" href="/canonical">' + script(
        {
            "@type": "WebPage",
            "mainEntity": {
                "@type": ["Thing", "https://schema.org/NewsArticle"],
                "url": {"url": "/canonical"},
                "datePublished": "2026-09-26T22:00:00Z",
            },
        }
    )
    assert metadata(content) == "2026-09-26T22:00:00+00:00"


def test_matched_article_precedes_anonymous_article():
    content = script(
        [
            {"@type": "Article", "datePublished": "2020-01-01T00:00:00Z"},
            {
                "@type": "Article",
                "@id": URL + "#article",
                "datePublished": "2026-09-26T22:00:00Z",
            },
        ]
    )
    assert metadata(content) == "2026-09-26T22:00:00+00:00"


def test_ambiguous_articles_do_not_invent_precise_time():
    content = script(
        [
            {"@type": "Article", "datePublished": "2020-01-01T00:00:00Z"},
            {"@type": "Article", "datePublished": "2021-01-01T00:00:00Z"},
        ]
    )
    assert "T" not in (metadata(content) or "")


@pytest.mark.parametrize(
    "invalid",
    [
        "2026-09-26",
        "badT25:77",
        "2026-99-99T00:00:00Z",
        "2099-01-01T00:00:00Z",
        "1800-01-01T00:00:00Z",
    ],
)
def test_bad_candidate_does_not_hide_valid_timestamp(invalid):
    content = f'<meta property="article:published_time" content="{invalid}">'
    content += '<time itemprop="datePublished" datetime="2026-09-26T22:00:00Z"></time>'
    assert metadata(content) == "2026-09-26T22:00:00+00:00"


def test_date_bounds_and_date_only_fallback():
    content = '<meta itemprop="datePublished" content="2026-09-26T22:00:00Z">'
    assert metadata(content, min_date="2026-09-27") is None
    assert (
        metadata('<meta itemprop="datePublished" content="2026-09-26">') == "2026-09-26"
    )


def test_modification_requires_explicit_request_and_config_is_not_mutated():
    content = '<meta property="article:modified_time" content="2026-09-26T22:00:00Z">'
    assert "T" not in (metadata(content) or "")
    assert metadata(content, original_date=False) == "2026-09-26T22:00:00+00:00"
    config = {"preserve_timestamp": True}
    find_date(content, **config)
    assert config == {"preserve_timestamp": True}
