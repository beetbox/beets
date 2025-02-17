from beets.plugins import BeetsPlugin
from beets import ui
import mediafile
import shutil
from pathlib import Path

class ReplacePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('replace', help='This command replaces the target audio file, while keeping tags intact')
        cmd.func = self.run
        return [cmd]
    def run(self, lib, opts, args):
        newFilePath = Path(args[-1])
        itemQuery = args[:-1]

        self.file_check(newFilePath)

        itemList = list(lib.items(itemQuery))

        if not itemList:
            raise ui.UserError("No matching songs found.")
        
        song = self.select_song(itemList)

        if not self.confirm_replacement(newFilePath, song):
            print("Aborting replacement.")
            return

        self.replace_file(newFilePath, song)

    def file_check(self, file):
        """Check if the file exists and is supported"""
        if not file.is_file():
            raise ui.UserError(f"'{file}' is not a valid file.")

        try:
            f = mediafile.MediaFile(str(file))
        except mediafile.FileTypeError as fte:
            raise ui.UserError(fte)


    def select_song(self, items):
        """Present a menu of matching songs and get user selection."""
        print("Matching songs:")
        for i, item in enumerate(items):
            print(f"{i+1}. {item}")

        while True:
            try:
                index = int(input(f"Which song would you like to replace? [1-{len(items)}]: "))
                if 1 <= index <= len(items):
                    return items[index - 1]
                print(f"Invalid choice. Please enter a number between 1 and {len(items)}.")
            except ValueError:
                print("Invalid input. Please type in a number.")

    def confirm_replacement(self, newFilePath, song):
        """Get user confirmation for the replacement."""
        originalFilePath = Path(song.path.decode())
        print(f"\nReplacing: {newFilePath} -> {originalFilePath}")
        decision = input("Are you sure you want to replace this track? (yes/no): ").strip().casefold()
        return decision in {"yes", "y"}

    def replace_file(self, newFilePath, song):
        """Replace the existing file with the new one."""
        originalFilePath = Path(song.path.decode())
        dest = originalFilePath.with_suffix(newFilePath.suffix)
        
        try:
            shutil.move(newFilePath, dest)
        except Exception as e:
            raise ui.UserError(f"Error replacing file: {e}")

        if newFilePath.suffix != originalFilePath.suffix:
            originalFilePath.unlink()

        song.path = str(dest).encode()
        song.store()

        print("Replacement successful.")
