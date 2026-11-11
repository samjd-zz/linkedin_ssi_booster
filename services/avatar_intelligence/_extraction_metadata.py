"""Identify scraped navigation artifacts in newly extracted metadata."""

import re

_NAV_MARKERS = (
    "はてなブックマーク", "関連記事", "もっとみる", "リアルサウンド厳選記事",
    "アクセス数 シェア数", "このコントリビューター", "facebookでシェア",
    "blueprint book store", "サイトを検索",
)
_SOCIAL_FOLLOW_RE = re.compile(
    r"\b(?:follow on (?:x|facebook|instagram|youtube|line|tiktok|sns)|like on facebook)\b",
    re.IGNORECASE,
)
_PICK_UP_RE = re.compile(r"\bpick\s*up\b", re.IGNORECASE)
_JP_CHARS_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")
_MENU_WORDS = frozenset({
    "menu", "search", "products", "solutions", "industries", "partners",
    "customers", "pricing", "resources", "login", "signup", "developers",
})


def is_navigation_metadata(value: str) -> bool:
    """Detect clear UI/share fragments without treating generic concepts as junk."""
    text = value.casefold()
    if any(marker in text for marker in _NAV_MARKERS) or _SOCIAL_FOLLOW_RE.search(text):
        return True
    if _PICK_UP_RE.search(text) and (
        _JP_CHARS_RE.search(text) or re.fullmatch(r"\s*pick\s*up[!！\s]*", text)
    ):
        return True
    words = re.findall(r"[a-z]+", text)
    return len(words) >= 5 and "menu" in words and len(set(words) & _MENU_WORDS) >= 3
