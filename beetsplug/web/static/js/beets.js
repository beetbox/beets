// vim expandtab ts=4 sw=4 ai
$(document).ready(function(){

    var api = "/";

    var formatTime = function(secs) {
        if (secs == undefined || isNaN(secs)) {
            return '0:00';
        }
        secs = Math.round(secs);
        var mins = '' + Math.floor(secs / 60);
        secs = '' + (secs % 60);
        if (secs.length < 2) {
            secs = '0' + secs;
        }
        var t = mins + ':' + secs;
        return t;
    };

    var Item = Backbone.Model.extend({
        defaults: {
            artist: 'Artist',
            title: 'Track Title',
            time: 0,
            playing: false
        },

        getFileUrl: function(){
            return api + 'item/' + this.get('id') + '/file';
        },

        prepForDisplay: function(){
            this.set('time', formatTime(this.get('length')));
        },
    });

    var Items = Backbone.Collection.extend({
        model: Item,
        initialize: function(){
            this.listenTo(Backbone, 'items:search', this.query);
        },
        query: function(query) {
            var queryURL = query.split(/\s+/).map(encodeURIComponent).join('/');
            var url = api + 'item/query/' + queryURL;
            var self = this;
            $.getJSON(url, function(data){
                self.set(data.results);
            });
        }
    });

    // https://ianstormtaylor.com/rendering-views-in-backbonejs-isnt-always-simple/
    var BaseView = Backbone.View.extend({
        assign : function (view, selector) {
            view.setElement(this.$(selector)).render();
        }
    });

    var ItemView = BaseView.extend({
        template: _.template( $('#item-template').html()),
        events: {
            'click #play-button': 'onPlayButtonClick',
            'click': 'onClick',
            'dblclick': 'onPlayButtonClick',
        },
        initialize: function(){
            _.bindAll(this, 'render');
            this.listenTo(this.model, 'change', this.render);
            this.listenTo(Backbone, 'play:stop', this.stop);
            this.render();
        },
        render: function(){
            this.$el.html(this.template(this.model.toJSON()));
            return this;
        },
        onClick: function(ev){
            ev.preventDefault();
            Backbone.trigger('show:item', this.model);
        },
        onPlayButtonClick: function(ev){
            ev.preventDefault();
            if (this.model.get('playing')){
                Backbone.trigger('play:pause');
                this.stop();
            } else {
                Backbone.trigger('play:clear', this.model);
                Backbone.trigger('play:PlayOrResume', this.model);
                this.play();
            }
        },
        stop: function(){
            this.model.set('playing', false);
            this.render();
        }, 
        play: function(){
            this.model.set('playing', true);
            this.render();
        }
    });

    var ItemsView = BaseView.extend({
        initialize: function(){
            this.repeat = false;

            this.listenTo(Backbone, 'play:setRepeat', this.setRepeat);
            this.listenTo(Backbone, 'play:clear', this.clearPlaying);
            this.listenTo(Backbone, 'play:first', this.onPlayFirst);
            this.listenTo(Backbone, 'play:next', this.onPlayNext);
            this.listenTo(Backbone, 'items:shuffle', this.shuffle);
            this.collection.on('reset', this.render, this);
            this.collection.on('update', this.render, this);
        },

        render: function(){
            this.$el.empty();
            var self = this;

            this.collection.each(function(item){
                item.prepForDisplay();
                var itemView = new ItemView({model: item});
                self.$el.append(itemView.el);
            });
            return this;
        },

        onPlayFirst: function(){
            this.clearPlaying();
            var first = this.collection.at(0);
            if (random) {
                first = this.collection.sample();
            }
            if (first) {
                Backbone.trigger('play:item', first);
            }
        },

        onPlayNext: function(current) {
            if (this.repeat) {
                Backbone.trigger('play:repeat');
                return;
            }

            this.clearPlaying();
            var next = null;
            if (current) {
                var n = this.collection.findWhere({id: current.get('id')});
                if (n) {
                    var index = this.collection.indexOf(n);
                    var nextIndex = index + 1;
                    next = this.collection.at(nextIndex);
                }
            }

            if (next) {
                Backbone.trigger('play:item', next);
            }
        },

        clearPlaying: function(){
            this.collection.each(function(item){
                item.set('playing', false);
            });
        },

        shuffle: function(){
            this.collection.reset(this.collection.shuffle(), {silent:true});
            this.render();
        },

        setRepeat: function(){
            this.repeat = !this.repeat;
        }
    });

    var MetaView = BaseView.extend({
        template: _.template( $('#metadata-template').html() ),
        initialize: function(){
            this.listenTo(Backbone, 'show:item', this.show);
        },
        render: function(){
            this.$el.html(this.template(this.model.toJSON()));
            return this;
        },
        show: function(model){
            this.model = model;
            this.render();
        }
    });

    var LyricsView = BaseView.extend({
        template: _.template($('#lyrics-template').html()),
        initialize: function(){
            this.listenTo(Backbone, 'show:item', this.show);
        },
        render: function(){
            this.$el.html(this.template(this.model.toJSON()));
            return this;
        },
        show: function(model){
            this.model = model;
            this.render();
        }
    });

    var PlayPauseButtonView = BaseView.extend({
        events: {
            'click': 'togglePlay'
        },
        togglePlay: function(){
            Backbone.trigger('play:PlayOrPause');
        },
    });

    var StopButtonView = BaseView.extend({
        events: {
            'click': 'stopPlay',
        },
        stopPlay: function(){
            Backbone.trigger('play:stop');
        }
    });

    var SliderView = BaseView.extend({
        events: {
            'input': 'setSlider',
        },

        initialize: function(){
            this.listenTo(Backbone, 'play:item', this.reset);
            this.listenTo(Backbone, 'update:currentTime', this.updateSlider);
        },

        render(){
            this.$el.prop('value', 0); 
            return this;
        },

        updateSlider: function(value){
            this.$el.prop('value', value); 
        },

        setSlider: function(value) {
            Backbone.trigger('play:advance', value.timeStamp);
        },

        reset: function(model) {
            this.$el.prop('value', 0);
            this.$el.prop('max', model.get('length'));
        }
    });

    var CurrentTimeView = BaseView.extend({
        initialize: function(){
            this.listenTo(Backbone, 'update:currentTime', this.updateCurrentTime);
        },

        render() {
            this.$el.html('0:00');
            return this;
        },

        updateCurrentTime: function(value) {
            this.$el.html(formatTime(value));
        }
    });

    var TotalTimeView = BaseView.extend({
        initialize: function(){
            this.listenTo(Backbone, 'play:item', this.updateTotalTime);
        },

        render() {
            this.$el.html('0:00');
            return this;
        },

        updateTotalTime: function(model) {
            this.$el.html(formatTime(model.get('length')));
        }
    });

    var PlayingView = BaseView.extend({
        template: _.template($('#playing-template').html()),

        initialize: function(){
            this.model = new Item();
            this.listenTo(Backbone, 'play:item', this.set);
            this.listenTo(Backbone, 'play:PlayOrResume', this.set);
            this.listenTo(this.model, 'change', this.render);
        },

        render: function(){
            this.$el.html(this.template(this.model.toJSON()));
        },

        set: function(model){
            this.model = model;
            this.render();
        }

    });

    var RepeatButtonView = BaseView.extend({
        events: {
            'click': 'onClick'
        },
        onClick: function(event){
            Backbone.trigger('play:setRepeat');
            $(event.target).toggleClass('active');            
        }
    });

    var ShuffleButtonView = BaseView.extend({
        events: {
            'click': 'onClick'
        },
        onClick: function(){
            Backbone.trigger('items:shuffle');
        }
    });

    var Router = Backbone.Router.extend({
        routes: {
            'item/query/:query': 'doSearch',
        },

        doSearch: function(query){
            Backbone.trigger('items:search', query);
        }
    });

    var initAudio = function(){
        var audio = new Audio();
        _.extend(audio, Backbone.Events);

        audio.listenTo(Backbone, 'play:item', function(model) {
            audio.model = model;
            audio.src = model.getFileUrl();
            audio.play();
        });

        audio.listenTo(Backbone, 'play:pause', function() {
            audio.pause();
        });

        audio.listenTo(Backbone, 'play:resume', function() {
            audio.play();
        });

        audio.listenTo(Backbone, 'play:stop', function() {
            audio.pause();
        });

        audio.listenTo(Backbone, 'play:PlayOrResume', function(model) {
            if (!audio.paused || model != audio.model){
                audio.model = model;
                audio.src = model.getFileUrl();
            }
            audio.play();
        });

        audio.listenTo(Backbone, 'play:PlayOrPause', function(){
            if (audio.paused){
                audio.play();
            } else {
                audio.pause();
            }
        });

        audio.listenTo(Backbone, 'play:advance', function(secs) {
            audio.currentTime = secs;
        });


        audio.addEventListener('timeupdate', function(){
            Backbone.trigger('update:currentTime', audio.currentTime);
        });

        audio.addEventListener('ended', function(){
            Backbone.trigger('play:next', audio.current);
        });

        audio.listenTo(Backbone, 'play:repeat', function(){
            audio.currentTime = 0;
            audio.play();
        });

        return audio;
    };

    var AppView = BaseView.extend({

        events: {
            'submit #queryForm': 'onSubmit',
            'click #searchButton': 'onSubmit',
        },

        initialize: function(options){
            new ItemsView({el: '#results', collection: new Items()});
            new MetaView({el: '#meta'});
            new LyricsView({ el: '#lyrics'});
            // new PlayerView({ el: '#player', audio: options.audio});
            new PlayPauseButtonView({el: '#play-pause-button'});
            new StopButtonView({el: '#stop-button'});
            new SliderView({el: '#slider'});
            new CurrentTimeView({el: '#currentTime'});
            new TotalTimeView({el: '#totalTime'});
            new PlayingView({el: '#playingLabel'});
            new RepeatButtonView({el: '#repeat-button'});
            new ShuffleButtonView({el: '#shuffle-button'});
        },

        onSubmit: function(e){
            e.preventDefault();
            var q = this.$('#query').val().trim();
            Backbone.history.navigate('item/query/' + q, true);
        }

    });


    var audio = initAudio();

    new Router();
    new AppView({ el: 'body', audio: audio });
    Backbone.history.start({pushState: false});
});
