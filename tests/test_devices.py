from types import SimpleNamespace

import pytest

from fakes import FakeLight, FakeStrip
from meross_cli.devices import AmbiguousName, DeviceNotFound, resolve


def make_devices(*names):
    return [SimpleNamespace(name=n, outlets=()) for n in names]


def test_resolve_ignores_case_and_surrounding_spaces():
    devices = make_devices("Bureau", "Volet Ouest")

    assert resolve(devices, "  volet ouest ").entry.name == "Volet Ouest"


def test_resolve_unknown_name_suggests_close_matches():
    devices = make_devices("Bureau", "Volet Ouest", "Atelier")

    with pytest.raises(DeviceNotFound) as exc:
        resolve(devices, "volet oues")

    assert exc.value.suggestions == ["Volet Ouest"]


def test_resolve_plain_device_targets_main_channel():
    target = resolve([FakeLight("Bureau")], "bureau")

    assert (target.entry.name, target.channel) == ("Bureau", 0)


def test_resolve_outlet_by_its_own_name():
    target = resolve([FakeLight("Bureau"), FakeStrip("Multiprise")], "switch 4")

    assert (target.entry.name, target.channel) == ("Multiprise", 4)
    assert target.label == "Multiprise › Switch 4"


def test_resolve_outlet_prefixed_by_device_name():
    target = resolve([FakeStrip("Multiprise")], "multiprise usb")

    assert target.channel == 5


def test_resolve_refuses_ambiguous_name_and_lists_options():
    with pytest.raises(AmbiguousName) as exc:
        resolve([FakeStrip("Atelier"), FakeStrip("Bureau")], "switch 1")

    assert exc.value.options == ["Atelier › Switch 1", "Bureau › Switch 1"]


def test_resolve_suggests_outlet_names_too():
    with pytest.raises(DeviceNotFound) as exc:
        resolve([FakeStrip("Multiprise")], "swich 4")

    assert exc.value.suggestions[0] == "Multiprise › Switch 4"
