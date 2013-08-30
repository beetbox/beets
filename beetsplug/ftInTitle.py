#Copyright (c) <2013> Verrus, <github.com/Verrus/beets-plugin-featInTitle>
#All rights reserved.
## New BSD License:
#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met:
    #* Redistributions of source code must retain the above copyright
      #notice, this list of conditions and the following disclaimer.
    #* Redistributions in binary form must reproduce the above copyright
      #notice, this list of conditions and the following disclaimer in the
      #documentation and/or other materials provided with the distribution.
    #* Neither the name of the <organization> nor the
      #names of its contributors may be used to endorse or promote products
      #derived from this software without specific prior written permission.

#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This file is a plugin on beets.

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
		
			def findSupplementaryArtists(artistfield):
				return re.split('[fF]t\.|[fF]eaturing|[fF]eat\.|[wW]ith|&|vs\.|and', artistfield,1) #only split on the first.
			def DetectIfFeaturingArtistAlreadyInTitle(titleField):
				return re.split('[fF]t\.|[fF]eaturing|[fF]eat\.|[wW]ith|&', titleField)
			# feat is already in title only replace artistfield
			def writeArtistFieldOnlyAndPrintEditedFileLoc(track,albumArtist):
				print track.__getattr__("path")
				print "new artist field",albumArtist.strip()
				track.__setattr__("artist", albumArtist)
				track.write()
			# write a new title and a new artistfield.
			def writeArtistAndTitleFieldAndPrintEditedFileLoc(track,albumArtist,titleField,featuringPartofArtistField):
				print track.__getattr__("path")
				print "albumartist:",albumArtist," title:",titleField," featuartist:",featuringPartofArtistField
				track.__setattr__("artist", albumArtist)
				track.__setattr__("title", titleField.strip() + " feat." + featuringPartofArtistField)
				track.write()
			# split the extended artistfield in the extended part and albumartist
			def splitOnAlbumArtist(albumArtist,artistfield):
				return re.split(albumArtist, artistfield)
			#checks if title has a feat artist and calls the writing methods accordingly
			def chooseWritingOfTitleAndWrite(track,albumArtist,titleField,featuringPartofArtistField):
				if len(DetectIfFeaturingArtistAlreadyInTitle(titleField))>1: #if already in title only replace the artist field.
					#no replace title
					writeArtistFieldOnlyAndPrintEditedFileLoc(track,albumArtist)
				else:
					#do replace title.
					writeArtistAndTitleFieldAndPrintEditedFileLoc(track,albumArtist,titleField,featuringPartofArtistField)
			
			for track in lib.items():
				artistfield  = track.__getattr__("artist").strip()
				titleField = track.__getattr__("title").strip()
				albumArtist = track.__getattr__("albumartist").strip()
				suppArtistsSplit = findSupplementaryArtists(artistfield)
				if len(suppArtistsSplit)>1 and albumArtist!=artistfield: # found supplementary artist. and the albumArtist is not a perfect match.
					albumArtistSplit = splitOnAlbumArtist(albumArtist,artistfield) 
					
					if len(albumArtistSplit)>1 and albumArtistSplit[-1]!='': # check if the artist field is composed of the albumartist.  AND check if the last element of the split is not empty.
						featuringPartofArtistField = findSupplementaryArtists(albumArtistSplit[-1])[-1] #last elements
						chooseWritingOfTitleAndWrite(track,albumArtist,titleField,featuringPartofArtistField)
							
					elif len(albumArtistSplit)>1 and len(findSupplementaryArtists(albumArtistSplit[0]))>1: #check for inversion of artist and featuring ; if feat is listed on the first split.
						featuringPartofArtistField = findSupplementaryArtists(albumArtistSplit[0])[0] #first elements because of inversion
						chooseWritingOfTitleAndWrite(track,albumArtist,titleField,featuringPartofArtistField)
									
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
        
