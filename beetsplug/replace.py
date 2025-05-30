import shutil
from pathlib import Path

import mediafile

from beets import ui, util
from beets.library import Item, Library
from beets.plugins import BeetsPlugin


class ReplacePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand(
            "replace", help="replace audio file while keeping tags"
        )
        cmd.func = self.run
        return [cmd]

    def run(self, lib: Library, args: list[str]) -> None:
        if len(args) < 2:
            raise ui.UserError("Usage: beet replace <query> <new_file_path>")

        new_file_path: Path = Path(args[-1])
        item_query: list[str] = args[:-1]

        self.file_check(new_file_path)

        item_list = list(lib.items(item_query))

        if not item_list:
            raise ui.UserError("No matching songs found.")

        song = self.select_song(item_list)

        if not song:
            ui.print_("Operation cancelled.")
            return

        if not self.confirm_replacement(new_file_path, song):
            ui.print_("Aborting replacement.")
            return

        self.replace_file(new_file_path, song)

    def file_check(self, filepath: Path) -> None:
        """Check if the file exists and is supported"""
        if not filepath.is_file():
            raise ui.UserError(
                f"'{util.displayable_path(filepath)}' is not a valid file."
            )

        try:
            mediafile.MediaFile(util.syspath(filepath))
        except mediafile.FileTypeError as fte:
            raise ui.UserError(fte)

    def select_song(self, items: list[Item]):
        """Present a menu of matching songs and get user selection."""
        ui.print_("\nMatching songs:")
        for i, item in enumerate(items, 1):
            ui.print_(f"{i}. {util.displayable_path(item)}")

        while True:
            try:
                index = int(
                    input(
                        f"Which song would you like to replace? "
                        f"[1-{len(items)}] (0 to cancel): "
                    )
                )
                if index == 0:
                    return None
                if 1 <= index <= len(items):
                    return items[index - 1]
                ui.print_(
                    f"Invalid choice. Please enter a number "
                    f"between 1 and {len(items)}."
                )
            except ValueError:
                ui.print_("Invalid input. Please type in a number.")

    def confirm_replacement(self, new_file_path: Path, song: Item):
        """Get user confirmation for the replacement."""
        original_file_path: Path = Path(song.path.decode())

        if not original_file_path.exists():
            raise ui.UserError("The original song file was not found.")

        ui.print_(
            f"\nReplacing: {util.displayable_path(new_file_path)} "
            f"-> {util.displayable_path(original_file_path)}"
        )
        decision: str = (
            input("Are you sure you want to replace this track? (y/N): ")
            .strip()
            .casefold()
        )
        return decision in {"yes", "y"}

    def replace_file(self, new_file_path: Path, song: Item) -> None:
        """Replace the existing file with the new one."""
        original_file_path = Path(song.path.decode())
        dest = original_file_path.with_suffix(new_file_path.suffix)

        try:
            shutil.move(util.syspath(new_file_path), util.syspath(dest))
        except Exception as e:
            raise ui.UserError(f"Error replacing file: {e}")

        if (
            new_file_path.suffix != original_file_path.suffix
            and original_file_path.exists()
        ):
            try:
                original_file_path.unlink()
            except Exception as e:
                raise ui.UserError(f"Could not delete original file: {e}")

        song.path = str(dest).encode()
        song.store()

        ui.print_("Replacement successful.")
