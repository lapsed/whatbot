#!/usr/bin/python
import urllib, urllib2, httplib
import re, traceback, time, socket

from xml.dom import minidom
from xml.parsers.expat import ExpatError

class ResponseBody:
	pass

class WhatBase:
	# Some utility functions and constants that I am very lazily bunging into a base class
	_sitename = "what.cd"
	
	def debugMessage(self, message, messagecallback = None):
		if messagecallback:
			messagecallback(message)
		else:
			print message

	def downloadResource(self, url, path, fname, messagecallback = None):
		# Remove characters Windoze doesn't allow in filenames
		fname = re.sub("[\*\"\/\\\[\]\:\;\|\=\,]", "", fname)

		try:
			# Do an impression of Firefox to prevent 403 from some image hosts
			opener = urllib2.build_opener()
			opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3")]
			response = opener.open(url)
			
			if response.getcode() == 200:
				copy = open(path + "/" + fname, 'wb')
				copy.write(response.read())
				copy.close()
			else:
				self.debugMessage("ERROR: Unexpected HTTP response code %d downloading %s" % (response.getcode(), url), messagecallback)

			response.close()
		except IOError, io:
			self.debugMessage("ERROR: IO exception downloading resource %s" % url, messagecallback)
			self.debugMessage(traceback.format_exc(), messagecallback)

	def bytesFromString(self, sizestr):
		size = sizestr.split(" ")
		mag = str(size[0]).translate(None, ',')
		
		if size[1] == "KB":
			return float(mag) * 1024
		elif size[1] == "MB":
			return float(mag) * 1024 * 1024
		elif size[1] == "GB":
			return float(mag) * 1024 * 1024 * 1024
		elif size[1] == "TB":
			return float(mag) * 1024 * 1024 * 1024 * 1024
		else:
			return 0
		

