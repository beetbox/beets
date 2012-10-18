var INTERVAL_INITIAL = 7000;
var INTERVAL_SUBSEQUENT = 5000;
var BEETS_IS = [
    'the media library management system for obsessive-compulsive music geeks',
    'an infinitely flexible automatic metadata corrector and file renamer',
    'the best command-line tool for viewing, querying, and renaming your music collection',
    'an album art downloader, lyrics fetcher, and genre identifier',
    'a simple music metadata inspection and modification tool for tons of audio file types',
    'an MPD-compatible music player',
    'a Web-based collection explorer and HTML5 music player',
    'grep for your music collection',
    'a batch audio file transcoder'
];

// Cycle "Beets is..." text.
var beetsisIndex = 0;
function updateBeetsis() {
    beetsisIndex++;
    if (beetsisIndex >= BEETS_IS.length)
        beetsisIndex = 0;
    var message = BEETS_IS[beetsisIndex] + '.';
    $('#beetsis').fadeOut(function() {
        $(this).text(message).fadeIn();
        setTimeout(updateBeetsis, INTERVAL_SUBSEQUENT);
    });
}

// Fetch and display the latest messages from the Twitter account.
var NEWS_COUNT = 3;
var MONTH_NAMES = [ "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December" ];
var urlre = /(http:\/\/([^ \/]+)(\/\S+)?)\b/g;
function getNews() {
    var url = 'http://pipes.yahoo.com/pipes/pipe.run'
    var args = {
        _id: '6a14ac0e3884a3913d16bbc4d0811322',
        _render: 'json',
        _callback: 'jsonpCallback'
    };
    $.ajax({
        url: url,
        data: args,
        type: 'GET',
        dataType: 'jsonp',
        jsonpCallback: 'jsonpCallback',
        success: function(data) {
            // Find the first non-reply status. This assumes there's at least
            // one non-reply in this chunk... probably a reasonable assumption.
            $('#twitterStatus').empty();
            var count = 0;
            $.each(data['value']['items'], function(i, status) {
                console.log(status);
    			if (status.in_reply_to_screen_name == null) {
    				// Not a reply.

    				var text = status.text;
                    text = text.replace(urlre, "<a href=\"$1\">link&nbsp;&raquo;</a>");

                    var date = new Date(Date.parse(status.created_at));
                    date = MONTH_NAMES[date.getMonth()] + ' ' + date.getDate();

                    $('#twitterStatus').append(
                        '<li><span class="date">' + date + ':</span> ' +
                        text + '</li>'
                    );
                    count++;
                    if (count >= NEWS_COUNT)
                        return false; // break
    			}
    		});
        },
    });
}

$(function() {
    setTimeout(updateBeetsis, INTERVAL_INITIAL);
    getNews();
});
