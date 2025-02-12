from beets.plugins import BeetsPlugin
from beets import ui
import os

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
            exit()

        itemList = []
        i = 0
        items = lib.items(itemQuery)
        for item in items:
            i += 1
            itemList.append(item)
            print(f"{i}. {item}")

        if len(itemList) == 0:
            print(f"No song found for this query.")
            exit()

        while True:
            try:
                index = int(input(f"Which song would you like to replace? [1-{len(itemList)}]: "))
                break
            except ValueError:
                print("Please type in a number.")

        song = itemList[index-1]

        print(f"{newFilePath} -> {song.destination().decode()}")
        decision = input("Are you sure you want to replace this track? Yes/No: ")

        if decision not in ("yes", "Yes", "y", "Y"):
            print("Not doing anything. Exiting!")
            exit()

        if not song.try_write(newFilePath):
            print("Not a supported file.")
            exit()

        originalFilePath = song.path.decode()

        originalFileBase, originalFileExt = os.path.splitext(originalFilePath)
        newFileBase, newFileExt = os.path.splitext(newFilePath)

        dest = originalFileBase + newFileExt
        destEncoded = dest.encode()
        
        os.rename(newFilePath, dest)

        if newFileExt != originalFileExt:
            os.remove(originalFilePath)

        song.path = destEncoded
        song.store()