class WhatCD(WhatBase):
	_login = "/login.php"

	def __init__(self, config, mm):
		# This singleton class owns the singleton parser
		self.parser = Parser()
		self.config = config
		self.mm = mm
		
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
		headers = { "Content-Type": "application/x-www-form-urlencoded"}
		loginform= {'username': self.config.get("what", "username"), 'password': self.config.get("what", "password") \
			, 'keeplogged': '1', 'login': 'Login'}
		data = urllib.urlencode(loginform)
		headers = self.request("POST", self._login, data, headers).headers

		try:
			cookie=dict(headers)['set-cookie']
			session=re.search("session=[^;]+", cookie).group(0)
			self.headers = { "Cookie": session }
			
			homepage = re.sub('value="Vote">', 'value="Vote"/>', self.request("GET", "/index.php", "", self.headers).body)
			homepage = re.sub("forums\.php\?action=viewthread\&threadid=[0-9]+", "dummy.php", homepage)
			homepage = re.sub("user\.php\?action=search\&search=[a-z0-9A-Z]+", "dummy.php", homepage)
			self.userstats = self.parser.getUserStats(minidom.parseString(re.sub("<a href=blog.php>Latest blog posts</a>", "", homepage)))
		except (KeyError, AttributeError):
			# Login failed, most likely bad creds or the site is down, nothing to do
			self.headers = None
			self.userstats = None
		
		return self.headers
		
	def loggedIn(self):
		return self.headers and True or False
	
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

	def snatched(self, progressbar):
		# more bugs on what, this time an unterminated table tag.  Or terminated and not opened if there is nothing found ><
		nodata = re.compile('<div class="center">\s+Nothing found!\s+</div>', re.MULTILINE + re.DOTALL)
		badtable = re.compile('<table class="cat_list">.+?</table>', re.MULTILINE + re.DOTALL)
	
		snatched = []
		page = 1
		while True:
			progressbar.message("Grabbing snatched page %s" % (page,))
			html = self.snatchedPage(page)
			if nodata.search(html):
				break
	
			dom = minidom.parseString(badtable.sub("", html))
			snatched += self.parser.extractAlbumsSnatched(dom)
			progressbar.message("Added %s snatched albums, now sleeping..." % (len(snatched),))
			page += 1
			
			# Sleep for five seconds, it's only polite
			time.sleep(5)
		return snatched
		
	def snatchedPage(self, page):
		return self.request("GET", "/torrents.php?page=%s&type=snatched&userid=%s" % (page, self.userstats["user_id"]), "", self.headers).body

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
					, re.sub(" ", "_", "adv_%s_%s.html" % advsearch), progressbar.message)
				continue
				
			albums = self.parser.extractAlbumsSearch(dom)
			if len(albums) > 0:
				progressbar.message("Found %d albums, adding them to match list" % len(albums))
				foundalbums.extend(albums)
			else:
				progressbar.message("Nothing found on what.cd")
				
			ratio =  float(i + 1) / float(len(advsearches))
			progressbar.updateProgress(ratio)
		
		return foundalbums

	def grabart(self, folder, album, progressbar, imagepreview):
		try:
			htmldetail = self.torrentdetails(album)
			# Throttle HTML request throughput
			time.sleep(5)
		
			detailpage = re.sub(' id="postpreview" ', ' ', htmldetail)
			details = minidom.parseString(detailpage)
			album.art = self.parser.locateAlbumArt(details)
			
			if not album.art.startswith('static/common/noartwork'):
				imagepreview.changeImage(album.downloadAlbumArt(folder, progressbar.message))
			else:
				progressbar.message("what.cd has no artwork for %s: %s, please submit some" % (album.artist, album.title))
		except (ExpatError):
			progressbar.message("Parse error dealing with what's response, dumping debug")
			self.parser.handleExpatError("Parse error grabbing album art for %s: %s" % (album.artist, album.title) \
				, detailpage, re.sub(" ", "_", "art_%s_%s.html" % (album.artist, album.title)), progressbar.message)
		except socket.error:
			progressbar.message("socket error grabbing art, skipping %s: %s" % (album.artist, album.title))

	# strip extraneous junk like CD1, disc 1 and so on out of an album name
	def unmangle(self, album):
		nobrackets = re.compile("\(.+?\)")
		nocd = re.compile("CD\s*[0-9]", re.IGNORECASE)
		nodisc = re.compile("disc\s*[0-9]", re.IGNORECASE)
		trailcrap = re.compile("[^\w]+$")
		
		return trailcrap.sub("", nocd.sub("", nodisc.sub("", nobrackets.sub("", album))))
			
	# Compare user's snatch list to what mediamonkey thinks is missing and snag the art
	def downloadSnatchedArt(self, snatched, progressbar, imagepreview):
		missingalbums = self.mm.missingArt()
		
		for i, missingalbum in enumerate(missingalbums):
			artist, album = missingalbum[0], self.unmangle(missingalbum[1])
			for snatch in filter(lambda x:x.artist.upper() == artist.upper() and x.title.upper() == album.upper(), snatched):
				progressbar.message("Found torrent in snatched for %s - %s" % (artist, album))
				folder = self.mm.fullpath(missingalbum[2])
				progressbar.message("Downloading album art from %s to %s" % (snatch.torrent, folder))
				self.grabart(folder, snatch, progressbar, imagepreview)
			
		ratio =  float(i + 1) / float(len(missingalbums))
		progressbar.updateProgress(ratio)	
	
	# Expecting a list of (artist, album, folder) tuples for local foldernames and refs to GUI progress objects
	def downloadImages(self, tuples, progressbar, imagepreview):
		pos = 0
		for artist, mangledalbum, folder in tuples:
			album = self.unmangle(mangledalbum)
			progressbar.message("Advanced search for %s: %s" % (artist, album))

			try:
				advresponse = self.advsearch(artist, album)
				# Sleep after a search plz
				time.sleep(10)
				dom = minidom.parseString(advresponse)
			except (ExpatError):
				progressbar.message("Parse error dealing with what's response, dumping debug")
				self.parser.handleExpatError("Parse error performing advanced search for %s: %s" % (artist, album) \
					, advresponse, re.sub(" ", "_", "adv_%s_%s.html" % (artist, album)), progressbar.message)
				continue
			except socket.error:
				progressbar.message("socket error performing advanced search, skipping %s: %s" % (artist.album))
				continue
			
			albums = self.parser.extractAlbumsSearch(dom)

			if len(albums) == 1:
				progressbar.message("Found exactly one album, grabbing art")
				self.grabart(folder, albums[0], progressbar, imagepreview)
			elif len(albums) > 1:
				progressbar.message("Ambigous result: found %d albums, skipping" % len(albums))
			else:
				progressbar.message("Nothing found for %s: %s" % (artist, album))
			
			ratio =  float(pos + 1) / float(len(tuples))
			progressbar.updateProgress(ratio)
			pos += 1

	# Expecting a list of (artist, album, folder) tuples for local foldernames and refs to GUI progress objects
	def fakeDownloadImages(self, tuples, progressbar, imagepreview):
		pos = 0
		testimages = ["testdata/1.jpg", "testdata/2.jpg", "testdata/3.jpg", "testdata/4.jpg", "testdata/5.jpg", "testdata/6.jpg"]
		for artist, album, folder in tuples:
			progressbar.message("Fake advanced search for %s - %s" % (artist, album))

			time.sleep(3)
			progressbar.message("Found exactly one album, grabbing art")
			imagepreview.changeImage(testimages[pos % len(testimages)])
			
			ratio =  float(pos + 1) / float(len(tuples))
			progressbar.updateProgress(ratio)		
			pos += 1
			
