from contextlib import asynccontextmanager

from meross_iot.model.enums import OnlineStatus

from fakes import FakeHome, FakeLight, FakeShutter, FakeStrip
from meross_cli.cli import main


def fake_connect(home):
    @asynccontextmanager
    async def connect():
        yield home

    return connect


def test_list_shows_each_device_with_its_state(capsys):
    home = FakeHome(
        FakeLight("Bureau", on=True),
        FakeShutter("Volet Ouest", position=40),
        FakeLight("Garage", online=OnlineStatus.OFFLINE),
    )

    assert main(["list"], connect=fake_connect(home)) == 0

    out = capsys.readouterr().out
    assert "Bureau" in out and "allumé" in out
    assert "Volet Ouest" in out and "40 %" in out
    assert "Garage" in out and "hors ligne" in out


def test_list_does_not_try_to_load_offline_devices():
    home = FakeHome(FakeLight("Bureau"), FakeLight("Garage", online=OnlineStatus.OFFLINE))

    main(["list"], connect=fake_connect(home))

    assert home.loaded == ["Bureau"]


def test_list_reports_unresponsive_device_without_failing(capsys):
    sensor = FakeLight("Capteur")
    home = FakeHome(FakeLight("Bureau", on=True), sensor, unreachable=[sensor])

    assert main(["list"], connect=fake_connect(home)) == 0

    out = capsys.readouterr().out
    assert "allumé" in out
    assert "Capteur" in out and "ne répond pas" in out


def test_command_only_loads_the_target_device():
    light = FakeLight("Bureau")
    home = FakeHome(light, FakeShutter("Volet Ouest"))

    assert main(["bureau", "on"], connect=fake_connect(home)) == 0
    assert "turn_on" in light.calls
    assert home.loaded == ["Bureau"]


def test_command_on_offline_device_fails_without_loading_it(capsys):
    home = FakeHome(FakeLight("Garage", online=OnlineStatus.OFFLINE))

    assert main(["garage", "on"], connect=fake_connect(home)) == 1
    assert home.loaded == []
    assert "pas en ligne" in capsys.readouterr().err


def test_command_on_unresponsive_device_exits_with_error(capsys):
    sensor = FakeLight("Capteur")

    assert main(["capteur", "on"], connect=fake_connect(FakeHome(sensor, unreachable=[sensor]))) == 1
    assert "ne répond pas" in capsys.readouterr().err


def test_device_name_may_span_several_words_without_quotes():
    shutter = FakeShutter("Volet Ouest")

    assert main(["volet", "ouest", "50"], connect=fake_connect(FakeHome(shutter))) == 0
    assert ("set_position", 50) in shutter.calls


def test_name_without_action_prints_device_state(capsys):
    home = FakeHome(FakeShutter("Volet Ouest", position=0))

    assert main(["volet", "ouest"], connect=fake_connect(home)) == 0
    assert "0 %" in capsys.readouterr().out


def test_unknown_device_exits_with_error_and_suggestion(capsys):
    assert main(["bureu", "on"], connect=fake_connect(FakeHome(FakeLight("Bureau")))) == 1
    assert "Bureau" in capsys.readouterr().err


def test_unsupported_action_exits_with_error(capsys):
    assert main(["bureau", "50"], connect=fake_connect(FakeHome(FakeLight("Bureau")))) == 1
    assert "ne gère pas" in capsys.readouterr().err


def test_no_argument_opens_the_interactive_app():
    home = FakeHome(FakeLight("Bureau"))
    opened = []

    async def fake_tui(h):
        opened.append(h)

    assert main([], connect=fake_connect(home), run_tui=fake_tui) == 0
    assert opened == [home]


def test_command_on_one_outlet(capsys):
    strip = FakeStrip()

    assert main(["switch", "4", "off"], connect=fake_connect(FakeHome(strip))) == 0
    assert ("turn_off", 4) in strip.calls
    assert "Multiprise › Switch 4" in capsys.readouterr().out


def test_command_on_strip_name_targets_all_outlets():
    strip = FakeStrip()

    assert main(["multiprise", "off"], connect=fake_connect(FakeHome(strip))) == 0
    assert ("turn_off", 0) in strip.calls


def test_list_shows_outlets_under_the_strip(capsys):
    main(["list"], connect=fake_connect(FakeHome(FakeStrip())))

    lines = capsys.readouterr().out.splitlines()
    strip_line = next(i for i, l in enumerate(lines) if "Multiprise" in l)
    assert "2/5 allumé" in lines[strip_line]
    assert "Switch 1" in lines[strip_line + 1] and "éteint" in lines[strip_line + 1]
    assert "USB" in lines[strip_line + 5] and "allumé" in lines[strip_line + 5]


def test_ambiguous_outlet_name_exits_with_options(capsys):
    home = FakeHome(FakeStrip("Atelier"), FakeStrip("Bureau"))

    assert main(["switch", "1", "on"], connect=fake_connect(home)) == 1
    err = capsys.readouterr().err
    assert "Atelier › Switch 1" in err and "Bureau › Switch 1" in err


def test_outlet_name_ending_with_a_digit_shows_its_state(capsys):
    assert main(["switch", "4"], connect=fake_connect(FakeHome(FakeStrip()))) == 0
    assert "Multiprise › Switch 4 : allumé" in capsys.readouterr().out


def test_exact_name_wins_over_name_plus_position():
    volet, volet5 = FakeShutter("Volet"), FakeShutter("Volet 5", position=30)

    assert main(["volet", "5"], connect=fake_connect(FakeHome(volet, volet5))) == 0
    assert not any(isinstance(c, tuple) for c in volet.calls)  # aucune position envoyée


def test_outlet_name_ending_with_a_digit_accepts_an_action():
    strip = FakeStrip()

    assert main(["switch", "1", "on"], connect=fake_connect(FakeHome(strip))) == 0
    assert ("turn_on", 1) in strip.calls
