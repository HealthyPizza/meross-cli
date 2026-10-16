import difflib
from dataclasses import dataclass


class DeviceNotFound(Exception):
    def __init__(self, name, suggestions):
        self.name = name
        self.suggestions = suggestions
        message = f"Appareil introuvable : « {name} »"
        if suggestions:
            message += f". Tu voulais dire : {', '.join(suggestions)} ?"
        super().__init__(message)


class AmbiguousName(Exception):
    def __init__(self, name, options):
        self.name = name
        self.options = options
        super().__init__(f"« {name} » est ambigu, précise : {', '.join(options)}")


@dataclass(frozen=True)
class Target:
    """Ce que vise une commande : un appareil, et le canal (0 = tout l'appareil)."""
    entry: object
    channel: int
    label: str


def _normalize(name):
    return " ".join(name.split()).casefold()


def _aliases(entries):
    """Chaque appareil se vise par son nom ; chaque sortie par son nom seul ou préfixé du nom de l'appareil."""
    for entry in entries:
        yield entry.name, Target(entry, 0, entry.name)
        for index, outlet in entry.outlets:
            target = Target(entry, index, f"{entry.name} › {outlet}")
            yield outlet, target
            yield f"{entry.name} {outlet}", target


def resolve(entries, name):
    by_alias = {}
    for alias, target in _aliases(entries):
        by_alias.setdefault(_normalize(alias), []).append(target)

    matches = by_alias.get(_normalize(name), [])
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise AmbiguousName(name, sorted(t.label for t in matches))

    close = difflib.get_close_matches(_normalize(name), by_alias.keys(), n=3, cutoff=0.6)
    labels = list(dict.fromkeys(t.label for alias in close for t in by_alias[alias]))
    raise DeviceNotFound(name, labels)
