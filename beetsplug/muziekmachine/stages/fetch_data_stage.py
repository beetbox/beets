from beetsplug.customspotify import SpotifyPlugin
from beetsplug.customyoutube import YouTubePlugin

class FetchPlatformData:
    def __call__(self, lib):
        self.lib = lib

        sf = SpotifyPlugin()

        spotify_info = sf.retrieve_info(self.lib)

        print(spotify_info)

        all_info = spotify_info
        
        return all_info