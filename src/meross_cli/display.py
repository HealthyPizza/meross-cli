from meross_iot.model.enums import OnlineStatus

from .actions import is_shutter, is_switch


def outlets(device):
    """Sorties pilotables séparément (multiprise), hors canal principal. Vide pour un appareil simple."""
    return [c for c in getattr(device, "channels", []) if not c.is_master_channel]


def on_off(device, channel):
    on = device.is_on(channel=channel)
    return "inconnu" if on is None else ("allumé" if on else "éteint")


def describe_state(device, channel=0):
    if device.online_status != OnlineStatus.ONLINE:
        return "hors ligne"
    if is_shutter(device):
        position = device.get_position(channel=0)
        return f"{position} %" if position is not None and position >= 0 else "position inconnue"
    if is_switch(device):
        sorties = outlets(device)
        if channel == 0 and sorties:
            allumees = sum(1 for c in sorties if device.is_on(channel=c.index))
            return f"{allumees}/{len(sorties)} allumé"
        return on_off(device, channel)
    return "non géré"
