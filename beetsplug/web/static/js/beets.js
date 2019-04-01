// vim expandtab ts=4 sw=4 ai
/* global $ _ Backbone Sortable */

$(document).ready(function(){

  function formatTime (secs) {
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
  }

  var App = {
    api: "/",
    audio: initAudio(),
    init: function(){
      this.appView = new AppView({ el: '#app', audio: this.audio });
    },
    start: function(){
      new Router({audio: this.audio});
      Backbone.history.start();
    }
  };

  // https://ianstormtaylor.com/rendering-views-in-backbonejs-isnt-always-simple/
  var BaseView = Backbone.View.extend({
    // Use only for child views
    assign : function (view, selector) {
      if (view) {
        view.setElement(this.$(selector)).render();
      }
    }
  });

  var AppView = BaseView.extend({
    show: function(childView) {
      this.$el.empty();
      this.$el.append(childView.el);
    }
  });

  var Item = Backbone.Model.extend({
    defaults: {
      artist: 'Artist',
      title: 'Track Title',
      time: 0,
      playing: false,
      selected: false,
      album_details: {}
    },

    getFileUrl: function(){
      return App.api + 'item/' + this.get('id') + '/file';
    },

    prepForDisplay: function(){
      this.set('time', formatTime(this.get('length')));
    },
  });

  var Album = Backbone.Model.extend({
    urlRoot: App.api + 'album/'
  });

  var Albums = Backbone.Collection.extend({
    model: Album,
    url: App.api + 'album/',
    initialize: function(){
      this.fetch();
    },
    parse: function(data) {
      return data.albums;
    },
  });

  var Items = Backbone.Collection.extend({
    model: Item,
    initialize: function(){
      this.listenTo(Backbone, 'items:search', this.query);
    },
    query: function(query) {
      var queryURL = query.split(/\s+/).map(encodeURIComponent).join('/');
      var url = App.api + 'item/query/' + queryURL;
      var self = this;
      $.getJSON(url, function(data){
        self.set(data.results);
      });
    }
  });

  var ItemView = BaseView.extend({
    events: {
      'click #play-button': 'onPlayButtonClick',
      'click #view-button': 'onClick',
    },
    initialize: function(){
      _.bindAll(this, 'render');
      this.listenTo(this.model, 'change', this.render);
      this.listenTo(Backbone, 'play:item', this.play);
      this.listenTo(Backbone, 'play:stop', this.stop);
      this.listenTo(Backbone, 'play:pause', this.stop); //For now
      this.listenTo(Backbone, 'play:resume', this.resume);
      this.template = _.template( $('#item-template').html() ),
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
        Backbone.trigger('play:clear');
        Backbone.trigger('play:PlayOrResume', this.model);
        this.play();
      }
    },
    play: function(model){
      if(model && model != this.model) {
        return;
      }
      this.model.set('playing', true);
      this.model.set('selected', true);
      this.render();
    },
    stop: function(){
      this.model.set('playing', false);
      this.render();
    },
    resume: function(){
      if (this.model.get('selected')){
        this.play(); //This is probably not right
      }
    },
  });

  var ItemsView = BaseView.extend({
    initialize: function(){
      this.repeat = false;

      this.listenTo(Backbone, 'play:setRepeat', this.setRepeat);
      this.listenTo(Backbone, 'play:clear', this.clearList);
      this.listenTo(Backbone, 'play:first', this.onPlayFirst);
      this.listenTo(Backbone, 'play:next', this.onPlayNext);
      this.listenTo(Backbone, 'items:shuffle', this.shuffle);
      this.listenTo(Backbone, 'collection:reorder', this.reorder);
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

      this.makeListSortable();
      return this;
    },

    makeListSortable: function(){
      this.sortable = new Sortable(this.$el[0], {
        onEnd: function(evt){
          Backbone.trigger('collection:reorder', evt.oldIndex, evt.newIndex);
        }
      });
    },

    onPlayFirst: function(){
      this.clearList();
      var first = this.collection.at(0);
      if (first) {
        Backbone.trigger('play:item', first);
      }
    },

    onPlayNext: function(current) {
      if (this.repeat) {
        Backbone.trigger('play:repeat');
        return;
      }

      this.clearList();
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

    clearList: function(){
      this.collection.each(function(item){
        item.set('playing', false);
        item.set('selected', false);
      });
    },

    shuffle: function(){
      this.collection.reset(this.collection.shuffle(), {silent:true});
      this.render();
    },

    setRepeat: function(){
      this.repeat = !this.repeat;
    },

    reorder: function(oldIndex, newIndex) {
      // reorganise the collection, so that playNext just works
      this.collection.models.splice(newIndex, 0, this.collection.models.splice(oldIndex, 1)[0]);
    }
  });

  var MetaView = BaseView.extend({
    initialize: function(options){
      this.albums = options.albums;
      this.template = _.template( $('#metadata-template').html() );
      this.listenTo(Backbone, 'show:item', this.show);
    },
    render: function(){
      if (this.model) {
        var album = this.albums.get(this.model.get('album_id'));
        var album_json = album.toJSON();

        this.$el.html(this.template(_.extend({
          model: this.model.toJSON(),
          album: album_json
        }, {api: App.api})));
      }
      return this;
    },
    show: function(model){
      this.model = model;
      this.render();
    }
  });

  var LyricsView = BaseView.extend({
    initialize: function(){
      this.template = _.template($('#lyrics-template').html()),
        this.listenTo(Backbone, 'show:item', this.show);
    },
    render: function(){
      if (this.model) {
        this.$el.html(this.template(this.model.toJSON()));
      }
      return this;
    },
    show: function(model){
      this.model = model;
      this.render();
    }
  });

  var SliderView = BaseView.extend({
    events: {
      'input': 'setSlider',
    },

    initialize: function(){
      this.listenTo(Backbone, 'play:  item', this.reset);
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
      Backbone.trigger('play:advance', value.target.valueAsNumber);
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
    initialize: function(){
      this.listenTo(Backbone, 'play:item', this.set);
      this.listenTo(Backbone, 'play:PlayOrResume', this.set);
      this.listenTo(this.model, 'change', this.render);
      this.template = _.template($('#playing-template').html());
    },

    render: function(){
      if (this.model) {
        this.$el.html(this.template(this.model.toJSON()));
      }
    },

    set: function(model){
      this.model = model;
      this.render();
    }

  });


  function initAudio() {
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
        Backbone.trigger('play:item', model);
      }
      else {
        audio.play();
      }
    });

    audio.listenTo(Backbone, 'play:PlayOrPause', function(){
      if (audio.paused){
        Backbone.trigger('play:resume');
      } else {
        Backbone.trigger('play:pause');
      }
    });

    audio.listenTo(Backbone, 'play:advance', function(secs) {
      audio.currentTime = secs;
    });


    audio.addEventListener('timeupdate', function(){
      Backbone.trigger('update:currentTime', audio.currentTime);
    });

    audio.addEventListener('ended', function(){
      Backbone.trigger('play:next', audio.model);
    });

    audio.listenTo(Backbone, 'play:repeat', function(){
      audio.currentTime = 0;
      audio.play();
    });

    return audio;
  }

  var PlayerView = BaseView.extend({
    events: {
      'submit #queryForm': 'onSubmit',
      'click #searchButton': 'onSubmit',
      'click #play-pause-button': 'togglePlay',
      'click #stop-button': 'stopPlay',
      'input #slider': 'setSlider',
      'click #repeat-button': 'repeatButtonClick',
      'click #shuffle-button': 'shuffleButtonClick',
    },

    initialize: function(){
      this.template = _.template( $('#player-template').html() );

      this.itemsView = new ItemsView({ collection: new Items() });
      this.metaView = new MetaView({ albums: new Albums() });
      this.lyricsView = new LyricsView();
      this.sliderView = new SliderView();
      this.currentTimeView = new CurrentTimeView();
      this.totalTimeView = new TotalTimeView();
      this.playingView = new PlayingView();
    },

    onSubmit: function(e){
      e.preventDefault();
      var q = this.$('#query').val().trim();
      Backbone.history.navigate('playlist/item/query/' + q, true);
    },

    togglePlay: function(){
      Backbone.trigger('play:PlayOrPause');
    },

    stopPlay: function(){
      Backbone.trigger('play:stop');
    },

    repeatButtonClick: function(event){
      Backbone.trigger('play:setRepeat');
      $(event.target).toggleClass('active text-success');            
    },

    shuffleButtonClick: function(event){
      Backbone.trigger('items:shuffle');
      $(event.target).toggleClass('active text-success');            
    },

    render: function(){
      this.$el.html(this.template());

      this.assign(this.itemsView,        '#results');
      this.assign(this.metaView,         '#meta');
      this.assign(this.lyricsView,       '#lyrics');
      this.assign(this.sliderView,       '#slider');
      this.assign(this.currentTimeView,  '#currentTime');
      this.assign(this.totalTimeView,    '#totalTime');
      this.assign(this.playingView,      '#playingLabel');
      return this;
    },
  });

  var Router = Backbone.Router.extend({
    initialize: function(options){
      if (options.audio) {
        this.audio = options.audio
      }
    },
    routes: {
      'playlist/item/query/:query': 'doSearch',
      'playlist': 'doPlaylist',
      'stats/:query': 'doStats',
      'about': 'doAbout',
      'library': 'doLibrary',
    },

    doPlaylist: function(){
      App.appView.show( new PlayerView().render() );
    },

    doSearch: function(query){
      App.appView.show( new PlayerView().render() );
      Backbone.trigger('items:search', query);
    },
    doStats: function(query){
      Backbone.trigger('stats:show', query);
    },
    doAbout: function(){
      Backbone.trigger('about:show');
    },
    doLibrary: function(){
      Backbone.trigger('library:show');
    }
  });


  // Rock and Roll

  App.init();
  App.start();
})
