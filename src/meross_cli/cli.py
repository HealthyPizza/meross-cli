import argparse
import asyncio
import dataclasses
import sys

from meross_iot.model.enums import OnlineStatus
from meross_iot.model.exception import CommandTimeoutError

from .actions import DeviceOffline, UnsupportedAction, apply, parse_action
from .devices import AmbiguousName, DeviceNotFound, resolve
from .display import describe_state, outlets
from .session import DeviceUnreachable, SessionError

EPILOG = """exemples :
  meross                         ouvre l'appli interactive (plein écran)
  meross list                    liste les appareils et leur état
  meross bureau on               allume (alias : enable)
  meross bureau off              éteint (alias : disable)
  meross volet ouest 50          volet à 50 %
  meross volet ouest open        ouvre (aussi : close, stop)
  meross volet ouest             affiche l'état
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="meross",
        usage="meross | meross list | meross <appareil> [action]",
        description="Pilote tes appareils Meross depuis le terminal.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("words", nargs="*", metavar="appareil [action]",
                        help="rien (appli interactive), « list », ou nom de l'appareil (tel que dans l'appli) suivi d'une action")
    return parser


def parse_command(entries, words):
    """Renvoie (cible, action ou None).

    La phrase entière est d'abord essayée comme nom : « switch 4 » est une sortie, pas « switch » à 4 %.
    En cas de doute on consulte plutôt qu'on actionne. Sinon le dernier mot est l'action.
    """
    phrase = " ".join(words)
    try:
        return resolve(entries, phrase), None
    except DeviceNotFound as not_found:
        if len(words) == 1:
            raise
        try:
            action = parse_action(words[-1])
        except ValueError:
            raise not_found
    return resolve(entries, " ".join(words[:-1])), action


def ensure_online(entry):
    if entry.online_status != OnlineStatus.ONLINE:
        raise DeviceOffline(f"« {entry.name} » n'est pas en ligne ({entry.online_status.name}).")


async def load_fresh(home, entry):
    ensure_online(entry)
    device = await home.load(entry)
    try:
        await device.async_update()
    except CommandTimeoutError:
        raise DeviceUnreachable(f"« {entry.name} » ne répond pas.")
    return device


async def load_or_status(home, entry):
    """(appareil, None) si chargé, sinon (None, raison affichable)."""
    try:
        return await load_fresh(home, entry), None
    except DeviceOffline:
        return None, "hors ligne"
    except DeviceUnreachable:
        return None, "ne répond pas"


def print_list(entries, loaded):
    rows = []  # (nom, type, état)
    for entry, (device, status) in zip(entries, loaded):
        rows.append((entry.name, entry.type, status or describe_state(device)))
        sorties = outlets(device) if device else []
        for i, outlet in enumerate(sorties):
            branch = "└" if i == len(sorties) - 1 else "├"
            rows.append((f"  {branch} {outlet.name}", "", describe_state(device, outlet.index)))
    width = max((len(name) for name, _, _ in rows), default=0)
    for name, type_, state in rows:
        print(f"{name:<{width}}  {type_:<8}  {state}")


async def open_tui(home):
    from .tui import MerossApp  # import tardif : Textual n'est utile qu'en mode interactif

    await MerossApp(home).run_async()


async def run(words, connect, run_tui=open_tui):
    if not words:
        print("Connexion à Meross…", file=sys.stderr)
    async with connect() as home:
        if not words:
            await run_tui(home)
            return
        if [w.lower() for w in words] == ["list"]:
            entries = sorted(home.entries, key=lambda e: e.name.casefold())
            # En parallèle : un appareil lent ne retarde pas les autres.
            print_list(entries, await asyncio.gather(*(load_or_status(home, e) for e in entries)))
            return

        target, action = parse_command(home.entries, words)
        if action is None:
            device = await load_fresh(home, target.entry)
            print(f"{target.label} : {describe_state(device, target.channel)}")
        else:
            ensure_online(target.entry)
            await apply(await home.load(target.entry), dataclasses.replace(action, channel=target.channel))
            print(f"{target.label} : {words[-1].lower()} ✓")


def main(argv=None, connect=None, run_tui=open_tui):
    args = build_parser().parse_args(argv)
    if connect is None:
        from .session import connect

    # meross-iot ne fonctionne pas avec la boucle Proactor par défaut de Windows.
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    try:
        asyncio.run(run(args.words, connect, run_tui), loop_factory=loop_factory)
    except (DeviceNotFound, AmbiguousName, UnsupportedAction, DeviceOffline, DeviceUnreachable, SessionError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    except CommandTimeoutError:
        print("Erreur : l'appareil n'a pas répondu à temps.", file=sys.stderr)
        return 1
    return 0
