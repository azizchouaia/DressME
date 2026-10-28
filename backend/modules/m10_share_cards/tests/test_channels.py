"""Channel attribution: which channel (WhatsApp, Instagram, …) brings new users."""

from urllib.parse import unquote

from modules.m10_share_cards.pipeline import links, metrics
from modules.m10_share_cards.store import MemoryShareStore


def test_channel_links_are_tagged():
    out = links.channel_links("https://dressme.tn/s/abc1234", "Linen day")
    assert set(out) == set(links.CHANNELS)
    assert unquote(out["whatsapp"]).endswith("https://dressme.tn/s/abc1234?ch=whatsapp")
    assert "ch%3Dfacebook" in out["facebook"] and out["copy"].endswith("?ch=copy")


def test_signup_takes_channel_of_last_open_and_best_channel():
    s = MemoryShareStore()
    s.cards["c"] = {"card_id": "c", "user_id": "u", "short_code": "AAA"}
    for _ in range(3):
        s.add_open("AAA", "whatsapp")
    for _ in range(4):
        s.add_open("AAA", "instagram")
    s.add_signup("AAA", "n1")  # last open was instagram
    s.add_signup("AAA", "n2", "whatsapp")
    s.add_signup("AAA", "n3", "whatsapp")
    m = metrics.compute(*s.events())
    rows = {r["channel"]: r for r in m.channels}
    assert rows["instagram"]["signups"] == 1 and rows["whatsapp"]["signups"] == 2
    assert m.best_channel == "whatsapp"  # 2/3 beats 1/4


def test_best_channel_needs_enough_opens():
    _, best = metrics.by_channel([{"channel": "x"}], [{"new_user_id": "a", "channel": "x"}])
    assert best is None


def test_a_signup_always_comes_with_an_open():
    from modules.m10_share_cards.store import MemoryShareStore

    st = MemoryShareStore()
    st.cards["c1"] = {"card_id": "c1", "user_id": "u", "short_code": "abc1234"}
    for i in range(3):  # three friends sign up without a recorded visit
        st.add_signup("abc1234", f"f{i}", "whatsapp")
    st.add_open("abc1234", "instagram")
    st.add_signup("abc1234", "f9")  # this one did open the link first
    _, opens, signups = st.events()
    assert len(signups) == 4 and len(opens) == 4  # never more sign-ups than opens
