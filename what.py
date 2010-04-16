#!/usr/bin/python
import urllib, urllib2, httplib
import re, traceback, time

from xml.dom import minidom
from xml.parsers.expat import ExpatError

class ResponseBody:
	pass

class WhatBase:
	# Some utility functions and constants that I am very lazily bunging into a base class
	_sitename = "what.cd"
	#_sitename = "foo.bar.site.noexist"

	def downloadResource(self, url, path, fname):
		# Remove characters Windoze doesn't allow in filenames
		fname = re.sub("[\*\"\/\\\[\]\:\;\|\=\,]", "", fname)

		try:
			f = urllib2.urlopen(url)

			if f.getcode() == 200:
				copy = open(path + "/" + fname, 'wb')
				copy.write(f.read())
				copy.close()
			else:
				print "ERROR: Unexpected HTTP response code %d downloading %s" % (f.getcode(), url)

			f.close()
		except (IOError):
			print "ERROR: IO exception downloading resource %s" % url

	def bytesFromString(self, sizestr):
		size = sizestr.split(" ")
		
		if size[1] == "KB":
			return float(size[0]) * 1024
		elif size[1] == "MB":
			return float(size[0]) * 1024 * 1024
		elif size[1] == "GB":
			return float(size[0]) * 1024 * 1024 * 1024
		elif size[1] == "TB":
			return float(size[0]) * 1024 * 1024 * 1024 * 1024
		else:
			return 0
		

class WhatCD(WhatBase):
	_login = "/login.php"

	def __init__(self, config):
		# This singleton class owns the singleton parser
		self.parser = Parser()
		self.config = config
		
		# We are not logged in if there is no cookie here
		self.headers = None
		self.userstats = None
		
	def getUpload(self):
		upload = 0
		if self.userstats:
			upload = self.userstats["stats_seeding"] 
		return upload
		
	def getDownload(self):
		download = 0
		if self.userstats:
			download = self.userstats["stats_leeching"] 
		return download
	
	def getRatio(self):
		ratio = 0.0
		if self.userstats:
			ratio = self.userstats["stats_ratio"]
		return ratio

	def request(self, type, path, data, headers, stripscript = True):
		conn = httplib.HTTPConnection(self._sitename)
		conn.request(type, path, data, headers)
		response = conn.getresponse()
		rb = ResponseBody()
		rb.headers = response.getheaders()

		# Optionally rip all inline JavaScript out of the response in case it hasn't been properly escaped
		if stripscript:
			rb.body = re.sub('<script type="text/javascript">[^<]+</script>', '', response.read())
		else:
			rb.body = response.read()

		conn.close()
		return rb

	def login(self):
		headers = self.request("GET", self._login, "", {}).headers
		cookie=dict(headers)['set-cookie']
		web_session=re.search("web_session=[a-f0-9]+", cookie).group(0)
		headers = { "Cookie": web_session, "Content-Type": "application/x-www-form-urlencoded"}

		loginform= {'username': self.config.get("what", "username"), 'password': self.config.get("what", "password") \
			, 'keeplogged': '1', 'login': 'Login'}
		data = urllib.urlencode(loginform)
		headers = self.request("POST", self._login, data, headers).headers

		try:
			cookie=dict(headers)['set-cookie']
			session=re.search("session=[^;]+", cookie).group(0)
			self.headers = { "Cookie": web_session + "; " + session }
			
			homepage = re.sub('value="Vote">', 'value="Vote"/>', self.request("GET", "/index.php", "", self.headers).body)
			self.userstats = self.parser.getUserStats(minidom.parseString(re.sub("<a href=blog.php>Latest blog posts</a>", "", homepage)))
		except (KeyError, AttributeError):
			# Login failed, most likely bad creds or the site is down, nothing to do
			self.headers = None
			self.userstats = None
		
		return self.headers
		
	def loggedIn(self):
		if headers:
			return True
		else:
			return False
	
	def getCollage(self, collageid):
		return self.request("GET", "/collages.php?id=" + str(collageid), "", self.headers).body
	
	def search(self, searchstr):
		searchform = {'searchstr': searchstr}
		data = urllib.urlencode(searchform)
		return self.request("GET", "/torrents.php?" + data, "", self.headers).body

	def advsearch(self, artist, album):
		searchform = {'action': 'advanced', 'artistname': artist, 'groupname': album, 'tags_type': '1', 'order_by': 'time', 'order_way': 'desc' }
		data = urllib.urlencode(searchform)
		return self.request("GET", "/torrents.php?" + data, "", self.headers).body

	def torrentdetails(self, album):
		return self.request("GET", "/" + album.torrent, "", self.headers).body
	
	def fakeSearch(self, searches, progressbar):
		for i in range(len(searches)):
			progressbar.message("Doing a search for %s: %s" % searches[i])
			time.sleep(1)
			ratio =  float(i + 1) / float(len(searches))
			progressbar.message("Search worked fine, honest")
			progressbar.updateProgress(ratio)
		
		dom = minidom.parse("testdata/mastercuts.html")
		return self.parser.extractAlbumsSearch(dom)
	
	def searchReplacements(self, searches, progressbar):
		foundalbums = []
		
		# Convert from list to set and back again as we are stripping junk and deduplicating
		advsearches = list(set([ ( search[0], re.sub(" *\([^\)]+\) *", "", search[1])) for search in searches ]))
		
		for i in range(len(advsearches)):
			advsearch = advsearches[i]
			progressbar.message("About to search what for %s: %s, sleeping for 10s to be polite..." % advsearch)
			time.sleep(10)
			
			advresponse = self.advsearch(advsearch[0], advsearch[1])
			
			try:
				dom = minidom.parseString(advresponse)
			except (ExpatError):
				progressbar.message("Parse error dealing with response, dumping debug")
				self.parser.handleExpatError("Parse error performing advanced search for %s: %s" % advsearch, advresponse \
					, re.sub(" ", "_", "adv_%s_%s.html" % advsearch))
				continue
				
			albums = self.parser.extractAlbumsSearch(dom)
			if len(albums) > 0:
				progressbar.message("Found %d albums, adding them to match list" % len(albums))
				foundalbums += albums
			else:
				progressbar.message("Nothing found on what.cd")
		
		return foundalbums

