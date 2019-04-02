// Define View Manager to manage view states
window.VM = window.VM || {};

// VM.views hold all references to existing views
VM.views = VM.views || {};

// Close existing view
VM.closeView = function(name) {
	if ( typeof VM.views[name] !== 'undefined') {
		// Cleanup view
		// Remove all of the view's delegated events
		VM.views[name].undelegateEvents();
		// Remove view from the DOM
		VM.views[name].remove();
		// Removes all callbacks on view
		VM.views[name].off();

		if ( typeof VM.views[name].close === 'function') {
			VM.views[name].close();
		}
	}
};

// VM.createView always cleans up existing view before
// creating a new one.
// callback function always return a new view instance
VM.createView = function(name, callback) {
	VM.closeView(name);
	VM.views[name] = callback();
	return VM.views[name];
};

// VM.reuseView always returns existing view. Otherwise it
// execute callback function to return new view
// callback function always return a new view instance
VM.reuseView = function(name, callback) {
	if ( typeof VM.views[name] !== 'undefined') {
		return VM.views[name];
	}

	VM.views[name] = callback();
	return VM.views[name];
};