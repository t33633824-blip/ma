from pathlib import Path

from shorts.feeds import parse_feed, read_feed_list
from shorts.llm.base import build_prompts
from shorts.config import Settings
from shorts.models import SourceDoc
from shorts.sources import is_reddit

RSS = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>top scoring in TIFU</title>
<entry><title>TIFU by doing a thing</title><link href="https://www.reddit.com/r/tifu/comments/abc/tifu_by/"/>
<content type="html">&lt;div&gt;&lt;p&gt;So this happened yesterday and it was wild.&lt;/p&gt; submitted by &lt;a&gt;/u/someone&lt;/a&gt;&lt;/div&gt;</content>
<updated>2026-09-10T10:00:00+00:00</updated></entry></feed>"""


def test_feed_list_with_story_prefix(tmp_path: Path):
    f = tmp_path / "feeds.txt"
    f.write_text("# c\nhttps://a.com/rss\nstory https://www.reddit.com/r/tifu/top/.rss?t=week\n", encoding="utf-8")
    specs = read_feed_list(f)
    assert [(s.kind, s.url) for s in specs] == [("article", "https://a.com/rss"), ("story", "https://www.reddit.com/r/tifu/top/.rss?t=week")]


def test_parse_story_feed_uses_content():
    items = parse_feed(RSS, source="x", kind="story")
    assert len(items) == 1
    assert items[0].kind == "story"
    assert "wild" in items[0].summary


def test_is_reddit_and_story_prompt():
    assert is_reddit("https://www.reddit.com/r/tifu/comments/abc/x/")
    assert not is_reddit("https://www.sciencedaily.com/x")
    settings = Settings(_env_file=None)
    system, user = build_prompts(SourceDoc(url="u", title="t", text="x", kind="story"), settings)
    assert "рассказчик" in system and "Reddit" in system
    system2, _ = build_prompts(SourceDoc(url="u", title="t", text="x"), settings)
    assert "сценарист" in system2
