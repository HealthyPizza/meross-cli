from dataclasses import dataclass

from meross_iot.model.enums import OnlineStatus

SWITCH_WORDS = {"on": True, "enable": True, "off": False, "disable": False}
SHUTTER_MOVES = {"open": "async_open", "close": "async_close", "stop": "async_stop"}


class UnsupportedAction(Exception):
    pass


class DeviceOffline(Exception):
    pass


@dataclass(frozen=True)
class Action:
    kind: str  # "switch", "move" ou "position"
    value: object
    channel: int = 0  # 0 = tout l'appareil ; 1..n = une sortie de multiprise


def parse_action(text):
    word = text.strip().lower()
    if word in SWITCH_WORDS:
        return Action("switch", SWITCH_WORDS[word])
    if word in SHUTTER_MOVES:
        return Action("move", word)
    if word.isdigit() and 0 <= int(word) <= 100:
        return Action("position", int(word))
    raise ValueError(
        f"Action inconnue : « {text} ». Attendu : on/off, enable/disable, open/close/stop ou une position 0-100."
    )


# On détecte les capacités par duck typing (présence des méthodes) plutôt que par
# isinstance sur les mixins meross-iot : ça découple le CLI de la hiérarchie interne
# de la lib et permet de tester avec de simples faux objets.
def is_shutter(device):
    return hasattr(device, "async_set_position")


def is_switch(device):
    return hasattr(device, "async_turn_on")


async def apply(device, action):
    if device.online_status != OnlineStatus.ONLINE:
        raise DeviceOffline(f"« {device.name} » n'est pas en ligne ({device.online_status.name}).")

    if action.kind == "switch" and is_switch(device):
        if action.value:
            await device.async_turn_on(channel=action.channel)
        else:
            await device.async_turn_off(channel=action.channel)
    elif action.kind == "move" and is_shutter(device):
        await getattr(device, SHUTTER_MOVES[action.value])(channel=0)
    elif action.kind == "position" and is_shutter(device):
        await device.async_set_position(action.value, channel=0)
    else:
        raise UnsupportedAction(f"« {device.name} » ({device.type}) ne gère pas cette action.")
