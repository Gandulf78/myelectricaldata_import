"""Server configuration."""
import inspect

from database.config import DatabaseConfig
from utils import edit_config, str2bool


class HomeAssistant:
    """Home Assistant configuration."""

    def __init__(self, config: dict, write: bool = True) -> None:
        self.config: dict = config
        self.write: dict = write
        self.db = DatabaseConfig()
        # LOCAL PROPERTIES
        self._enable: bool = None
        self._discovery_prefix: str = None
        # PROPERTIES
        self.key: str = "home_assistant"
        self.json: dict = {}
        self.comments = {"home_assistant": 'Configuration pour le "MQTT Discovery" de Home Assistant.'}
        # FUNCTION
        self.load()

    def default(self) -> dict:
        """Return configuration as dictionary."""
        return {"enable": False, "discovery_prefix": "homeassistant"}

    def load(self) -> dict:
        """Load configuration from file."""
        try:
            sub_key = "enable"
            self.change(sub_key, str2bool(self.config[self.key][sub_key]), False)
        except Exception:
            self.change(sub_key, self.default()[sub_key], False)
        try:
            sub_key = "discovery_prefix"
            self.change(sub_key, self.config[self.key][sub_key], False)
        except Exception:
            self.change(sub_key, self.default()[sub_key], False)

        # Save configuration
        if self.write:
            edit_config(data={self.key: self.json}, comments=self.comments)
            self.db.set(self.key, self.json)

    def change(self, key: str, value: str, write_file: bool = True) -> None:
        """Change configuration."""
        setattr(self, f"_{key}", value)
        self.json[key] = value
        if write_file:
            edit_config({self.key: {key: value}})
            current_config = self.db.get(self.key)
            new_config = {**current_config, **{key: value}}
            self.db.set(self.key, new_config)

    @property
    def enable(self) -> bool:
        """Home Assistant enable."""
        return self._enable

    @enable.setter
    def enable(self, value):
        self.change(inspect.currentframe().f_code.co_name, value)

    @property
    def discovery_prefix(self) -> str:
        """Home Assistant MQTT discovery prefix."""
        return self._discovery_prefix

    @discovery_prefix.setter
    def discovery_prefix(self, value):
        self.change(inspect.currentframe().f_code.co_name, value)
