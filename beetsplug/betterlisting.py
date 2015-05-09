# -*- coding: utf-8 -*-

import re
from beets import ui, plugins
from beets.library import Item, Album

# Other fields can be:
#   bitrate, bpm, lyrics,


def _int_arg(s):
    """Convert a string argument to an integer for use in a template
    function.  May raise a ValueError.
    """
    return int(s.strip())


def printed_length(s):
    """Printed length of string after removing ansi escape sequences. This is
    useful in getting the number of characters occupied by the string on
    terminal, for example."""
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return len(ansi_escape.sub('', s))


def is_album(item):
    """Check if the given item represents an album"""
    return isinstance(item, Album)


def is_singleton(item):
    """Check if the given item represents a singleton"""
    return isinstance(item, Item) and not item.album_id


def config_icon(item, view):
    """Get either the unicode special character for the integer specified, or
    the format string from the user configured formatting. This is useful to
    display special unicode characters like :greenbook: in listings."""
    fmt = None
    if view:
        try:
            fmt = ("\\U%08x" % view.get(int)).decode('unicode-escape')
        except:
            fmt = view.get(unicode)
    return format(item, fmt) if fmt else u''


class BetterListingPlugin(plugins.BeetsPlugin):
    """ Provide template functions, and fields for better listing of queries."""

    # Tuples containing the hook, prefix, and a list of all mathcing functions
    # for passing the template functions and fields to beet.
    _prop_names = []

    # Store the prefix used in this class for the given hooks. `all_fields`
    # refers to template fields that can be used by both items and albums.
    _prefixes = {
        'template_funcs': u'tmpl_',
        'template_fields': u'tmpl_field_',
        'album_template_fields': u'album_field_',
        'all_fields': u'field_'
    }

    def __init__(self):
        super(BetterListingPlugin, self).__init__()

        self.config.add({
            'sparks': u'▇▆▅▄▃▂▁ ',
            'track_length': 360,
            'icon_missing_none': u'',
            'icon_missing_some': u'%colorize{◎,red}',
            'icon_lyrics_all':  128215,                 # unicode :green book:
            'icon_lyrics_some': 128217,                 # unicode :orange book:
            'icon_lyrics_none': 128213,                 # unicode :red book:
            'duration_format': '{mins:02d}:{secs:02d}',
            'format_item': "$lyrics_icon %colorize{$duration_bar,blue}",
            'format_album': "$lyrics_icon %colorize{$duration_bar,blue} $missing_icon",
        })

        # Extract tuples containing a list of functions for appropriate beet
        # hooks, and pass them over to that hook.
        for hook, prefix, props in self._prop_names:
            for prop in props:
                key, val = prop[len(prefix):], getattr(self, prop)
                if prefix == self._prefixes["all_fields"]:
                    self.template_fields[key] = val
                    self.album_template_fields[key] = val
                else:
                    getattr(self, hook)[key] = val

    # TEMPLATE FUNCTIONS #####

    @staticmethod
    def tmpl_rpad(s, chars):
        """Right pad a given string with spaces."""
        return s + (u' ' * (_int_arg(chars) - printed_length(s)))

    @staticmethod
    def tmpl_lpad(s, chars, delim=r' '):
        """Left pad a given string with spaces."""
        return (u' ' * (_int_arg(chars) - printed_length(s))) + s

    @staticmethod
    def tmpl_rtrimpad(s, chars):
        """Right pad a given string and/or trim it, if required."""
        if _int_arg(chars) > 0:
            return u'%-*s' % (_int_arg(chars), s[0:_int_arg(chars)])
        else:
            return u''

    @staticmethod
    def tmpl_ltrimpad(s, chars, delim=r' '):
        """Left pad a given string and/or trim it, if required."""
        if _int_arg(chars) > 0:
            return u'%*s' % (_int_arg(chars), s[-_int_arg(chars):])
        else:
            return u''

    @staticmethod
    def tmpl_colorize(message, color=u''):
        """Colorize a given string with the given color"""
        return ui._colorize(color.strip(), message) if color.strip() else message

    def tmpl_sparkbar(self, count, total, color=u''):
        """Produce a spark bar for given count based on a given total. A third
        argument can be provided to colorize the spark bar."""
        count = float(str(count).strip()) if count else 0
        total = float(str(total).strip()) if total else 0

        sparks = self.config["sparks"].get(unicode)[::-1]
        spark = sparks[0] if len(sparks) > 0 else u''

        if len(sparks) > 0:
            if count > 0 and total > 0:
                index = int(count/total*len(sparks))
                spark = sparks[index] if index < len(sparks) else sparks[-1]
            elif total == 0:
                spark = sparks[-1]

        return ui._colorize(color, spark) if color else spark

    # TEMPLATE FIELDS ########

    def field_icons(self, item):
        fmt = self.config['format_album' if is_album(item) else 'format_item']
        return format(item, fmt.get(unicode))

    def field_duration(self, item):
        mins, secs = divmod(self.field_duration_sort(item), 60)
        fmt = self.config['duration_format'].get(unicode)
        return fmt.format(mins=mins, secs=secs)

    def field_duration_sort(self, item):
        duration = 0
        if is_album(item):
            duration = sum([x.length for x in item.items()])
        elif hasattr(item, 'length') and item.length:
            duration = item.length
        return int(duration)

    def field_duration_bar(self, item):
        duration = 0
        total = self.config['track_length'].get(int)
        if is_album(item):
            duration = self.album_field_avg_duration_sort(item)
        else:
            duration = self.field_duration_sort(item)
        return self.tmpl_sparkbar(duration, total)

    def field_lyrics_sort(self, item):
        lyrics = 0
        if is_album(item):
            lyrics = sum(1 if x.lyrics else 0 for x in item.items())
            lyrics = lyrics/float(len(item.items()))
        else:
            lyrics = 1 if hasattr(item, u'lyrics') and item.lyrics else 0
        return lyrics

    def field_lyrics_icon(self, item):
        lyrics = self.field_lyrics_sort(item)
        icon   = self.config['icon_lyrics_some']
        if lyrics == 1:
            icon = self.config["icon_lyrics_all"]
        elif lyrics == 0:
            icon = self.config["icon_lyrics_none"]
        return config_icon(item, icon)

    # ALBUM TEMPLATE FIELDS ########

    def album_field_avg_duration(self, item):
        mins, secs = divmod(self.album_field_avg_duration_sort(item), 60)
        fmt = self.config['duration_format'].get(unicode)
        return fmt.format(mins=mins, secs=secs)

    def album_field_avg_duration_sort(self, item):
        return int(sum([x.length for x in item.items()])/len(item.items()))

    def album_field_missing(self, item):
        return (item.albumtotal or 0) - len(item.items())

    def album_field_missing_icon(self, item):
        missing = self.config['icon_missing_some']
        none_missing = self.config['icon_missing_none']
        icon = missing if self.album_field_missing(item) > 0 else none_missing
        return config_icon(item, icon)

    def album_field_missing_bar(self, item):
        return self.tmpl_sparkbar(self.album_field_missing(item),
                                            self.album_field_total(item))

    def album_field_available(self, item):
        return len(item.items())

    def album_field_available_bar(self, item):
        return self.tmpl_sparkbar(self.album_field_available(item),
                                            self.album_field_total(item))

    def album_field_total(self, item):
        return (item.albumtotal or 0)

for prefix, name in BetterListingPlugin._prefixes.iteritems():
    matching_props = [s for s in dir(BetterListingPlugin) if s.startswith(name)]
    BetterListingPlugin._prop_names.append((prefix, name, matching_props))

