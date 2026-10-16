from meross_iot.model.enums import OnlineStatus
from meross_iot.model.exception import CommandTimeoutError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from .actions import Action, DeviceOffline, UnsupportedAction, apply, is_shutter, is_switch
from .display import describe_state, on_off, outlets
from .session import DeviceUnreachable

SHUTTER_HELP = "[o] Ouvrir   [c] Fermer   [s] Stop\n[←/→] -10 % / +10 %\n[p] Position précise…"
SWITCH_HELP = "[o] Allumer   [f] Éteindre\n[Entrée/espace] Basculer"
STRIP_HELP = "[1-{n}] Basculer une sortie\n[o] Tout allumer   [f] Tout éteindre"


def position_bar(position, width=20):
    filled = round(width * position / 100)
    return "█" * filled + "░" * (width - filled)


class PositionScreen(ModalScreen):
    """Demande une position 0-100 ; renvoie None si on annule (Échap)."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Annuler")]
    CSS = """
    PositionScreen { align: center middle; }
    #dialog { width: 40; height: auto; padding: 1 2; border: thick $accent; background: $surface; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Position (0 = fermé, 100 = ouvert) :")
            yield Input(type="integer", placeholder="0-100", id="position")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value.isdigit() and 0 <= int(value) <= 100:
            self.dismiss(int(value))
        else:
            self.notify("Entre un nombre entre 0 et 100.", severity="warning")


