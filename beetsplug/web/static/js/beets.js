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
            time: 0
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

    var ItemView = Backbone.View.extend({
        template: _.template( $('#item-template').html()),
        events: {
            'click #play-button': 'onPlayButtonClick',
            'click': 'onClick',
            'dblclick': 'onPlayButtonClick',
        },
        initialize: function(){
            _.bindAll(this, 'render');
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
            Backbone.trigger('play:item', this.model);
        }
    });

    var ItemsView = Backbone.View.extend({
        initialize: function(){
            this.listenTo(Backbone, 'play:first', this.onPlayFirst);
            this.listenTo(Backbone, 'play:next', this.onPlayNext);
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

        onPlayFirst: function(random){
            var first = this.collection.at(0);
            if (random) {
                first = this.collection.sample();
            }
            if (first) {
                Backbone.trigger('play:item', first);
            }
        },

        onPlayNext: function(current, random) {
            var next = null;
            if (current) {
                var n = this.collection.findWhere({id: current.get('id')});
                if (n) {
                    var index = this.collection.indexOf(n);
                    var nextIndex = index + 1;
                    next = this.collection.at(nextIndex);
                }
            }

            if (random) {
                next = this.collection.sample();
            }

            if (next) {
                Backbone.trigger('play:item', next);
            }
        }
    });

    var MetaView = Backbone.View.extend({
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

    var LyricsView = Backbone.View.extend({
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

    var PlayerView = BaseView.extend({
        playingTemplate: _.template($('#playing-template').html()),

        events: {
            'click .play-button': 'onPlayButtonClick',
            'click .stop-button': 'onStopButtonClick',
            'click .pause-button': 'onPauseButtonClick',
            'click .repeat-button': 'onRepeatButtonClick',
            'click .random-button': 'onRandomButtonClick',
        },

        initialize: function( options ){
            this.model = new Item();
            this.audio = options.audio;

            this.listenTo(Backbone, 'play:item', this.show);
            this.listenTo(this.model, 'change', this.play);

            this.$playButton = this.$('.play-button');
            this.$pauseButton = this.$('.pause-button');

            this.$label = this.$('#playingLabel');
            this.$slider = this.$('#slider');
            this.$totalTime = this.$('#totalTime');
            this.$currentTime = this.$('#currentTime');
            this.$repeatButton = this.$('.repeat-button');
            this.$randomButton = this.$('.random-button');
            this.repeat = false;
            this.random = false;
            this.bindEvents();
        },

        show: function(model) {
            this.model = model;
            this.audio.src = this.model.getFileUrl();
            this.audio.play();

            // setup the slider
            this.$slider.prop('min', 0);
            this.$slider.prop('max', this.model.get('length'));

            // setup the 'Now Playing' label
            this.$label.html(this.playingTemplate(this.model.toJSON()));
            this.$totalTime.html(formatTime(this.model.get('length')));

            Backbone.trigger('show:item', this.model);
        },

        play: function(model){
            this.audio.play();
        },

        pause: function(model){
            this.audio.pause();
        },

        bindEvents: function(){
            var self = this;

            this.audio.addEventListener('ended', function(){
                if (!this.repeat) {
                    Backbone.trigger('play:next', self.model, self.random);
                } else {
                    this.audio.play();
                }
            });

            this.audio.addEventListener('timeupdate', function(){
                self.updateSlider();
                self.updateCurrentTime();
            });
        },

        onRepeatButtonClick: function(event){
            event.preventDefault();
            $(event.target).toggleClass('active');
            this.audio.loop = !this.audio.loop;
        },

        onRandomButtonClick: function(event){
            event.preventDefault();
            $(event.target).toggleClass('active');
            this.random = !this.random;
        },

        onPlayButtonClick: function(ev) {
            ev.preventDefault();
            if (!this.audio.src) {
                Backbone.trigger('play:first', this.random);
            } else {
                this.play();
            }
        },

        onPauseButtonClick: function(ev) {
            ev.preventDefault();
            this.pause();
        },

        onStopButtonClick: function(ev) {
            ev.preventDefault();
            this.audio.pause();
            this.audio.currentTime = 0;
            this.audio.load();
        },

        updateSlider: function() {
            this.$slider.attr('value', this.audio.currentTime);
        },

        updateCurrentTime: function() {
            this.$currentTime.html(formatTime(this.audio.currentTime));
        },

    });
    var Router = Backbone.Router.extend({
        routes: {
            'item/query/:query': 'doSearch',
        },

        doSearch: function(query){
            Backbone.trigger('items:search', query);
        }
    });

    var AppView = Backbone.View.extend({

        events: {
            'submit #queryForm': 'onSubmit',
            'click #searchButton': 'onSubmit',
        },

        initialize: function(options){
            new ItemsView({el: '#results', collection: new Items()});
            new MetaView({el: '#meta'});
            new LyricsView({ el: '#lyrics'});
            new PlayerView({ el: '#player', audio: options.audio});
        },

        onSubmit: function(e){
            e.preventDefault();
            var q = this.$('#query').val().trim();
            Backbone.history.navigate('item/query/' + q, true);
        }

    });

    new Router();
    new AppView({ el: 'body', audio: new Audio() });
    Backbone.history.start({pushState: false});
});
