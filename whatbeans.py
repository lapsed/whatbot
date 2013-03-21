import re
from whatbase import WhatBase

class Collage:
	def __init__(self):
		self.albums = []
		
	def __str__(self):
		return str(self.id) + ": " + self.name + " - " + str(len(self.albums)) + " recordings"
		
class Request:
	def __init__(self):
		self.request_id = 0
		self.in_db = False
		self.torrent_group_id = None
		self.flac_present = None

	def __str__(self):
		return "Request ID " + self.request_id + ": " + self.artist_names[0] + " - " + self.request_name
		
# Hierarchy of beans for music Album -> Edition -> Format
# TODO: Album is something of a misnomer, refactor 
class Album(WhatBase):
	def __str__(self):
		return self.artist + " [" + self.type + "]" + " - " + self.title + " - " + self.year + " - " + \
			self.torrent + " - " + str(len(self.editions)) + " editions - " + str(self.formatCount()) + " formats"

	# Gets the best format using compound scoring algorithm
	def bestFormat(self, config):
		# edition ranking is a three way compound key on the original flag, bytes and seeds and the order of the compound key is user 
		# configurable.  so we iterate over the three configurable items in the list in the configured order and conditionally 
		# produce a list of rankings of each type, which we then stitch together into a list of tuples that corresponds with the 
		# list of formats as presented by the site and sort.  we then update all the editions with their cross-edition ranking for
		# use as a configurable tie breaker.  yeah.  easy.  users will love it ><
		ranks = []
		for rulename in [ rule[1] for rule in sorted(config.items('edition'), key=lambda x:x[0]) ]:
			if rulename == "Original":
				ranks.append([format.edition.originalscore() for format in self.formats])
			elif rulename == "Seeds":
				ranks.append([ 0 - int(format.seeds) for format in self.formats])
			elif rulename == "Bytes":
				ranks.append([ 0 - int(format.bytes()) for format in self.formats])
				
		# If we get here and we don't have three lists it goes bang, it is misconfigured - last item is the index
		compoundRank = sorted(zip(ranks[0], ranks[1], ranks[2], range(len(ranks[0]))), key=lambda x:(x[0], x[1], x[2]))

		# We now have a meaningful edition rank to use as a tie breaker, store it on each format bean so we can sort them
		for i in range(len(compoundRank)):
			self.formats[compoundRank[i][3]].editionRank = i
		
		return sorted(self.formats, key=lambda x:x.rank(config))[0]

	# Download album art
	def downloadAlbumArt(self, folder, messagecallback = None):
		self.debugMessage("Downloading %s to folder %s" % (self.art, folder), messagecallback)
		fname = "folder." + self.art.split('.').pop()
		self.downloadResource(self.art, folder, fname, messagecallback)
		return folder + "/" + fname
	
	def formatCount(self):
		return sum([ len(ed.formats) for ed in self.editions ])
		
class Edition(WhatBase):
	def __init__(self):
		self.original = True
		self.medium = ""
		self.year = ""
		self.title = ""
		self.label = ""
		self.catalog = ""

	def strOriginal(self):
		return self.original and "Original Release" or "Alternate Release"

	def originalscore(self):
		return int(self.original and "0" or "1")
		
	# Several of the data fields for an Edition are optional
	def __str__(self):
		return self.strOriginal() + " - " + self.medium + " - " + self.year + " - " + self.nvl(self.title, "No Title") + " - " + \
			self.nvl(self.label, "No label") + " - " + self.nvl(self.catalog, "No Catalog Number")
		
class Format(WhatBase):
	def __str__(self):
		return self.format + " - " + self.bitrate + " - "  + \
			self.edition.strOriginal() + " - " + self.edition.medium + " - " + self.seeds + " - " + self.size

	def encodingRank(self, config):
		# Cannot match encoding and bitrate yields a large value for rank, always prioritise user preferences for types of file
		# User can change this in configuration
		rank = int(config.get('ranking_rules', 'no_match_rank'))

		for rule in sorted(config.getRankingRules(), key=lambda x:x[2]):
			if (self.format == rule[0] or rule[0] == "") and (self.bitrate == rule[1] or rule[1] == ""):
				rank = int(rule[2])
				break

		return rank
		
	def mediumRank(self, config):
		# Cannot match medium is the same large disadvantage as cannot match encoding/bitrate
		# If the wildcard is specified it is always last and matches everything
		rank = int(config.get('ranking_rules', 'no_match_rank'))
		
		for rule in sorted(config.items("medium"), key=lambda x:(x[0])):
			if (self.edition.medium == rule[1]) or rule[1] == "*":
				rank = int(rule[0])
				break
		
		return rank
		
	def rank(self, config):
		# Scores are assinged from config based on user preferences for encoding & bitrate, medium and edition type
		# editionRank has already been calculated at this point, it is effectively a tie breaker calculated by ordering the formats by properties of their edition
		return self.encodingRank(config) + self.mediumRank(config) + self.editionRank
				
	def isscene(self):
		return self.scene and "Scene" or "User"

	def isfree(self):
		return self.freeleech and "Free" or "Not free"
		
	def bytes(self):
		return self.bytesFromString(self.size)

	def downloadTorrent(self, album):
		fname = album.artist + " - " + album.title + " - " + album.year + " (" + self.edition.medium + " - " + \
			self.format + " - " + re.sub('/.*$', '', self.bitrate) + ").torrent"

		furl = "http://" + self._sitename + "/" + self.url
		self.downloadResource(furl, ".", fname)

			
if __name__ == "__main__":
	print "Bean classes to contain what.cd data"
		