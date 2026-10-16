import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values
from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager
from meross_iot.model.credentials import MerossCloudCreds
from meross_iot.model.enums import OnlineStatus
from meross_iot.model.exception import CommandTimeoutError
from meross_iot.model.http.exception import (
    BadLoginException,
    HttpApiError,
    MissingMFA,
    TokenExpiredException,
    TooManyTokensException,
    UnauthorizedException,
)

# ~/.meross sur Linux, C:\Users\<toi>\.meross sur Windows
CONFIG_DIR = Path.home() / ".meross"
CREDS_FILE = "credentials.json"
DEFAULT_API_URL = "https://iotx-eu.meross.com"
# Un appareil sain répond en ~1 s ; au-delà on abandonne plutôt que d'attendre les 10 s de la lib.
LOAD_TIMEOUT = 4


class SessionError(Exception):
    pass


class DeviceUnreachable(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    email: str
    password: str
    api_url: str


def load_settings(config_dir=CONFIG_DIR):
    """Variables d'environnement > .env du dossier courant > .env du dossier de config."""
    values = {
        **dotenv_values(Path(config_dir) / ".env"),
        **dotenv_values(Path.cwd() / ".env"),
        **{k: v for k, v in os.environ.items() if k.startswith("MEROSS_")},
    }
    email, password = values.get("MEROSS_EMAIL"), values.get("MEROSS_PASSWORD")
    if not email or not password:
        raise SessionError(
            f"identifiants Meross manquants. Crée {Path(config_dir) / '.env'} avec :\n"
            "  MEROSS_EMAIL=ton@email.com\n  MEROSS_PASSWORD=ton_mot_de_passe"
        )
    return Settings(email, password, values.get("MEROSS_API_URL") or DEFAULT_API_URL)


def load_cached_creds(config_dir=CONFIG_DIR):
    path = Path(config_dir) / CREDS_FILE
    try:
        return MerossCloudCreds.from_json(path.read_text())
    except (OSError, ValueError, TypeError):
        return None


def save_creds(config_dir, creds):
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / CREDS_FILE
    path.write_text(creds.to_json())
    path.chmod(0o600)  # le token donne accès au compte ; sans effet sous Windows


async def _http_client(settings, config_dir):
    # On réutilise le token en cache : un login complet est lent et Meross limite
    # le nombre de tokens actifs par compte (TooManyTokensException).
    creds = load_cached_creds(config_dir)
    if creds is not None and creds.user_email.casefold() == settings.email.casefold():
        try:
            return await MerossHttpClient.async_from_cloud_creds(creds)
        except (UnauthorizedException, TokenExpiredException, HttpApiError, BadLoginException):
            pass  # token périmé : on refait un login

    try:
        client = await MerossHttpClient.async_from_user_password(
            api_base_url=settings.api_url, email=settings.email, password=settings.password
        )
    except MissingMFA:
        raise SessionError("ton compte a la double authentification activée, non gérée pour l'instant.")
    except BadLoginException:
        raise SessionError("login Meross refusé : vérifie MEROSS_EMAIL / MEROSS_PASSWORD.")
    except TooManyTokensException:
        raise SessionError("trop de sessions ouvertes sur le compte Meross, réessaie plus tard.")
    save_creds(config_dir, client.cloud_credentials)
    return client


@dataclass(frozen=True)
class Entry:
    """Un appareil tel que listé par le cloud (y compris hors ligne), avant toute connexion MQTT."""
    name: str
    type: str
    online_status: OnlineStatus
    uuid: str
    outlets: tuple = ()  # ((index, nom), ...) des sorties d'une multiprise, connues sans connexion MQTT


def _outlets(http_device):
    # Le canal 0 (« tout l'appareil ») est un dict vide ; les sorties ont un devName.
    return tuple((i, c["devName"]) for i, c in enumerate(http_device.channels or []) if i > 0 and c.get("devName"))


class Home:
    """Liste cloud des appareils + chargement MQTT à la demande.

    La découverte complète de meross-iot interroge les appareils un par un : un seul appareil
    muet (ex. un ms600 mal géré par la lib) bloque alors tout le monde 10 s. On ne découvre donc
    que les appareils dont on a besoin, avec un timeout court.
    """

    def __init__(self, manager, http_devices):
        self._manager = manager
        self._http_devices = http_devices
        self.entries = [Entry(h.dev_name, h.device_type, h.online_status, h.uuid, _outlets(h)) for h in http_devices]

    async def load(self, entry, timeout=LOAD_TIMEOUT):
        try:
            await asyncio.wait_for(
                self._manager.async_device_discovery(
                    update_subdevice_status=False,
                    meross_device_uuid=entry.uuid,
                    cached_http_device_list=self._http_devices,
                ),
                timeout,
            )
        except (asyncio.TimeoutError, CommandTimeoutError):
            pass
        found = self._manager.find_devices(device_uuids=[entry.uuid])
        if not found:
            raise DeviceUnreachable(f"« {entry.name} » ({entry.type}) ne répond pas.")
        return found[0]


@asynccontextmanager
async def connect(config_dir=CONFIG_DIR):
    # meross-iot fait un logging.basicConfig(stream=sys.stdout) à l'import : sans ça,
    # ses erreurs internes polluent la sortie de chaque commande.
    if not os.environ.get("MEROSS_DEBUG"):
        logging.getLogger("meross_iot").setLevel(logging.CRITICAL)

    settings = load_settings(config_dir)
    client = await _http_client(settings, config_dir)
    manager = MerossManager(http_client=client)
    try:
        yield Home(manager, await client.async_list_devices())
    finally:
        # Pas de logout : il invaliderait le token qu'on garde en cache.
        manager.close()
        await _wait_mqtt_shutdown(manager)


async def _wait_mqtt_shutdown(manager):
    """close() déconnecte MQTT sans attendre : le thread paho rappelle ensuite la boucle asyncio
    (_on_disconnect) alors qu'asyncio.run l'a déjà fermée → warnings et exception de thread.
    On attend donc la fin des threads paho, puis on laisse la boucle traiter ce qu'ils ont programmé."""
    for client in manager._mqtt_clients.values():  # attribut privé : pas d'API publique pour ça
        await asyncio.to_thread(client.loop_stop)
    await asyncio.sleep(0.1)
