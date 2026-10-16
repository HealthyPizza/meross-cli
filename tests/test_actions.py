import asyncio

import pytest
from meross_iot.model.enums import OnlineStatus

from fakes import FakeLight, FakeShutter, FakeStrip
from meross_cli.actions import Action, DeviceOffline, UnsupportedAction, apply, parse_action


def run(device, action_text):
    asyncio.run(apply(device, parse_action(action_text)))
    return device.calls


@pytest.mark.parametrize("text, expected", [
    ("on", "turn_on"), ("enable", "turn_on"), ("ON", "turn_on"),
    ("off", "turn_off"), ("disable", "turn_off"),
])
def test_switch_actions_on_light(text, expected):
    assert run(FakeLight(), text) == [expected]


@pytest.mark.parametrize("text", ["open", "close", "stop"])
def test_shutter_moves(text):
    assert run(FakeShutter(), text) == [text]


def test_shutter_position_in_percent():
    assert run(FakeShutter(), "50") == [("set_position", 50)]


@pytest.mark.parametrize("text", ["101", "-1", "blink"])
def test_parse_action_rejects_invalid_values(text):
    with pytest.raises(ValueError):
        parse_action(text)


def test_position_on_a_light_is_unsupported():
    with pytest.raises(UnsupportedAction):
        run(FakeLight(), "50")


def test_on_on_a_shutter_is_unsupported():
    with pytest.raises(UnsupportedAction):
        run(FakeShutter(), "on")


def test_offline_device_is_rejected_before_sending_command():
    light = FakeLight(online=OnlineStatus.OFFLINE)

    with pytest.raises(DeviceOffline):
        run(light, "on")
    assert light.calls == []


def test_switch_action_targets_requested_channel():
    strip = FakeStrip()

    asyncio.run(apply(strip, Action("switch", False, channel=4)))

    assert strip.calls == [("turn_off", 4)]
