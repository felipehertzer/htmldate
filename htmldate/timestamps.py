"""Preserve explicitly published ISO timestamps without guessing a time of day."""

import json
import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin

from lxml.html import HtmlElement

JSON_ARTICLE_SCHEMA = {
    "article",
    "newsarticle",
    "blogposting",
    "liveblogposting",
    "backgroundnewsarticle",
    "opinionnewsarticle",
    "reportagenewsarticle",
    "scholarlyarticle",
    "medicalscholarlyarticle",
    "socialmediaposting",
    "analysisnewsarticle",
    "reviewnewsarticle",
    "techarticle",
}


def _nodes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [node for child in value for node in _nodes(child)]
    if not isinstance(value, dict):
        return []
    return [value, *_nodes(value.get("@graph")), *_nodes(value.get("mainEntity"))]


def _identity(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("@id") or value.get("url")
    return value if isinstance(value, str) and value.strip() else None


def _bound(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return None


def extract_timestamp(tree: HtmlElement, config: dict[str, Any]) -> str | None:
    """Return an explicit ISO timestamp for this page, respecting date bounds.

    Only page-level publication/modification tags and matching article JSON-LD
    are considered. Related stories, live-blog updates and arbitrary body dates
    cannot provide the time. Naive timestamps remain naive for the caller to
    interpret; no timezone or midnight is invented.
    """
    original = config.get("original_date", True)
    field = "datePublished" if original else "dateModified"
    prop = "article:published_time" if original else "article:modified_time"
    candidates = list(tree.xpath(f'.//meta[@property="{prop}"]/@content'))
    candidates.extend(
        tree.xpath(f'.//meta[@itemprop="{field}" or @name="{field}"]/@content')
    )
    candidates.extend(tree.xpath(f'.//time[@itemprop="{field}"]/@datetime'))

    page_url = config.get("url") or ""

    def normalize(value: str) -> str:
        return urljoin(page_url, value).split("#", 1)[0].rstrip("/")

    allowed = {normalize(page_url)} if page_url else set()
    allowed.update(
        normalize(value) for value in tree.xpath('.//link[@rel="canonical"]/@href')
    )
    nodes = []
    for script in tree.xpath('.//script[@type="application/ld+json"]/text()'):
        try:
            nodes.extend(_nodes(json.loads(script, strict=False)))
        except json.JSONDecodeError:  # noqa: PERF203 — malformed scripts must not hide later metadata
            continue
    matched, anonymous = [], []
    for node in nodes:
        kinds = node.get("@type", [])
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(
            str(kind).rsplit("/", 1)[-1].casefold() in JSON_ARTICLE_SCHEMA
            for kind in kinds
        ):
            continue
        identity = _identity(node.get("url")) or _identity(node.get("mainEntityOfPage"))
        identity = identity or _identity(node.get("@id"))
        if identity:
            if normalize(identity) in allowed:
                matched.append(node)
        else:
            anonymous.append(node)
    articles = matched or (anonymous if len(anonymous) == 1 else [])
    candidates.extend(
        node[field] for node in articles if isinstance(node.get(field), str)
    )

    minimum = _bound(config.get("min_date")) or date(1995, 1, 1)
    maximum = _bound(config.get("max_date")) or datetime.now(timezone.utc).date()
    for value in candidates:
        if not re.search(r"[Tt ]\d{2}:\d{2}", value):
            continue
        try:
            stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        if minimum <= stamp.date() <= maximum:
            return stamp.isoformat()
    return None
