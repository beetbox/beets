# This file is a plugin on beets.
#Copyright (c) <2013> Verrus, <github.com/Verrus/beets-plugin-featInTitle>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""puts featuring artists in the title instead of the artist field"""

from beets.plugins import BeetsPlugin
from beets import library
from beets import ui
import locale
import re
import sys
reload(sys)
sys.setdefaultencoding("utf-8") # fixes encoding issues using a pipe




class ftInTitle(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('ftintitle', help='puts featuring artists in the title instead of the artist field')
        def func(lib, opts, args):
        
            def find_supplementary_artists(artistfield):
                return re.split('[fF]t\.|[fF]eaturing|[fF]eat\.|\b[wW]ith\b|&|vs\.|and', artistfield,1) #only split on the first.
            def detect_If_featuring_artist_already_In_title(titleField):
                return re.split('[fF]t\.|[fF]eaturing|[fF]eat\.|\b[wW]ith\b|&', titleField)
            # feat is already in title only replace artistfield
            def write_artist_field_only_and_print_edited_file_loc(track,albumArtist,sortArtist):
                print track.__getattr__("path")
                print "new artist field",albumArtist.strip()
                track["artist"] = albumArtist
                track["artist_sort"] = rewrite_sort_artist(sortArtist)
                track.write()
            # write a new title and a new artistfield.
            def write_artist_and_title_field_and_print_edited_file_loc(track,albumArtist,titleField,featuringPartofArtistField,sortArtist):
                print track.__getattr__("path")
                print "albumartist:",albumArtist," title:",titleField," featuartist:",featuringPartofArtistField
                track["artist"] = albumArtist
                track["artist_sort"] = rewrite_sort_artist(sortArtist)
                track["title"] = titleField.strip() + " feat." + featuringPartofArtistField
                track.write()
            # split the extended artistfield in the extended part and albumartist
            def split_on_album_artist(albumArtist,artistfield):
                return re.split(albumArtist, artistfield)
            #checks if title has a feat artist and calls the writing methods accordingly
            def choose_writing_of_title_and_write(track,albumArtist,titleField,featuringPartofArtistField,sortArtist):
                if len(detect_If_featuring_artist_already_In_title(titleField))>1: #if already in title only replace the artist field.
                    #no replace title
                    write_artist_field_only_and_print_edited_file_loc(track,albumArtist,sortArtist)
                else:
                    #do replace title.
                    write_artist_and_title_field_and_print_edited_file_loc(track,albumArtist,titleField,featuringPartofArtistField,sortArtist)
            # filter the sort artist with a regex split. and strip.
            def rewrite_sort_artist(sortArtist):
                return find_supplementary_artists(sortArtist)[0].strip()
            for track in lib.items():
                artistfield  = track.__getattr__("artist").strip()
                titleField = track.__getattr__("title").strip()
                albumArtist = track.__getattr__("albumartist").strip()
                sortArtist = track.__getattr__("artist_sort").strip()
                suppArtistsSplit = find_supplementary_artists(artistfield)
                
                if len(suppArtistsSplit)>1 and albumArtist!=artistfield: # found supplementary artist. and the albumArtist is not a perfect match.
        
                    albumArtistSplit = split_on_album_artist(albumArtist,artistfield) 
                    if len(albumArtistSplit)>1 and albumArtistSplit[-1]!='': # check if the artist field is composed of the albumartist.  AND check if the last element of the split is not empty.
                        featuringPartofArtistField = find_supplementary_artists(albumArtistSplit[-1])[-1] #last elements
                        choose_writing_of_title_and_write(track,albumArtist,titleField,featuringPartofArtistField,sortArtist)
                            
                    elif len(albumArtistSplit)>1 and len(find_supplementary_artists(albumArtistSplit[0]))>1: #check for inversion of artist and featuring ; if feat is listed on the first split.
                        featuringPartofArtistField = find_supplementary_artists(albumArtistSplit[0])[0] #first elements because of inversion
                        choose_writing_of_title_and_write(track,albumArtist,titleField,featuringPartofArtistField,sortArtist)
                                    
                    else:
                        print "#############################"
                        print "ftInTitle has not touched this track, unsure what to do with this one.:"
                        print "artistfield: ",artistfield
                        print "albumArtist",albumArtist
                        print "titleField: ",titleField
                        print track.__getattr__("path")
                        print "#############################"

            print "A Manual 'beet update' run is recommended. "
        cmd.func = func
        return [cmd]
    
