"""Updates a Sonos library whenever the beets library is changed.
This is based on the Kodi Update plugin.
"""

import soco

from beets.plugins import BeetsPlugin


class SonosUpdate(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.register_listener("database_change", self.listen_for_db_change)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change and register the update"""
        self.register_listener("cli_exit", self.update)

    def update(self, lib):
        """When the client exists try to send refresh request to a Sonos
        controller.
        """
        self._log.info("Requesting a Sonos library update...")

        device = soco.discovery.any_soco()

        if device:
            device.music_library.start_library_update()
        else:
            self._log.warning("Could not find a Sonos device.")
            return

        self._log.info("Sonos update triggered")
