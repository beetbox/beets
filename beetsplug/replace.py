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
        title = args[:-1]

        song = lib.items(title)[0]
        song.write(newFilePath)
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
