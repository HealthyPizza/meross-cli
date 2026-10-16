# meross-cli

Pilote tes lumières et volets Meross depuis le terminal (Linux et Windows), via le cloud Meross
et la lib [meross-iot](https://github.com/albertogeniola/MerossIot).

```
meross                         # appli interactive plein écran (voir plus bas)
meross list                    # liste les appareils et leur état
meross bureau on               # allume (alias : enable)
meross bureau off              # éteint (alias : disable)
meross volet ouest 50          # volet à 50 %
meross volet ouest open        # ouvre (aussi : close, stop)
meross volet ouest             # affiche l'état
```

Les noms sont ceux de l'appli Meross, sans tenir compte de la casse. Pas besoin de guillemets pour
les noms en plusieurs mots.

Multiprise : chaque sortie se vise par son nom (tel que dans l'appli Meross), seul ou préfixé du nom
de la multiprise. Le nom de la multiprise seul agit sur toutes les sorties.

```
meross switch 4 off            # une sortie (si son nom est unique)
meross multiprise usb on       # une sortie, sans ambiguïté
meross multiprise off          # toutes les sorties
```

Si la phrase entière correspond à un nom, on affiche son état plutôt que d'agir : `meross switch 4`
consulte la sortie 4, et ne règle pas « switch » à 4 %.

## Appli interactive

`meross` sans argument ouvre une interface plein écran : la liste des appareils à gauche, les
actions de l'appareil sélectionné à droite. Les états se mettent à jour en direct, même quand un
appareil est actionné depuis l'appli Meross ou un interrupteur.

| Touche | Lumières / prises | Volets |
|---|---|---|
| `↑` `↓` | choisir un appareil | choisir un appareil |
| `o` | allumer | ouvrir |
| `f` | éteindre | — |
| `Entrée` / `espace` | basculer | — |
| `c` / `s` | — | fermer / stop |
| `←` `→` | — | -10 % / +10 % |
| `p` | — | position précise |
| `1`…`9` | multiprise : basculer la sortie n | — |
| `r` / `q` | rafraîchir / quitter | rafraîchir / quitter |

## Installation

1. Installe [uv](https://docs.astral.sh/uv/) :
   - Linux : `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell) : `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Depuis ce dossier : `uv tool install .` (la commande `meross` est alors disponible partout).
   Après une modif du code : `uv tool install --reinstall .`
3. Mets tes identifiants dans `~/.meross/.env` (Windows : `C:\Users\<toi>\.meross\.env`), voir `.env.example`.

## Fonctionnement

- Le premier appel fait un login. Le token est ensuite gardé dans `~/.meross/credentials.json` et
  réutilisé, ce qui va plus vite et évite la limite de sessions de Meross. Supprime ce fichier pour
  forcer un nouveau login.
- Ordre de priorité des identifiants : variables d'environnement, puis `.env` du dossier courant,
  puis `~/.meross/.env`.
- `MEROSS_DEBUG=1` affiche les logs de meross-iot.

## Développement

```
uv run pytest        # tests (faux appareils, pas d'appel au cloud)
uv run meross list   # lancer sans installer
```