class Collage:
	albums = list()
	def __str__(self):
		return str(self.id) + ": " + self.name + " - " + str(len(self.albums)) + " recordings"

class Album(WhatBase):
	def __str__(self):
		return self.artist + " - " + self.title + " - " + self.year + " - " + \
			self.torrent + " - " + str(len(self.formats)) + " formats"

	# Gets the best format using number of seeders as a tie breaker
	def bestFormatSeeded(self, config):
		return sorted(self.formats, key=lambda x:(int(x.rank(config)), 0 - int(x.seeds)))[0]

	# Gets the best format using biggest size as a tie breaker
	def bestFormatSize(self, config):
		return sorted(self.formats, key=lambda x:(int(x.rank(config)), 0 - x.bytes()))[0]

	# Download album art
	def downloadAlbumArt(self, folder):
		print "Downloading %s to folder %s" % (self.art, folder)
		fname = "folder." + self.art.split('.').pop()
		self.downloadResource(self.art, folder, fname)
 
class Format(WhatBase):
	NO_MATCH_RANK = 1000000
	def __init__(self):
		# Default edition to original release as the data does not exist for audiobooks/comedy
		self.edition = "Original Release"

	def __str__(self):
		return self.format + " - " + self.bitrate + " - " + self.source + " - " + \
			self.edition + " - " + self.seeds + " - " + self.size

	def rank(self, config):
		# Matches nothing yields a large value for format rank
		rank = self.NO_MATCH_RANK

		for rule in config.getRankingRules():
			if (self.format == rule[0] or rule[0] == "") and (self.bitrate == rule[1] or rule[1] == ""):
				rank = rule[2]
				break

		return rank
		
	def isscene(self):
		if self.scene:
			return "Scene"
		else:
			return "User"

	def isfree(self):
		if self.freeleech:
			return "Free"
		else:
			return "Not free"

	def bytes(self):
		return self.bytesFromString(self.size)

	def downloadTorrent(self, album):
		fname = album.artist + " - " + album.title + " - " + album.year + " (" + self.source + " - " + \
			self.format + " - " + re.sub('/.*$', '', self.bitrate) + ").torrent"

		furl = "http://" + self._sitename + "/" + self.url
		self.downloadResource(furl, ".", fname)

