from beets.plugins import BeetsPlugin
from beets import ui
import mediafile
import os
import sys

class ReplacePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('replace', help='This command replaces the target audio file, while keeping tags intact')
        cmd.func = self.run
        return [cmd]
    def run(self, lib, opts, args):
        newFilePath = args[-1]
        itemQuery = args[:-1]

        if not os.path.isfile(newFilePath):
            print("Input path is not a file.")
            sys.exit(1)

        try:
            f = mediafile.MediaFile(newFilePath)
        except mediafile.FileTypeError as fte:
            print("This file type is not supported. Error:", fte)
            sys.exit(1)

        itemList = list(lib.items(itemQuery))

        if not itemList:
            print(f"Error: No matching songs found.")
            sys.exit(1)
        
        song = self.select_song(itemList)

        if not self.confirm_replacement(newFilePath, song):
            print("Aborting replacement.")
            sys.exit(0)

        self.replace_file(newFilePath, song)

    def select_song(self, items):
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
        print(f"\nReplacing: {newFilePath} -> {song.destination().decode()}")
        decision = input("Are you sure you want to replace this track? (yes/no): ").strip().casefold()
        return decision in {"yes", "y"}

    def replace_file(self, newFilePath, song):
        originalFilePath = song.path.decode()
        originalFileBase, originalFileExt = os.path.splitext(originalFilePath)
        newFileBase, newFileExt = os.path.splitext(newFilePath)

        dest = originalFileBase + newFileExt
        
        try:
            os.rename(newFilePath, dest)
        except OSError as e:
            print(f"Error renaming file: {e}")
            sys.exit(1)

        if newFileExt != originalFileExt:
            os.remove(originalFilePath)

        song.path = dest.encode()
        song.store()

        print("Replacement successful.")
