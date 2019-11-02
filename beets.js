var INTERVAL_INITIAL = 7000;
var INTERVAL_SUBSEQUENT = 5000;
var BEETS_IS = [
    'the media library management system for obsessive music geeks',
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

$(function() {
    setTimeout(updateBeetsis, INTERVAL_INITIAL);
});
