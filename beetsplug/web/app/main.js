const $ = require('jquery');
const _ = require('lodash');
const Bb = require('backbone');
const Mn = require('backbone.marionette');
const AppRouter = require('marionette.approuter');

const api = "/";
const globalAudioObject = new Audio();

// Format times as minutes and seconds.
var timeFormat = function(secs) {
    if (secs == undefined || isNaN(secs)) {
        return '0:00';
    }
    secs = Math.round(secs);
    var mins = '' + Math.floor(secs / 60);
    secs = '' + (secs % 60);
    if (secs.length < 2) {
        secs = '0' + secs;
    }
    return mins + ':' + secs;
};

// Format BitRate
var bitRateFormat = function(bitrate){
    return bitrate/1000;
};

var Item = Bb.Model.extend({
    getFileUrl: function(){
        return api + 'item/' + this.get('id') + '/file';
    }
});

var Items = Bb.Collection.extend({
    model: Item,

    search: function(query) {
        var queryURL = query.split(/\s+/).map(encodeURIComponent).join('/');
        var url = api + 'item/query/' + queryURL;
        var that = this;
        $.getJSON(url, null, function(data){
            that.set(data.results);
        });
    }
});

// Another Global (Oh My God!! :=D )
const items = new Items();

var Router = AppRouter.extend({
    routes: {
        'item/query/:query': 'itemQuery'
    },

    itemQuery: function(query){
        items.search(query);
    }
});
var router = new Router();

var ItemDetailView = Mn.View.extend({
    template: _.template($('#result-detail-template').html()),
    templateContext: function() {
        return {
            time: timeFormat(this.model.get('length')),
            formatedBitrate: bitRateFormat(this.model.get('bitrate')),
        };
    }
});

var ItemLyricsView = Mn.View.extend({
    template: _.template($('#result-lyrics-template').html()),
});

var EmptyView = Mn.View.extend({
    template: _.template('Nothing to display.')
});

var ResultView = Mn.View.extend({
    template: _.template($('#result-item-template').html()),
    ui: {
        play: '#play-button'
    },

    triggers: {
        'click': 'item:selected',
        'dblclick': 'item:play',
        'click @ui.play': 'item:play',
    },
});

var ResultsView = Mn.CollectionView.extend({
    className: 'pre-scrollable list-group',
    childView: ResultView,
    emptyView: EmptyView,

    childViewEvents: {
        'item:selected': 'itemSelected',
        'item:play': 'itemPlay',
    },

    itemSelected: function(view){
        this.selectedItem = view.model;
        view.model.set('selected', true);
        this.trigger('detail:show', view.model);
    },

    itemPlay: function(view){
        this.itemSelected(view);
        this.trigger('player:play', view.model);
    },

    selectNext: function(model, random){
        var nextItem = null;

        if (model){
            var index = this.collection.indexOf(model);
            if(index >= 0 && index < this.collection.length - 1) {
                nextItem = this.collection.at(index + 1);
            }
        }

        if (random) {
            nextItem = this.collection.sample();
        }

        if (nextItem) {
            this.trigger('player:play', nextItem);
        }
    },

});

var NowPlayingView = Mn.View.extend({
    template: _.template($('#now-playing-template').html()),
});