class Collage:
	albums = []
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
	def downloadAlbumArt(self, folder, messagecallback = None):
		self.debugMessage("Downloading %s to folder %s" % (self.art, folder), messagecallback)
		fname = "folder." + self.art.split('.').pop()
		self.downloadResource(self.art, folder, fname, messagecallback)
		return folder + "/" + fname
 
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
		return self.scene and "Scene" or "User"

	def isfree(self):
		return self.freeleech and "Free" or "Not free"

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
		albums = []
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'table'):
			if node.getAttribute("class") == "torrent_table":
				albums = self.parseTorrentTable(node)
		return albums

	def extractAlbumsSearch(self, dom):
		albums = []
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'table'):
			if node.getAttribute("id") == "torrent_table":
				albums = self.parseTorrentTableSearch(node)
		return albums

	def parseTorrentTable(self, torrent_table):
		albums = []
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
		
	def extractAlbumsSnatched(self, dom):
		albums = []
		for table in dom.getElementsByTagNameNS(self._XHTML_NS, 'table'):
			if table.getAttribute("width") == "100%":
				for row in table.getElementsByTagName("tr")[1:]:
					# we're only dealing with music torrents for the time being...
					classname = row.getElementsByTagName("div")[0].getAttribute("class").split(" ")[0]
					if classname != "cats_music":
						continue
					
					album = Album()
					# default to Various Artists as no link exists for compilations
					album.artist = "Various Artists"

					cells = row.getElementsByTagName("td")
					torrent, sizecell, seedcell = cells[1], cells[3], cells[5]
					
					for i, n in enumerate(torrent.childNodes):
						if n.nodeType == n.TEXT_NODE:
							year = re.search("\[[0-9]{4}\]", n.data)
							if year:
								album.year = year.group(0).strip("[]")
								format = Format()
								format.edition = "Original Edition"
								self.parseFormatItems(format, n.data.split(" - ")[1].strip().split(" / "))
								format.size = sizecell.childNodes[0].data
								format.seeds = seedcell.childNodes[0].data
								album.formats = [format]
								
					for link in torrent.getElementsByTagName("a"):
						url = link.getAttribute("href")
						if re.match("artist.php", url):
							album.artist = link.childNodes[0].data
						elif re.match("torrents.php\?id=[0-9]+&torrentid=[0-9]+$", url):
							album.title = link.childNodes[0].data
							format.url = url
							album.torrent = url.split("&")[0]
					
					try:
						# Skip albums with no year in what's metadata
						dummy = album.year
						albums.append(album)
					except (AttributeError):
						self.debugMessage("Skipping %s - %s, please fix metadata on what" % (album.artist, album.title))
							
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

		album.formats = [] 
		return album
	
	def parseTorrentTableSearch(self, torrent_table):
		albums = []
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

	def handleExpatError(self, description, response, debugfile, messagecallback = None):
		self.debugMessage(description, messagecallback)
		self.debugMessage(traceback.format_exc(), messagecallback)
		
		# Dump the search response for debug purposes
		try:
			self.debugMessage("Creating HTML dump for debug in file %s" % debugfile, messagecallback)
			dumpfile = open(debugfile, "w")
			dumpfile.write(response)
			dumpfile.close()
		except (IOError):
			self.debugMessage("IO Error creating debug file", messagecallback)
			self.debugMessage(traceback.format_exc(), messagecallback)
			
	def getUserStats(self, dom):
		userStats = {}
		for node in dom.getElementsByTagNameNS(self._XHTML_NS, 'ul'):
			# Pull the user's ID out to facilitate grabbing the user's data off the profile page
			if node.getAttribute("id") == "userinfo_username":
				for url in [ link.getAttribute("href") for link in node.getElementsByTagName("a")]:
					if url.startswith("user.php?id="):
						userStats["user_id"] = url.split("=")[1]
						break
				
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
			
if __name__ == "__main__":
	print "Module to manage what.cd as a web service"