class Parser(WhatBase):
	_XHTML_NS="http://www.w3.org/1999/xhtml"

	def getText(self, nodelist):
		rc = ""
		for node in nodelist:
			if node.nodeType == node.TEXT_NODE:
				rc = rc + node.data
		return rc

	def parseCollage(self, dom):
		collage = Collage()
		collage.name = self.getText(dom.getElementsByTagNameNS(self._XHTML_NS, 'title')[0].childNodes).split(" :: ")[0]

		for input in dom.getElementsByTagNameNS(self._XHTML_NS, 'input'):
			if input.getAttribute("type") == "hidden" and input.getAttribute("name") == "collageid":
				collage.id = input.getAttribute("value")
				break
		return collage

	def locateAlbumArt(self, dom):
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'div'):
			if node.getAttribute("class") == "box box_albumart":
				return node.getElementsByTagName("img")[0].getAttribute("src")
	
	def extractAlbums(self, dom):
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'table'):
			if node.getAttribute("class") == "torrent_table":
				albums = self.parseTorrentTable(node)
		return albums

	def extractAlbumsSearch(self, dom):
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'table'):
			albums = list()
			if node.getAttribute("id") == "torrent_table":
				albums = self.parseTorrentTableSearch(node)
		return albums

	def parseTorrentTable(self, torrent_table):
		albums = list()
		rows = torrent_table.getElementsByTagName("tr")

		for row in rows:
			if row.getAttribute("class") == "group discog":
				album = self.parseAlbumData(row)
				albums.append(album)

			elif row.getAttribute("class").startswith("group_torrent"):
				format = Format()
				links = row.getElementsByTagName("a")

				if len(links) == 0:
					format.edition = self.getText(row.getElementsByTagName("strong")[0].childNodes)
				if len(links) == 2:
					format.url = links[0].getAttribute("href")
					formatitems = self.getText(links[1].childNodes).split(" / ")

					self.parseFormatItems(format, formatitems)

					cells = row.getElementsByTagName("td")
					format.size = self.getText(cells[1].childNodes)
					format.seeds = self.getText(cells[3].childNodes)

					album.formats.append(format)
		return albums

	def parseFormatItems(self, format, formatitems):
		# Last item in the format string may be blank as freeleech tag gets dropped
		if formatitems[len(formatitems) - 1].strip() == "":
			formatitems.pop()
			format.freeleech = True
		else:
			format.freeleech = False

		# Now the last item in the format string may be a scene tag, deal with it
		if formatitems[len(formatitems) - 1].strip() == "Scene":
			format.scene = True
			formatitems.pop()
		else:
			format.scene = False

		# First item is format, last is source, everything else makes up the "bitrate" field
		format.format = formatitems[0]
		format.source = formatitems[len(formatitems) - 1]
		format.bitrate = "/".join(formatitems[1:len(formatitems)-1])

	def parseAlbumData(self, row):
		album = Album() 
		topnode = row.getElementsByTagName("td")[2]
		album.year = re.search("\[([0-9]{4})\]", topnode.toxml()).group(1)
		# Default to Various Artists as no link will exist for multi-artist torrents
		album.artist = "Various Artists" 
		lnodes = topnode.getElementsByTagName("a") 
		for lnode in lnodes:
			if lnode.getAttribute("href").startswith("artist"):
				album.artist = self.getText(lnode.childNodes)
			elif lnode.getAttribute("href").startswith("torrents.php?id"): 
				album.title = self.getText(lnode.childNodes)
				album.torrent = lnode.getAttribute("href")

		album.formats = list() 
		return album
	
	def parseTorrentTableSearch(self, torrent_table):
		albums = list()
		rows = torrent_table.getElementsByTagName("tr")

		for row in rows:
			if row.getAttribute("class") == "group":
				album = self.parseAlbumData(row)
				albums.append(album)

			elif row.getAttribute("class").startswith("group_torrent"):
				format = Format()

				links = row.getElementsByTagName("a")
				if len(links) == 0:
					format.edition = self.getText(row.getElementsByTagName("strong")[0].childNodes)
				elif len(links) == 3:
					format.url = links[0].getAttribute("href")
					formatitems = self.getText(links[2].childNodes).split(" / ")
					self.parseFormatItems(format, formatitems)

					cells = row.getElementsByTagName("td")
					format.size = self.getText(cells[3].childNodes)
					format.seeds = self.getText(cells[5].childNodes)

					album.formats.append(format)

		return albums

	def handleExpatError(self, description, response, debugfile):
		print description
		traceback.print_exc()
		
		# Dump the search response for debug purposes
		try:
			print "Creating HTML dump for debug in file %s" % debugfile
			dumpfile = open(debugfile, "w")
			dumpfile.write(response)
			dumpfile.close()
		except (IOError):
			print "IO Error creating debug file"
			traceback.print_exc()
			
	def getUserStats(self, dom):
		userStats = {}
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'ul'):
			if node.getAttribute("id") == "userinfo_stats":
				for li in node.getElementsByTagName('li'):
					id = li.getAttribute("id")
					
					# This bit's just great, don't ask me why span tags are nested for the user's ratio
					if id == "stats_ratio":
						val = self.getText(li.getElementsByTagName('span')[1].childNodes)
					else:
						val = self.getText(li.getElementsByTagName('span')[0].childNodes)
						
					# Rebase seed/leech user stats to bytes
					if id in ["stats_seeding", "stats_leeching"]:
						val = self.bytesFromString(val)
					
					userStats[id] = val
					
		return userStats

class DownloadStats:
	def __init__(self):
		self.downloaded = list()
	
	def addTorrent(self, format):
		self.downloaded.append(format)
		
	def printStats(self):
		print "Downloaded a total of %d torrents with the following potential cost" % len(self.downloaded)
		statsmap = {}
		for torrent in self.downloaded:
			key = torrent.format, torrent.isfree()
			if key in statsmap:
				statsmap[key] = ( statsmap[key][0] + torrent.bytes(), statsmap[key][1] + 1 )
			else:
				statsmap[key] = ( torrent.bytes(), 1 )
				
		for k in statsmap.keys():
			print "%d %s %s torrents for a total size of %.1fM" % (statsmap[k][1], k[1], k[0], statsmap[k][0] / 1048576.0)
			
if __name__ == "__main__":
	print "Module to manage what.cd as a web service"