var PlayerView = Mn.View.extend({
    el: '#player',

    modelEvents: {
        'change': 'onModelChange'
    },

    ui: {
        stateButton: '#stateButton',
        loopButton: '#repeatButton',
        randomButton: '#randomButton',
        stateI: '#stateButton i.glyphicon',
        label: '#nowPlaying',
        time: '#currentTime',
        total: '#totalTime',
        slider: '#slider'
    },

    events: {
        'click @ui.stateButton': 'onStateButtonClick',
        'click @ui.loopButton': 'onLoopButtonClick',
        'click @ui.randomButton': 'onRandomButtonClick',

    },

    initialize: function(){
        var audio = this.audio = globalAudioObject;
        this.audio.loop = false;
        this.onModelChange();

        var that = this;

        // some events on the audio chap
        $(this.audio, this).on({
            ended: function(){
                that.sendEndedTrigger();
            },
            timeupdate: function(){
                that.updateTime();
            },
        });
    },

    sendEndedTrigger: function(){
        if (!this.audio.loop){
            this.trigger('audio:ended', this.model, this.random);
        }
    },

    onModelChange: function(){
        if (!this.model) {
            this.getUI('stateButton').prop('disabled', true);
            return;
        }

        this.audio.setAttribute('src', this.model.getFileUrl());
        this.getUI('stateButton').prop('disabled', true);
        this.updateLabel();
        this.setupSlider();
        this.play();
    },

    updateLabel: function(){
        var html = _.template($('#now-playing-template').html())( this.model.toJSON() );
        var t = this.model.get('artist') + ' - ' + this.model.get('title');
        var label = this.getUI('label');
        label.html( html );
        label.addClass('center-block text-center lead bg-info');

        this.getUI('total').text(timeFormat(this.model.get('length')));
    },

    updateTime: function(){
        this.getUI('time').text(timeFormat(this.audio.currentTime));
        this.getUI('slider').attr('value', this.audio.currentTime);
    },

    setupSlider: function(){
        var slider = this.getUI('slider');
        slider.attr('min', 0);
        slider.attr('max', this.model.get('length'));
    },

    play: function(){
        if (! this.playing) {
            this.audio.play();
            this.getUI('stateButton').prop('disabled', false);
            this.getUI('stateI').removeClass('glyphicon-play').addClass('glyphicon-pause');
            this.playing = true;
        }
    },

    pause: function(){
        if (this.playing) {
            this.audio.pause();
            this.getUI('stateI').removeClass('glyphicon-pause').addClass('glyphicon-play');
            this.playing = false;
        }
    },

    onStateButtonClick: function(){
        if (this.playing) {
            this.pause();
        } else {
            if (this.model) {
                this.play();
            } else {
                this.trigger('player:first');
            }
        }
    },

    onLoopButtonClick: function() {
        this.getUI('loopButton').toggleClass('active');
        this.audio.loop = this.getUI('loopButton').hasClass('active');
    },

    onRandomButtonClick: function() {
        this.getUI('randomButton').toggleClass('active');
        this.random = this.getUI('randomButton').hasClass('active');
    }
});

var SearchView = Mn.View.extend({
    el: '#queryForm',

    events: {
        'submit': 'onSubmit'
    },

    ui: {
        query: '#query',
    },

    onSubmit: function(ev){
        ev.preventDefault();
        var value = this.getUI('query').val();
        this.trigger('search:query', value);
    }
});

var RootView = Mn.View.extend({
    el: 'body',

    childViewEvents: {
        'detail:show': 'showDetail',
        'player:play': 'playItem',
        'player:first': 'playFirst',
        'audio:ended': 'selectNext',
        'search:query': 'doSearch',
    },

    regions: {
        search: {
            el: '#queryForm',
            replaceElement: false
        },
        results: {
            el: '#results',
            replaceElement: false,
        },
        details: '#details',
        lyrics: '#lyrics',
        player: '#player',
    },

    ui: {
        'currentTime': '.currentTime'
    },

    initialize: function(){

        this.items = items;

        // show the children here, since they are already rendered
        this.showChildView('search', new SearchView());
        this.showChildView('results', new ResultsView({collection: this.items}));
        this.showChildView('player', new PlayerView());
    },

    showDetail: function(model){
        var x = new ItemDetailView({model: model});
        this.showChildView('details', new ItemDetailView({model: model}));
        this.showChildView('lyrics', new ItemLyricsView({model: model}));
    },

    playItem: function(model) {
        this.showChildView('player', new PlayerView({model: model}));
    },

    playFirst: function(){
        if (this.items.length){
            this.playItem( this.items.at(0) );
        }
    },

    selectNext: function(model, random){
        var v = this.getChildView('results');
        v.selectNext(model, random);
    },

    doSearch: function(searchItem){
        router.navigate('item/query/' + searchItem, true);
    }
});

var App = Mn.Application.extend({
    onBeforeStart: function(){
        this.rootView = new RootView();
    },
    onStart: function(){
        Bb.history.start({pushState: false});
    }
});

var app = new App();
app.start();
