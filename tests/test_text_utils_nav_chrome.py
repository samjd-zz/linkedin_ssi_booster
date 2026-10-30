"""Tests for nav/share-chrome detection in content_curator._text_utils.

looks_like_nav_chrome() guards two pipelines:
- avatar_intelligence._extraction drops chrome sentences at --learn time
- rei_toei._suno_pipeline.extract_themes ignores chrome facts/tags already
  present in learned data
"""

import pytest

from services.content_curator._text_utils import looks_like_nav_chrome


@pytest.mark.parametrize(
    "text",
    [
        # Share-button strip (Real Sound etc.)
        "ポスト はてなブックマーク LINE",
        # Related-articles rail header + headline blob
        "リアルサウンド編集部の記事一覧はこちら 関連記事 NIKO NIKO TAN TAN、ツアーを完走",
        # Ranking widget labels
        "実存』 ランキング アクセス数 シェア数 工藤静香",
        # "See more" link
        "「ニュース」の最新記事 もっとみる 竹内まりや、新曲が主題歌に起用",
        # Pagination chrome
        "稲葉浩志 次のページ 憧れの共演と異ジャンルの融合",
        # Site search box
        "サイトを検索 home music ニュース",
        # Hand-picked articles rail
        "独自路線をいくブランディング術 リアルサウンド厳選記事 ロックスター",
        # English social-follow strip on a JP site
        "Like on Facebook Follow on x Follow on Instagram Follow on YouTube",
        # "Pick Up" section header in Japanese context
        "『mind+』メンバー全員インタビュー Pick Up!",
    ],
)
def test_nav_chrome_detected(text):
    assert looks_like_nav_chrome(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        # Normal English prose — "pick up" without JP context must NOT flag
        "The courier will pick up the package tomorrow morning.",
        "Rust's ownership system prevents data races at compile time.",
        "Spring Boot 3.4 delivers a 30% reduction in AOT compilation time.",
        # Normal Japanese prose without chrome markers
        "新宿のライブハウスで生成AIを使った音楽イベントが開催された。",
        "このアルバムはテクノとジャズを融合した意欲作だ。",
    ],
)
def test_normal_prose_not_flagged(text):
    assert looks_like_nav_chrome(text) is False
