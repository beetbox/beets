function AuroraConnector(auroraPlayer, PlayerUI) {

    PlayerUI.seekTime = 0;
    PlayerUI.duration = 0;
    PlayerUI.bufferProgress = 0;

    var onplay,
        onpause,
        onvolume,
        onformat,
        onbuffer,
        onprogress,
        onduration,
        onerror;

    PlayerUI.on('play', onplay = function() {
        auroraPlayer.play();
        PlayerUI.state = 'playing';
    });

    PlayerUI.on('pause', onpause = function() {
        auroraPlayer.pause();
        PlayerUI.state = 'paused';
    });

    PlayerUI.on('volume', onvolume = function(value) {
        auroraPlayer.volume = value;
    });

    auroraPlayer.on('buffer', onbuffer = function(percent) {
        PlayerUI.bufferProgress = percent;
    });

    auroraPlayer.on('progress', onprogress = function(time) {
        PlayerUI.seekTime = time;
    });

    auroraPlayer.on('duration', onduration = function(duration) {
        PlayerUI.duration = duration;
    });

    auroraPlayer.on('error', onerror = function(e) {
        // reset state
        PlayerUI.state = 'disabled';
        PlayerUI.duration = 0;
        PlayerUI.bufferProgress = 0;
        PlayerUI.seekTime = 0;
    });

    auroraPlayer.volume = PlayerUI.volume;
    auroraPlayer.play();
    PlayerUI.state = 'playing';

    this.disconnect = function() {
        if (auroraPlayer) auroraPlayer.stop();

        PlayerUI.off('play', onplay);
        PlayerUI.off('pause', onpause);
        PlayerUI.off('volume', onvolume);
        PlayerUI.state = 'disabled';
        auroraPlayer.off('buffer', onbuffer);
        auroraPlayer.off('format', onformat);
        auroraPlayer.off('progress', onprogress);
        auroraPlayer.off('duration', onduration);
    }
}