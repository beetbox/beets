"""Filter imported files using a regular expression."""

import re

from beets import config
from beets.importer import SingletonImportTask
from beets.plugins import BeetsPlugin
from beets.util import bytestring_path


class FileFilterPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.register_listener(
            "import_task_created", self.import_task_created_event
        )
        self.config.add({"path": ".*"})

        self.path_album_regex = self.path_singleton_regex = re.compile(
            bytestring_path(self.config["path"].get())
        )

        if "album_path" in self.config:
            self.path_album_regex = re.compile(
                bytestring_path(self.config["album_path"].get())
            )

        if "singleton_path" in self.config:
            self.path_singleton_regex = re.compile(
                bytestring_path(self.config["singleton_path"].get())
            )

    def import_task_created_event(self, session, task):
        if task.items and len(task.items) > 0:
            items_to_import = []
            for item in task.items:
                if self.file_filter(item["path"]):
                    items_to_import.append(item)
            if len(items_to_import) > 0:
                task.items = items_to_import
            else:
                # Returning an empty list of tasks from the handler
                # drops the task from the rest of the importer pipeline.
                return []

        elif isinstance(task, SingletonImportTask):
            if not self.file_filter(task.item["path"]):
                return []

        # If not filtered, return the original task unchanged.
        return [task]

    def file_filter(self, full_path):
        """Checks if the configured regular expressions allow the import
        of the file given in full_path.
        """
        import_config = dict(config["import"])
        full_path = bytestring_path(full_path)
        if "singletons" not in import_config or not import_config["singletons"]:
            # Album
            return self.path_album_regex.match(full_path) is not None
        # Singleton
        return self.path_singleton_regex.match(full_path) is not None
