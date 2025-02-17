from beets.plugins import BeetsPlugin
from beets import ui
import mediafile
import shutil
from pathlib import Path

class ReplacePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('replace', help='replace audio file while keeping tags')
        cmd.func = self.run
        return [cmd]
    def run(self, lib, opts, args):
        if len(args) < 2:
            raise ui.UserError(f"Usage: beet replace <query> <new_file_path>")

        newFilePath = Path(args[-1])
        itemQuery = args[:-1]

        self.file_check(newFilePath)

        itemList = list(lib.items(itemQuery))

        if not itemList:
            raise ui.UserError("No matching songs found.")
        
        song = self.select_song(itemList)

        if not song:
            print("Operation cancelled.")
            return

        if not self.confirm_replacement(newFilePath, song):
            print("Aborting replacement.")
            return

        self.replace_file(newFilePath, song)

    def file_check(self, file):
        """Check if the file exists and is supported"""
        if not file.is_file():
            raise ui.UserError(f"'{file}' is not a valid file.")

        try:
           mediafile.MediaFile(str(file))
        except mediafile.FileTypeError as fte:
            raise ui.UserError(fte)


    def select_song(self, items):
        """Present a menu of matching songs and get user selection."""
        print("\nMatching songs:")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}")

        while True:
            try:
                index = int(input(f"Which song would you like to replace? [1-{len(items)}] (0 to cancel): "))
                if index == 0:
                    return None
                if 1 <= index <= len(items):
                    return items[index - 1]
                print(f"Invalid choice. Please enter a number between 1 and {len(items)}.")
            except ValueError:
                print("Invalid input. Please type in a number.")

    def confirm_replacement(self, newFilePath, song):
        """Get user confirmation for the replacement."""
        originalFilePath = Path(song.path.decode())

        if not originalFilePath.exists():
            raise ui.UserError(f"The original song file was not found.")

        print(f"\nReplacing: {newFilePath} -> {originalFilePath}")
        decision = input("Are you sure you want to replace this track? (y/N): ").strip().casefold()
        return decision in {"yes", "y"}

    def replace_file(self, newFilePath, song):
        """Replace the existing file with the new one."""
        originalFilePath = Path(song.path.decode())
        dest = originalFilePath.with_suffix(newFilePath.suffix)
        
        try:
            shutil.move(newFilePath, dest)
        except Exception as e:
            raise ui.UserError(f"Error replacing file: {e}")

        if newFilePath.suffix != originalFilePath.suffix and originalFilePath.exists():
            try:
                originalFilePath.unlink()
            except Exception as e:
                raise ui.UserError(f"Could not delete original file: {e}")

        song.path = str(dest).encode()
        song.store()

        print("Replacement successful.")
