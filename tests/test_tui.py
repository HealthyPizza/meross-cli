from meross_iot.model.enums import OnlineStatus
from textual.widgets import DataTable, Static

from fakes import FakeHome, FakeHub, FakeLight, FakeShutter, FakeStrip
from meross_cli.tui import MerossApp


async def settle(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def state_cell(app, device):
    return str(app.query_one("#devices", DataTable).get_cell(device.uuid, "state"))


def details(app):
    return str(app.query_one("#details", Static).content)


async def test_shows_every_device_with_its_state_once_loaded():
    lumiere = FakeLight("Lampe", on=True)
    volet = FakeShutter("Volet", position=80)
    lampe = FakeLight("Applique", online=OnlineStatus.OFFLINE)
    hub = FakeHub()
    home = FakeHome(lumiere, volet, lampe, hub)
    app = MerossApp(home)

    async with app.run_test() as pilot:
        await settle(pilot)

        assert state_cell(app, lumiere) == "allumé"
        assert state_cell(app, volet) == "80 %"
        assert state_cell(app, lampe) == "hors ligne"
        assert state_cell(app, hub) == "non géré"
        assert "Applique" not in home.loaded


async def test_unresponsive_device_is_reported():
    sensor = FakeLight("Capteur")
    app = MerossApp(FakeHome(sensor, unreachable=[sensor]))

    async with app.run_test() as pilot:
        await settle(pilot)

        assert state_cell(app, sensor) == "ne répond pas"


async def test_o_turns_on_selected_light():
    light = FakeLight("Lampe", on=False)
    app = MerossApp(FakeHome(light))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("o")
        await settle(pilot)

        assert "turn_on" in light.calls
        assert state_cell(app, light) == "allumé"


async def test_enter_toggles_selected_light():
    light = FakeLight("Lampe", on=True)
    app = MerossApp(FakeHome(light))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)

        assert "turn_off" in light.calls


async def test_details_follow_selection():
    app = MerossApp(FakeHome(FakeLight("A lampe"), FakeShutter("B volet")))

    async with app.run_test() as pilot:
        await settle(pilot)
        assert "Allumer" in details(app)

        await pilot.press("down")
        await pilot.pause()

        assert "B volet" in details(app) and "Ouvrir" in details(app)


async def test_right_raises_shutter_by_ten_percent_clamped_to_100():
    shutter = FakeShutter("Volet", position=95)
    app = MerossApp(FakeHome(shutter))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("right")
        await settle(pilot)

        assert ("set_position", 100) in shutter.calls


async def test_left_lowers_shutter_by_ten_percent():
    shutter = FakeShutter("Volet", position=80)
    app = MerossApp(FakeHome(shutter))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("left")
        await settle(pilot)

        assert ("set_position", 70) in shutter.calls


async def test_c_closes_selected_shutter():
    shutter = FakeShutter("Volet")
    app = MerossApp(FakeHome(shutter))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("c")
        await settle(pilot)

        assert "close" in shutter.calls


async def test_shutter_key_on_a_light_sends_nothing():
    light = FakeLight("Lampe")
    app = MerossApp(FakeHome(light))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("c")
        await settle(pilot)

        assert light.calls == ["update"]


async def test_p_asks_for_a_precise_position():
    shutter = FakeShutter("Volet")
    app = MerossApp(FakeHome(shutter))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("p", "3", "5", "enter")
        await settle(pilot)

        assert ("set_position", 35) in shutter.calls


async def test_offline_device_gets_no_command():
    light = FakeLight("Applique", online=OnlineStatus.OFFLINE)
    app = MerossApp(FakeHome(light))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("o")
        await settle(pilot)

        assert light.calls == []
        assert "hors ligne" in details(app)


async def test_push_notification_refreshes_the_row():
    shutter = FakeShutter("Volet", position=100)
    app = MerossApp(FakeHome(shutter))

    async with app.run_test() as pilot:
        await settle(pilot)
        shutter._position = 30  # quelqu'un a bougé le volet depuis l'appli Meross
        await shutter.simulate_push()
        await pilot.pause()

        assert state_cell(app, shutter) == "30 %"


async def test_strip_row_shows_outlet_summary():
    strip = FakeStrip()
    app = MerossApp(FakeHome(strip))

    async with app.run_test() as pilot:
        await settle(pilot)

        assert state_cell(app, strip) == "2/5 allumé"


async def test_strip_details_list_numbered_outlets():
    app = MerossApp(FakeHome(FakeStrip()))

    async with app.run_test() as pilot:
        await settle(pilot)

        text = details(app)
        assert "[1] Switch 1" in text and "[5] USB" in text
        assert "Tout allumer" in text


async def test_digit_key_toggles_that_outlet():
    strip = FakeStrip()
    app = MerossApp(FakeHome(strip))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("4")  # Switch 4 est allumé → on l'éteint
        await settle(pilot)

        assert ("turn_off", 4) in strip.calls
        assert state_cell(app, strip) == "1/5 allumé"


async def test_digit_beyond_outlet_count_sends_nothing():
    strip = FakeStrip()
    app = MerossApp(FakeHome(strip))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("9")
        await settle(pilot)

        assert strip.calls == ["update"]


async def test_f_on_strip_switches_everything_off():
    strip = FakeStrip()
    app = MerossApp(FakeHome(strip))

    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("f")
        await settle(pilot)

        assert ("turn_off", 0) in strip.calls