class MerossApp(App):
    TITLE = "Meross"
    CSS = """
    #devices { width: 1fr; }
    #details { width: 42; padding: 1 2; border: round $accent; }
    """
    BINDINGS = [
        Binding("o", "command('open')", "Ouvrir/Allumer"),
        Binding("f", "command('off')", "Éteindre"),
        Binding("c", "command('close')", "Fermer"),
        Binding("s", "command('stop')", "Stop"),
        # priority : sinon le tableau capte ←/→ pour son propre défilement
        Binding("left", "step(-10)", "-10 %", priority=True),
        Binding("right", "step(10)", "+10 %", priority=True),
        Binding("p", "ask_position", "Position"),
        Binding("space", "toggle", "Basculer", show=False),
        *(Binding(str(n), f"outlet({n})", f"Sortie {n}", show=False) for n in range(1, 10)),
        Binding("r", "reload", "Rafraîchir"),
        Binding("q", "quit", "Quitter"),
    ]

    def __init__(self, home):
        super().__init__()
        self._home = home
        self._entries = sorted(home.entries, key=lambda e: e.name.casefold())
        self._by_uuid = {e.uuid: e for e in self._entries}
        self._devices = {}  # uuid -> appareil meross-iot chargé
        self._status = {}  # uuid -> texte d'état tant que l'appareil n'est pas chargé
        self._subscribed = set()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="devices", cursor_type="row", zebra_stripes=True)
            yield Static(id="details", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#devices", DataTable)
        table.add_column("Appareil", key="name")
        table.add_column("Type", key="type")
        table.add_column("État", key="state")
        for entry in self._entries:
            online = entry.online_status == OnlineStatus.ONLINE
            self._status[entry.uuid] = "chargement…" if online else "hors ligne"
            table.add_row(entry.name, entry.type, self._status[entry.uuid], key=entry.uuid)
        self.action_reload()

    # --- chargement et état -------------------------------------------------

    def action_reload(self) -> None:
        # Un worker par appareil : ils tournent en parallèle, un appareil muet ne bloque pas les autres.
        for entry in self._entries:
            if entry.online_status == OnlineStatus.ONLINE:
                self.run_worker(self._load(entry))
        self._show_details()

    async def _load(self, entry):
        try:
            device = await self._home.load(entry)
            await device.async_update()
        except (DeviceUnreachable, CommandTimeoutError):
            self._status[entry.uuid] = "ne répond pas"
            self._refresh_row(entry)
            return
        self._devices[entry.uuid] = device
        self._subscribe(entry, device)
        self._refresh_row(entry)

    def _subscribe(self, entry, device):
        """Met la ligne à jour quand l'appareil change d'état ailleurs (appli, interrupteur…)."""
        if entry.uuid in self._subscribed:
            return

        async def on_push(namespace, data, device_internal_id):
            self._refresh_row(entry)

        device.register_push_notification_handler_coroutine(on_push)
        self._subscribed.add(entry.uuid)

    def _state_text(self, entry):
        device = self._devices.get(entry.uuid)
        return describe_state(device) if device else self._status[entry.uuid]

    def _refresh_row(self, entry, text=None):
        self.query_one("#devices", DataTable).update_cell(entry.uuid, "state", text or self._state_text(entry))
        if self._selected_entry() is entry:
            self._show_details()

    # --- sélection et panneau de détails --------------------------------------

    def _selected_entry(self):
        table = self.query_one("#devices", DataTable)
        if not self._entries:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return self._by_uuid[row_key.value]

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show_details()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle()

    def _show_details(self):
        entry = self._selected_entry()
        if entry is None:
            return
        device = self._devices.get(entry.uuid)
        lines = [entry.name, f"{entry.type}", ""]
        if device is None:
            lines.append(self._status[entry.uuid])
        elif is_shutter(device):
            position = device.get_position(channel=0)
            if position is not None and position >= 0:
                lines.append(f"Position : {position_bar(position)} {position} %")
            else:
                lines.append("Position inconnue")
            lines += ["", SHUTTER_HELP]
        elif is_switch(device) and outlets(device):
            for n, outlet in enumerate(outlets(device), start=1):
                mark = "●" if device.is_on(channel=outlet.index) else "○"
                lines.append(f"[{n}] {outlet.name:<14} {mark} {on_off(device, outlet.index)}")
            lines += ["", STRIP_HELP.format(n=len(outlets(device)))]
        elif is_switch(device):
            lines += [f"État : {describe_state(device)}", "", SWITCH_HELP]
        else:
            lines.append("Type non géré par l'appli.")
        self.query_one("#details", Static).update("\n".join(lines))

    # --- commandes --------------------------------------------------------------

    def _selected_device(self):
        entry = self._selected_entry()
        if entry is None:
            return None, None
        device = self._devices.get(entry.uuid)
        if device is None:
            self.notify(f"{entry.name} : {self._status[entry.uuid]}", severity="warning")
        return entry, device

    def _send(self, entry, device, action):
        self.run_worker(self._apply(entry, device, action))

    async def _apply(self, entry, device, action):
        self._refresh_row(entry, "en cours…")
        try:
            await apply(device, action)
        except (UnsupportedAction, DeviceOffline) as e:
            self.notify(str(e), severity="warning")
        except CommandTimeoutError:
            self.notify(f"{entry.name} n'a pas répondu à temps.", severity="error")
        finally:
            self._refresh_row(entry)

    def action_command(self, word: str) -> None:
        entry, device = self._selected_device()
        if device is None:
            return
        if word == "open":
            action = Action("move", "open") if is_shutter(device) else Action("switch", True)
        elif word == "off":
            action = Action("switch", False)
        else:
            action = Action("move", word)
        self._send(entry, device, action)

    def action_toggle(self) -> None:
        entry, device = self._selected_device()
        if device is None or not is_switch(device):
            return
        self._send(entry, device, Action("switch", not device.is_on(channel=0)))

    def action_outlet(self, number: int) -> None:
        entry, device = self._selected_device()
        if device is None:
            return
        sorties = outlets(device)
        if not 1 <= number <= len(sorties):
            return
        channel = sorties[number - 1].index
        self._send(entry, device, Action("switch", not device.is_on(channel=channel), channel=channel))

    def action_step(self, delta: int) -> None:
        entry, device = self._selected_device()
        if device is None or not is_shutter(device):
            return
        position = device.get_position(channel=0)
        if position is None or position < 0:
            self.notify("Position actuelle inconnue : utilise [p].", severity="warning")
            return
        self._send(entry, device, Action("position", max(0, min(100, position + delta))))

    def action_ask_position(self) -> None:
        entry, device = self._selected_device()
        if device is None or not is_shutter(device):
            return

        def on_result(position):
            if position is not None:
                self._send(entry, device, Action("position", position))

        self.push_screen(PositionScreen(), on_result)
