/* globals _,$,Backbone,Marionette,Howl */
(function () {
    "use strict";

    // Constants
    var SETTINGS = {
        API: "http://127.0.0.1:8337",
        ENABLE_PLAYLISTS: 0
    },
    // Models
        Item = Backbone.Model.extend({
            urlRoot: SETTINGS.API + "/item/",

            getFileUrl: function () {
                return this.urlRoot + this.get("id") + "/file";
            },

            initialize: function () {
                this.prepForDisplay();
            },

            // Format times as minutes and seconds.
            formatTime: function(secs) {
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
            },

            prepForDisplay: function () {
                this.set("time", this.formatTime(this.get("length")));
            }
        }),
        Album = Backbone.Model.extend({
            urlRoot: SETTINGS.API + "/album/",
            model: Item,
            getItems: function () {
                this.url = "/album/" + this.model.get("id") + "?expand=1";
                this.fetch();
            }
        }),
        Artist = Backbone.Model.extend({}),
        Stats = Backbone.Model.extend({
            url: SETTINGS.API + "/stats"
        }),

    // Collections
        Items = Backbone.Collection.extend({
            url: SETTINGS.API + "/item/",
            model: Item,
            parse: function (data) {
                return data.items;
            },
            comparator: 'track'
        }),
        Albums = Backbone.Collection.extend({
            url: SETTINGS.API + "/album/",
            model: Album,
            parse: function (data) {
                return data.albums;
            }
        }),
        Artists = Backbone.Collection.extend({
            url: SETTINGS.API + "/artist/",
            model: Artist,
            comparator: 'name',
            parse: function (data) {
                var r = _.map(data.artist_names, function (n) {
                    return {
                        name: n
                    };
                });
                return r;
            }
        }),
        Queue = Backbone.Collection.extend({
            model: Album
        }),

    // Templates
        JST = {
            "album/view": _.template($("#tpl-album-view").html()),
            "album/listview": _.template($("#tpl-album-list-view").html()),
            "album/detailview": _.template($("#tpl-album-detail-view").html()),
            "app/view": _.template($("#tpl-app-view").html()),
            "artist/view": _.template($("#tpl-artist-view").html()),
            "artist/listview": _.template($("#tpl-artist-list-view").html()),
            "item/view": _.template($("#tpl-item-view").html()),
            "item/detailview": _.template($("#tpl-item-detail-view").html()),
            "item/listview": _.template($("#tpl-item-list-view").html()),
            "nowplaying/view": _.template($("#tpl-nowplaying-view").html()),
            "nowplaying/timingview": _.template($("#tpl-nowplaying-timing-view").html()),
            "queue/listview": _.template($("#tpl-queue-list-view").html()),
            "queue/emptyview": _.template($("#tpl-queue-empty-view").html()),
            "queue/itemview": _.template($("#tpl-queue-item-view").html()),
            "savedplaylist/view": _.template($("#tpl-savedplaylist-view").html()),
            "search/view": _.template($("#tpl-search-view").html()),
            "search/itemview": _.template($("#tpl-search-item-view").html()),
            "sidebar/view": _.template($("#tpl-sidebar-view").html()),
            "stats/view": _.template($("#tpl-stats-view").html()),
        },

    // Views
        ItemDetailView = Marionette.View.extend({
            template: JST["item/detailview"],
            templateContext: function () {
                return {
                    time: this.model.formatTime(this.model.get("length")),
                };
            }
        }),
        SavedPlaylistView = Marionette.View.extend({
            template: JST["savedplaylist/view"]
        }),
        SidebarView = Marionette.View.extend({
            template: JST["sidebar/view"],
            className: "sidebar-sticky",
            events: {
                "click .nav-link.search-link": function () {
                    this.$(".nav-link.active").removeClass("active");
                    this.$(".nav-link.search-link").addClass("active");
                },
                "click .nav-link.queue-link": function () {
                    this.$(".nav-link.active").removeClass("active");
                    this.$(".nav-link.queue-link").addClass("active");
                },
                "click .nav-link.albums-link": function () {
                    this.$(".nav-link.active").removeClass("active");
                    this.$(".nav-link.albums-link").addClass("active");
                },
                "click .nav-link.stats-link": function () {
                    this.$(".nav-link.active").removeClass("active");
                    this.$(".nav-link.stats-link").addClass("active");
                },
                "click .nav-link.artists-link": function () {
                    this.$(".nav-link.active").removeClass("active");
                    this.$(".nav-link.artists-link").addClass("active");
                },
            },
            regions: {
                "savedplaylists": "#savedplaylists"
            },
            initialize: function () {
                this.listenTo(App.queue, "update", this.render);
            },
            onRender: function () {
                if (SETTINGS.ENANLE_PLAYLISTS) {
                    this.showChildView("savedplaylists", new SavedPlaylistView());
                }
            },
            templateContext: function () {
                return {
                    queue_size: App.queue.size()
                };
            },
        }),
        QueueEmptyView = Marionette.View.extend({
            template: JST["queue/emptyview"]
        }),
        QueueChildView = Marionette.View.extend({
            tagName: "li",
            template: JST["queue/itemview"],
            events: {
                "click .play-button": function () {
                    App.playTrack(this.model);
                },
                "click .info-button": function () {
                    App.router.navigate("track/" + this.model.get("id"), {
                        trigger: true
                    });
                },
            },

        }),
        QueueView = Marionette.CollectionView.extend({
            template: JST["queue/listview"],
            childViewContainer: ".js-widgets",
            emptyView: QueueEmptyView,
            childView: QueueChildView,
            events: {
                "click .play-icon": function () {
                    App.playNext();
                }
            }
        }),
        SearchResultView = Marionette.View.extend({
            template: JST["search/itemview"],
            className: "list-group-item",
            events: {
                "click .play-button": function () {
                    App.playTrack(this.model);
                },
                "click .add-button": function () {
                    App.queue.push(this.model);
                },
                "click .info-button": function () {
                    App.router.navigate("track/" + this.model.get("id"), {
                        trigger: true
                    });
                },
            },
        }),
        SearchView = Marionette.CollectionView.extend({
            template: JST["search/view"],
            tagName: "ul",
            className: "list-group",
            collection: new Items(),
            childView: SearchResultView,
            events: {
                "blur #query": "doSearch",
                "click .search-icon": "doSearch",
                "click button": "doSearch",
                "submit form": "doSearch"
            },
            ui: {
                "q": "#query"
            },
            doSearch: function () {
                var $inputField = this.getUI("q");
                var query = $inputField.val();
                var queryURL = query.split(/\s+/).map(encodeURIComponent).join("/");
                var url = SETTINGS.API + "/item/query/" + queryURL;
                var self = this;

                $.getJSON(url, function (data) {
                    self.collection.set(data.results);
                });
            },
        }),
        AlbumListChildView = Marionette.View.extend({
            tagName: "li",
            className: "list-group-item",
            template: JST["album/view"],
            events: {
                "click .add-button": "doQueue"
            },
            doQueue: function () {
                this.model.url = "/album/" + this.model.get("id") + "?expand=1";
                this.model.fetch({
                    success: function (data) {
                        var items = data.attributes.items;
                        _.each(items, function (item) {
                            var i = new Item( item );
                            App.queue.push(i);
                        });
                    }
                });
            }
        }),
        AlbumListView = Marionette.CollectionView.extend({
            template: JST["album/listview"],
            childViewContainer: ".js-widgets",
            childView: AlbumListChildView,
        }),
        StatsView = Marionette.View.extend({
            template: JST["stats/view"]
        }),
        TimingView = Marionette.View.extend({
            template: JST["nowplaying/timingview"],
            tagName: 'span',
            className: 'typewriter time-area',
            currentTime: "0:00",
            initialize: function () {
                var self = this;
                var timer = function () {
                    var p = App.sound.seek();
                    self.currentTime = self.model.formatTime(p);
                    self.render();
                };

                this.currentTimeTracker = setInterval(
                    function () {
                        timer();
                    },
                    1000
                );
            },
            templateContext: function () {
                return {
                    currentTime: this.currentTime,
                };
            },
        }),
        NowPlayingView = Marionette.View.extend({
            template: JST["nowplaying/view"],
            regions: {
                timeRegion: {
                    el: '.time-area',
                    replaceElement: true
                }
            },
            events: {
                "click .stop-icon": function () {
                    App.sound.stop();
                    this.$('button').removeClass('active');
                    this.$('button.stop-icon').addClass('active');
                },
                "click .pause-icon": function () {
                    App.sound.pause();
                    this.$('button').removeClass('active');
                    this.$('button.pause-icon').addClass('active');

                },
                "click .play-icon": function () {
                    App.sound.play();
                    this.$('button').removeClass('active');
                    this.$('button.play-icon').addClass('active');

                },
                "click .forward-icon": function () {
                    App.playNext();
                },
                "click .info-icon": function () {
                    App.router.navigate("track/" + this.model.get("id"), {
                        trigger: true
                    });
                }
            },

            onRender: function () {
                this.showChildView("timeRegion", new TimingView({
                    model: this.model
                }));
            }
        }),
        TrackListChildView = Marionette.View.extend({
            tagName: "li",
            className: "list-group-item",
            template: JST["item/view"],
            events: {
                "click .play-button": function () {
                    App.playTrack(this.model);
                },
                "click .add-button": function () {
                    App.queue.push(this.model);
                },
                "click .info-button": function () {
                    App.router.navigate("track/" + this.model.get("id"), {
                        trigger: true
                    });
                },
            }
        }),
        TrackListView = Marionette.CollectionView.extend({
            template: JST["item/listview"],
            childViewContainer: ".js-widgets",
            childView: TrackListChildView
        }),
        AlbumDetailView = Marionette.View.extend({
            template: JST["album/detailview"],
            regions: {
                "tracksRegion": "#tracks-region"
            },
            onRender: function () {
                var tracks = new Items();
                tracks.add(this.model.get("items"));
                this.showChildView("tracksRegion", new TrackListView({
                    collection: tracks
                }));
            },

        }),
        ArtistListChildView = Marionette.View.extend({
            tagName: "li",
            className: "list-group-item",
            template: JST["artist/view"]
        }),
        ArtistListView = Marionette.CollectionView.extend({
            template: JST["artist/listview"],
            childViewContainer: ".js-widgets",
            childView: ArtistListChildView
        }),
        AppView = Marionette.View.extend({
            template: JST["app/view"],
            className: "container-fluid m0 p0",
            regions: {
                "sidebar": "#sidebar",
                "nowPlaying": "#nowPlaying",
                "mainview": "#main"
            },
            initialize: function () {
                this.listenTo(Backbone, "show:queue", this.showQueueView);
                this.listenTo(Backbone, "show:search", this.showSearchView);
                this.listenTo(Backbone, "show:albums", this.showAlbumListView);
                this.listenTo(Backbone, "show:stats", this.showStatsView);
                this.listenTo(Backbone, "show:track", this.showTrackView);
                this.listenTo(Backbone, "show:album", this.showAlbumDetailView);
                this.listenTo(Backbone, "player:play", this.showNowPlayingView);
                this.listenTo(Backbone, "show:artists", this.showArtistListView);
            },
            onRender: function () {
                this.showChildView("sidebar", new SidebarView());
            },
            showQueueView: function () {
                this.showChildView("mainview", new QueueView({
                    collection: App.queue
                }));
            },
            showSearchView: function () {
                this.showChildView("mainview", new SearchView());
            },
            showAlbumListView: function () {
                var self = this;
                App.albums.fetch({
                    success: function () {
                        self.showChildView("mainview", new AlbumListView({
                            collection: App.albums
                        }));
                    }
                });
            },
            showStatsView: function () {
                var self = this;
                App.stats.fetch({
                    success: function () {
                        self.showChildView("mainview", new StatsView({
                            model: App.stats
                        }));
                    },
                });
            },
            showNowPlayingView: function (model) {
                this.showChildView("nowPlaying", new NowPlayingView({
                    model: model
                }));
            },
            showTrackView: function (id) {
                var item = new Item({
                    id: id
                });
                var self = this;
                item.fetch({
                    success: function () {
                        self.showChildView("mainview", new ItemDetailView({
                            model: item
                        }));
                    }
                });
            },
            showAlbumDetailView: function (id) {
                var album = new Album({
                    id: id
                });
                album.url = "/album/" + id + "?expand=1";
                var self = this;
                album.fetch({
                    success: function () {
                        self.showChildView("mainview", new AlbumDetailView({
                            model: album
                        }));
                    }
                });
            },
            showArtistListView: function () {
                var self = this;
                App.artists.fetch({
                    success: function () {
                        self.showChildView("mainview", new ArtistListView({
                            collection: App.artists
                        }));
                    }
                });
            }
        }),
    // Routers
        Router = Backbone.Router.extend({
            routes: {
                "": "default",
                "queue": "doQueue",
                "search": "doSearch",
                "albums": "doAlbums",
                "album/:id": "doAlbum",
                "track/:id": "doTrack",
                "stats": "doStats",
                "artists": "doArtists",
            },
            default: function () {
                this.navigate("search", {
                    trigger: true
                });
            },
            doQueue: function () {
                Backbone.trigger("show:queue");
            },
            doSearch: function () {
                Backbone.trigger("show:search");
            },
            doAlbums: function () {
                Backbone.trigger("show:albums");
            },
            doStats: function () {
                Backbone.trigger("show:stats");
            },
            doTrack: function (id) {
                Backbone.trigger("show:track", id);
            },
            doAlbum: function (id) {
                Backbone.trigger("show:album", id);
            },
            doArtists: function () {
                Backbone.trigger("show:artists");
            },
        }),
    // App Container
        App = {
            // Other Objects
            sound: new Howl({
                src: [""],
                format: ["mp3"]
            }),

            queue: new Queue(),

            albums: new Albums(),

            stats: new Stats(),

            artists: new Artists(),

            appView: new AppView({
                el: "#app"
            }),

            router: new Router(),

            start: function () {
                this.appView.render();
                Backbone.history.start();
            },

            playTrack: function (model) {
                if (model) {
                    this.sound.stop();
                    this.sound = new Howl({
                        src: [model.getFileUrl()],
                        format: [model.get("format").toLowerCase()],
                    });

                    Backbone.trigger("player:play", model);

                    this.sound.play();
                    this.sound.on("end", function () {
                        App.playTrack(App.queue.shift());
                    });
                }
            },
            playNext: function () {
                this.playTrack(this.queue.shift());
            }
        };

    $(function () {
        App.start();
    });

}());
