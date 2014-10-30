var safari = Application('com.apple.Safari');
safari.strictPropertyScope = true;
safari.strictCommandScope = true;

for (var i = 0; i < safari.windows.length; ++i) {
  var win = safari.windows[i];
  var tabs = win.tabs;
  if (Object.keys(tabs).length) {
    for (var j = 0; j < win.tabs.length; ++j) {
      var tab = win.tabs[j];
      var url = tab.url();
      if (url.indexOf("file:") == 0) {
        // A local file URL.
        console.log(url);
        tab.url = url;  // Refresh.
      }
    }
  }
}

'done';
