from pathlib import Path

from shorts.feeds import parse_feed
from shorts.queue import Pick, Queue

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Test Feed</title>
<item><title>Coffee and memory</title><link>https://example.com/coffee</link>
<description>&lt;p&gt;Morning coffee &amp;nbsp;helps memory.&lt;/p&gt;</description>
<pubDate>Wed, 09 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>No link item</title></item>
</channel></rss>"""


def test_parse_feed_strips_html_and_skips_missing_links():
    items = parse_feed(RSS, source="x")
    assert len(items) == 1
    c = items[0]
    assert c.title == "Coffee and memory" and c.url == "https://example.com/coffee"
    assert c.summary == "Morning coffee helps memory."
    assert c.source == "Test Feed" and c.published.startswith("2026-09-09")


def test_queue_dedupes_and_orders(tmp_path: Path):
    qpath = tmp_path / "q.json"
    q = Queue(qpath)
    picks = [
        Pick(url="https://a.com/x/", title="A", reason="r", hook_idea="h", score=6),
        Pick(url="https://b.com/y", title="B", reason="r", hook_idea="h", score=9),
        Pick(url="https://A.com/x?utm_source=rss", title="A dup", reason="r", hook_idea="h", score=7),
    ]
    added = q.add(picks)
    assert [p.title for p in added] == ["A", "B"]
    q.save()

    q2 = Queue(qpath)
    assert [p.title for p in q2.pending()] == ["B", "A"]
    q2.mark(q2.pending(1)[0], "done", video_dir="out/b")
    q2.save()
    q3 = Queue(qpath)
    assert [p.title for p in q3.pending()] == ["A"]
    assert q3.recent_titles() == ["A", "B"]
    assert q3.add([Pick(url="https://b.com/y", title="B again", reason="r", hook_idea="h", score=5)]) == []
