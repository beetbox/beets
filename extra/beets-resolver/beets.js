var BeetsResolver = Tomahawk.extend(TomahawkResolver,
{
    // Basic setup.
    settings:
    {
        name: 'beets',
        weight: 95,
        timeout: 5
    },

    // Resolution.
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
    baseUrl: function() {
        return 'http://' + this.host + ':' + this.port;
    },
    beetsQuery: function( qid, queryParts )
    {
        var baseUrl = this.baseUrl();
        var url = baseUrl + '/item/query/';
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
                    url: baseUrl + '/item/' + item['id'] + '/file',
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
    },

    // Configuration.
    getConfigUi: function () {
        var uiData = Tomahawk.readBase64("config.ui");
        return {
            "widget": uiData,
            "fields": [{
                name: "host",
                widget: "hostField",
                property: "text"
            }, {
                name: "port",
                widget: "portField",
                property: "text"
            }]
        };
    },
    newConfigSaved: function () {
        var userConfig = this.getUserConfig();

        this.host = userConfig.host || 'localhost';

        var port = userConfig.port;
        port = parseInt(port);
        if (isNaN(port) || !port) {
            port = 8337;
        }
        userConfig.port = port;

        this.port = port;
    },

    // Defaults.
    host: 'localhost',
    port: 8337
});

Tomahawk.resolver.instance = BeetsResolver;
