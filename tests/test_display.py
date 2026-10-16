from fakes import FakeLight, FakeStrip
from meross_cli.display import describe_state, outlets


def test_outlets_of_a_strip_exclude_the_main_channel():
    assert [c.index for c in outlets(FakeStrip())] == [1, 2, 3, 4, 5]


def test_single_channel_device_has_no_outlets():
    assert outlets(FakeLight()) == []


def test_strip_state_summarises_outlets():
    # canal 0 allumé, sorties : off off off on on
    assert describe_state(FakeStrip()) == "2/5 allumé"


def test_state_of_one_outlet():
    assert describe_state(FakeStrip(), channel=4) == "allumé"
    assert describe_state(FakeStrip(), channel=1) == "éteint"
