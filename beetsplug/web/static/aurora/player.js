function Player(root) {

    var events = {},
        state = 'disabled';

    var seekBar = (function() {

        var played = root.querySelector('.currentTime'),
            currentTime = 0,
            trackLength = 0,
            oldSeconds = 0;

        function pad(input) {
            return ('00' + input).slice(-2);
        }

        return {
            getTrackLength: function() {
                return trackLength;
            },

            setTrackLength: function(time) {
                trackLength = time;
                this.seekTime = currentTime;
            },

            getCurrentTime: function() {
                return currentTime;
            },

            setCurrentTime: function(time) {
                oldSeconds = Math.floor(currentTime / 1000 % 60);
                currentTime = time;

                if (currentTime >= trackLength && trackLength > 0) {
                    emit('end');
                }

                var t = currentTime / 1000,
                    seconds = Math.floor(t % 60),
                    minutes = Math.floor((t /= 60) % 60);

                if (seconds === oldSeconds) {
                    return;
                }

                played.innerHTML = minutes + ':' + pad(seconds);

            }
        }

    })();

    var playpause = (function() {

        var buttonPlay = root.querySelector('.play'),
            buttonPause = root.querySelector('.pause'),
            playing = 'disabled';

        buttonPlay.onclick = function() {
            emit('play');
        };

        buttonPause.onclick = function() {
            emit('pause');
        };

        function setPlaying(play) {
            root.setAttribute('data-status', play);
            playing = play;
        }

        setPlaying(playing);

        return {
            setPlaying: setPlaying,
            getPlaying: function() {
                return playing;
            }
        }

    })();

    function emit(event) {
        if (!events[event]) {
            return;
        }

        var args = Array.prototype.slice.call(arguments, 1),
            callbacks = events[event];

        for (var i = 0, len = callbacks.length; i < len; i++) {
            callbacks[i].apply(null, args);
        }
    }

    var API = {
        on: function(event, fn) {
            events[event] || (events[event] = []);
            events[event].push(fn);
        },

        off: function(event, fn) {
            var eventsOf = events[event],
                index = eventsOf.indexOf(fn);

            ~index && eventsOf.splice(index, 1);
        }
    };

    Object.defineProperty(API, 'state', {
        set: function(newstate) {
            playpause.setPlaying(newstate);
            state = newstate;
        },

        get: function() {
            return state;
        }
    });

    Object.defineProperty(API, 'duration', {
        get: seekBar.getTrackLength,
        set: seekBar.setTrackLength
    });

    Object.defineProperty(API, 'seekTime', {
        get: seekBar.getCurrentTime,
        set: seekBar.setCurrentTime
    });

    return API;

}