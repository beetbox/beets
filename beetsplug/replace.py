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

        itemList = []
        i = 0
        items = lib.items(itemQuery)
        for item in items:
            i += 1
            itemList.append(item)
            print(f"{i}. {item}")

        index = int(input("Which song would you like to replace? "))
        song = itemList[index-1]

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
