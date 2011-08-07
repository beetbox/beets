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
    },
    render: function() {
        $(this.el).html(this.template(this.model.toJSON()));
        return this;
    },
    select: function() {
        app.selectItem(this);
    }
});
var ItemDetailView = Backbone.View.extend({
    tagName: "div",
    template: _.template($('#item-detail-template').html()),
    render: function() {
        $(this.el).html(this.template(this.model.toJSON()));
        return this;
    }
});

// Main app view.
var AppView = Backbone.View.extend({
    el: $('body'),
    events: {
        'submit #queryForm': 'querySubmit'
    },
    querySubmit: function(ev) {
        ev.preventDefault();
        router.navigate('item/query/' + escape($('#query').val()), true);
    },
    initialize: function() {
        this.delegateEvents();
    },
    showItems: function(items) {
        $('#results').empty();
        console.log(items);
        items.each(function(item) {
            var view = new ItemEntryView({model: item});
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
    }
});
var app = new AppView();

// App setup.
Backbone.history.start({pushState: false});

// Disable selection on UI elements.
$('#entities ul').disableSelection();
$('#header').disableSelection();

});
