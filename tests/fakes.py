from types import SimpleNamespace

from meross_iot.model.enums import OnlineStatus


class PushMixin:
    """Simule les notifications push de meross-iot (changement d'état venu d'ailleurs)."""

    def register_push_notification_handler_coroutine(self, coro):
        self.__dict__.setdefault("_push_handlers", []).append(coro)

    async def simulate_push(self):
        for coro in self.__dict__.get("_push_handlers", []):
            await coro(None, {}, self.uuid)


class FakeLight(PushMixin):
    def __init__(self, name="Bureau", on=False, online=OnlineStatus.ONLINE):
        self.name = name
        self.uuid = f"uuid-{name}"
        self.type = "mss510"
        self.outlets = ()
        self.online_status = online
        self._on = on
        self.calls = []

    async def async_update(self):
        self.calls.append("update")

    def is_on(self, channel=0):
        return self._on

    async def async_turn_on(self, channel=0):
        self.calls.append("turn_on")
        self._on = True

    async def async_turn_off(self, channel=0):
        self.calls.append("turn_off")
        self._on = False


class FakeShutter(PushMixin):
    def __init__(self, name="Volet Ouest", position=100, online=OnlineStatus.ONLINE):
        self.name = name
        self.uuid = f"uuid-{name}"
        self.type = "mrs100"
        self.outlets = ()
        self.online_status = online
        self._position = position
        self.calls = []

    async def async_update(self):
        self.calls.append("update")

    def get_position(self, channel=0):
        return self._position

    async def async_open(self, channel=0):
        self.calls.append("open")

    async def async_close(self, channel=0):
        self.calls.append("close")

    async def async_stop(self, channel=0):
        self.calls.append("stop")

    async def async_set_position(self, position, channel=0):
        self.calls.append(("set_position", position))


STRIP_CHANNELS = ["Main channel", "Switch 1", "Switch 2", "Switch 3", "Switch 4", "USB"]


class FakeStrip(PushMixin):
    """Multiprise mss425f : canal 0 = toutes les sorties, 1-4 = prises, 5 = USB."""

    def __init__(self, name="Multiprise", states=(True, False, False, False, True, True),
                 online=OnlineStatus.ONLINE):
        self.name = name
        self.uuid = f"uuid-{name}"
        self.type = "mss425fc"
        self.online_status = online
        self.channels = [SimpleNamespace(index=i, name=n, is_master_channel=i == 0, is_usb=n == "USB")
                         for i, n in enumerate(STRIP_CHANNELS)]
        self.outlets = tuple((c.index, c.name) for c in self.channels[1:])
        self._on = list(states)
        self.calls = []

    async def async_update(self):
        self.calls.append("update")

    def is_on(self, channel=0):
        return self._on[channel]

    async def async_turn_on(self, channel=0):
        self.calls.append(("turn_on", channel))
        self._on[channel] = True

    async def async_turn_off(self, channel=0):
        self.calls.append(("turn_off", channel))
        self._on[channel] = False


class FakeHub(PushMixin):
    def __init__(self, name="Hub"):
        self.name = name
        self.uuid = f"uuid-{name}"
        self.type = "msh300hk"
        self.outlets = ()
        self.online_status = OnlineStatus.ONLINE
        self.calls = []

    async def async_update(self):
        self.calls.append("update")


class FakeHome:
    """Remplace session.Home : expose les entrées de la liste cloud et charge les appareils à la demande."""

    def __init__(self, *devices, unreachable=()):
        self.entries = list(devices)
        self._unreachable = {d.name for d in unreachable}
        self.loaded = []

    async def load(self, entry):
        from meross_cli.session import DeviceUnreachable

        self.loaded.append(entry.name)
        if entry.name in self._unreachable:
            raise DeviceUnreachable(f"« {entry.name} » ne répond pas.")
        return entry
