// Format times as minutes and seconds.
var timeFormat = function(secs) {
    if (secs == undefined || isNaN(secs)) {
        return '0:00';
    }
    secs = Math.round(secs);
    var mins = '' + Math.round(secs / 60);
    secs = '' + (secs % 60);
    if (secs.length < 2) {
        secs = '0' + secs;
    }
    return mins + ':' + secs;
}

// jQuery extension encapsulating event hookups for audio element controls.
$.fn.player = function(debug) {
    // Selected element should contain an HTML5 Audio element.
    var audio = $('audio', this).get(0);

    // Control elements that may be present, identified by class.
    var playBtn = $('.play', this);
    var pauseBtn = $('.pause', this);
    var disabledInd = $('.disabled', this);
    var timesEl = $('.times', this);
    var curTimeEl = $('.currentTime', this);
    var totalTimeEl  = $('.totalTime', this);
    var sliderPlayedEl = $('.slider .played', this);
    var sliderLoadedEl = $('.slider .loaded', this);

    // Button events.
    playBtn.click(function() {
        audio.play();
    });
    pauseBtn.click(function(ev) {
        audio.pause();
    });

    // Utilities.
    var timePercent = function(cur, total) {
        if (cur == undefined || isNaN(cur) ||
                total == undefined || isNaN(total) || total == 0) {
            return 0;
        }
        var ratio = cur / total;
        if (ratio > 1.0) {
            ratio = 1.0;
        }
        return (Math.round(ratio * 10000) / 100) + '%';
    }

    // Event helpers.
    var dbg = function(msg) {
        if (debug)
            console.log(msg);
    }
    var showState = function() {
        if (audio.duration == undefined || isNaN(audio.duration)) {
            playBtn.hide();
            pauseBtn.hide();
            disabledInd.show();
            timesEl.hide();
        } else if (audio.paused) {
            playBtn.show();
            pauseBtn.hide();
            disabledInd.hide();
            timesEl.show();
        } else {
            playBtn.hide();
            pauseBtn.show();
            disabledInd.hide();
            timesEl.show();
        }
    }
    var showTimes = function() {
        curTimeEl.text(timeFormat(audio.currentTime));
        totalTimeEl.text(timeFormat(audio.duration));

        sliderPlayedEl.css('width',
                timePercent(audio.currentTime, audio.duration));

        // last time buffered
        var bufferEnd = 0;
        for (var i = 0; i < audio.buffered.length; ++i) {
            if (audio.buffered.end(i) > bufferEnd)
                bufferEnd = audio.buffered.end(i);
        }
        sliderLoadedEl.css('width',
                timePercent(bufferEnd, audio.duration));
    }

    // Initialize controls.
    showState();
    showTimes();

    // Bind events.
    $('audio', this).bind({
        playing: function() {
            dbg('playing');
            showState();
        },
        pause: function() {
            dbg('pause');
            showState();
        },
        ended: function() {
            dbg('ended');
            showState();
        },
        progress: function() {
            dbg('progress ' + audio.buffered);
        },
        timeupdate: function() {
            dbg('timeupdate ' + audio.currentTime);
            showTimes();
        },
        durationchange: function() {
            dbg('durationchange ' + audio.duration);
            showState();
            showTimes();
        },
        loadeddata: function() {
            dbg('loadeddata');
        },
        loadedmetadata: function() {
            dbg('loadedmetadata');
        }
    });
}

// Simple selection disable for jQuery.
// Cut-and-paste from:
// http://stackoverflow.com/questions/2700000
$.fn.disableSelection = function() {
    $(this).attr('unselectable', 'on')
           .css('-moz-user-select', 'none')
           .each(function() { 
               this.onselectstart = function() { return false; };
            });
};

$(function() {

// Routes.
var BeetsRouter = Backbone.Router.extend({
    routes: {
        "item/query/:query": "itemQuery",
    },
    itemQuery: function(query) {
        $.getJSON('/item/query/' + query, function(data) {
            var models = _.map(
                data['results'],
                function(d) { return new Item(d); }
            );
            var results = new Items(models);
            app.showItems(results);
        });
    }
});
var router = new BeetsRouter();

// Model.
var Item = Backbone.Model.extend({
    urlRoot: '/item'
});
var Items = Backbone.Collection.extend({
    model: Item
});

// Item views.
var ItemEntryView = Backbone.View.extend({
    tagName: "li",
    template: _.template($('#item-entry-template').html()),
    events: {
        'click': 'select',
        'dblclick': 'play'
    },
    initialize: function() {
        this.playing = false;
    },
    render: function() {
        $(this.el).html(this.template(this.model.toJSON()));
        this.setPlaying(this.playing);
        return this;
    },
    select: function() {
        app.selectItem(this);
    },
    play: function() {
        app.playItem(this.model);
    },
    setPlaying: function(val) {
        this.playing = val;
        if (val)
            this.$('.playing').show();
        else
            this.$('.playing').hide();
    }
});
var ItemDetailView = Backbone.View.extend({
    tagName: "div",
    template: _.template($('#item-detail-template').html()),
    events: {
        'click .play': 'play',
    },
    render: function() {
        $(this.el).html(this.template(this.model.toJSON()));
        return this;
    },
    play: function() {
        app.playItem(this.model);
    }
});

// Main app view.
var AppView = Backbone.View.extend({
    el: $('body'),
    events: {
        'submit #queryForm': 'querySubmit',
    },
    querySubmit: function(ev) {
        ev.preventDefault();
        router.navigate('item/query/' + escape($('#query').val()), true);
    },
    initialize: function() {
        this.playingItem = null;
        this.shownItems = null;

        // Not sure why these events won't bind automatically.
        this.$('audio').bind({
            'play': _.bind(this.audioPlay, this),
            'pause': _.bind(this.audioPause, this),
            'ended': _.bind(this.audioEnded, this)
        });
    },
    showItems: function(items) {
        this.shownItems = items;
        $('#results').empty();
        items.each(function(item) {
            var view = new ItemEntryView({model: item});
            item.entryView = view;
            $('#results').append(view.render().el);
        });
    },
    selectItem: function(view) {
        // Mark row as selected.
        $('#results li').removeClass("selected");
        $(view.el).addClass("selected");

        // Show detail.
        var detailView = new ItemDetailView({model: view.model});
        $('#detail').empty().append(detailView.render().el);
    },
    playItem: function(item) {
        var url = '/item/' + item.get('id') + '/file';
        $('#player audio').attr('src', url);
        $('#player audio').get(0).play();

        if (this.playingItem != null) {
            this.playingItem.entryView.setPlaying(false);
        }
        item.entryView.setPlaying(true);
        this.playingItem = item;
    },

    audioPause: function() {
        this.playingItem.entryView.setPlaying(false);
    },
    audioPlay: function() {
        if (this.playingItem != null)
            this.playingItem.entryView.setPlaying(true);
    },
    audioEnded: function() {
        this.playingItem.entryView.setPlaying(false);

        // Try to play the next track.
        var idx = this.shownItems.indexOf(this.playingItem);
        if (idx == -1) {
            // Not in current list.
            return;
        }
        var nextIdx = idx + 1;
        if (nextIdx >= this.shownItems.size()) {
            // End of  list.
            return;
        }
        this.playItem(this.shownItems.at(nextIdx));
    }
});
var app = new AppView();

// App setup.
Backbone.history.start({pushState: false});

// Disable selection on UI elements.
$('#entities ul').disableSelection();
$('#header').disableSelection();

// Audio player setup.
$('#player').player();

});
