var BEETS_HOST = 'localhost';
var BEETS_PORT = 8337;

var BeetsResolver = Tomahawk.extend(TomahawkResolver,
{
    settings:
    {
        name: 'beets',
        weight: 95,
        timeout: 5
    },
    resolve: function( qid, artist, album, title )
    {
        this.beetsQuery(qid,
            ['artist:' + artist, 'album:' + album, 'title:' + title]
        );
    },
    search: function( qid, searchString )
    {
        this.beetsQuery(qid, searchString.split(' '));
    },
    beetsQuery: function( qid, queryParts )
    {
        var url = 'http://' + BEETS_HOST + ':' + BEETS_PORT + '/item/query/';
        for (var i = 0; i < queryParts.length; ++i) {
            url += encodeURIComponent(queryParts[i]);
            url += '/';
        }
        url = url.substring(0, url.length - 1);  // Remove last /.

        Tomahawk.asyncRequest(url, function(xhr) {
            var resp = JSON.parse(xhr.responseText);
            var items = resp['results'];

            var searchResults = [];
            for (var i = 0; i < items.length; ++i) {
                item = items[i];
                searchResults.push({
                    artist: item['artist'],
                    album: item['album'],
                    track: item['title'],
                    albumpos: item['track'],
                    source: "beets",
                    url: "http://" + BEETS_HOST + ':' + BEETS_PORT + '/item/' + item['id'] + '/file',
                    bitrate: Math.floor(item['bitrate'] / 1024),
                    duration: Math.floor(item['length']),
                    size: 83375, //!
                    score: 1.0,
                    extension: "mp3", //!
                    mimetype: "audio/mpeg", //!
                    year: item['year']
                });
            }

            Tomahawk.addTrackResults({
                qid: qid,
                results: searchResults
            })
        });
    }
});

Tomahawk.resolver.instance = BeetsResolver;
