#!/usr/bin/python
import urllib, urllib2, httplib
import re, traceback, time, socket, datetime

from xml.dom import minidom

from whatbase import WhatBase
from whatbeans import Format, Edition, Album, Request, Collage
from whatparser import Parser

class ResponseBody:
	pass

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
		
		# Set up wait times
		self.wait_times = {}
		for name in [ 'between_searches', 'art_grabs', 'snatched_pages' ]:
			self.wait_times[name] = int(config.get('wait_times', name))
		
		# Set up debug flags
		self.debug = {}
		for flag in [ 'dump_searches', 'dump_detail_pages' ]:
			self.debug[flag] = '1' == config.get('debug', flag) and True or False
		
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
		conn = httplib.HTTPSConnection(self._sitename)
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

			# Grab the homepage and scrape user's stats off it
			homepage = self.request("GET", "/index.php", "", self.headers).body
			try:
				self.userstats = self.parser.getUserStats(homepage)
			except:
				print "Error parsing home page, dumping homepage.htm"
				self.dumpFile("homepage.htm", homepage)
				raise
		except (KeyError, AttributeError):
			# Login failed, most likely bad creds or the site is down, nothing to do
			self.headers = None
			self.userstats = None
		
		return self.headers
		
	def loggedIn(self):
		return self.headers and True or False
	
	def getCollage(self, collageid):
		return self.request("GET", "/collages.php?id=" + str(collageid), "", self.headers).body
		
	def getRequests(self, pagenumber):
		return self.request("GET", "/requests.php?type=&submit=true&search=&tags=&tags_type=1&show_filled=on&releases[]=1&releases[]=3&releases[]=5&releases[]=6&releases[]=7&releases[]=8&releases[]=9&releases[]=11&releases[]=13&releases[]=14&releases[]=15&releases[]=16&releases[]=21&formats_strict=on&formats[]=0&bitrate_strict=on&bitrates[]=2&bitrates[]=6&bitrates[]=7&media[]=0&media[]=1&media[]=2&media[]=3&media[]=4&media[]=5&media[]=6&media[]=7&media[]=8&page=" + str(pagenumber), "", self.headers).body

	def getRequest(self, request_id):
		return self.request("GET", "/requests.php?action=view&id=" + str(request_id), "", self.headers).body
		
	def getTorrentGroup(self, torrent_group_id):
		return self.request("GET", "/torrents.php?id=" + str(torrent_group_id), "", self.headers).body
		
	def search(self, searchstr):
		searchform = {'searchstr': searchstr}
		data = urllib.urlencode(searchform)
		return self.request("GET", "/torrents.php?" + data, "", self.headers).body

	# restrict search results to the music category, whatbot's scope does not include comedy/audiobooks
	def advsearch(self, artist, album):
		searchform = {'action': 'advanced', 'artistname': artist, 'groupname': album, 'tags_type': '1', 'order_by': 'time', 'order_way': 'desc', 'filter_cat[1]': '1' }
		data = urllib.urlencode(searchform)
		return self.request("GET", "/torrents.php?" + data, "", self.headers).body

	def snatched(self, progressbar):
		# Use a sneaky RE to detect the end of the snatched list
		nodata = re.compile('<div class="center">\s+Nothing found!\s+</div>', re.MULTILINE + re.DOTALL)
	
		snatched = []
		page = 1
		while True:
			progressbar.message("Grabbing snatched page %s" % (page,))
			html = self.snatchedPage(page)
			if nodata.search(html):
				break

			try:
				snatched += self.parser.extractAlbumsSnatched(html)
			except:
				progressbar.message("Error parsing snatched page %d, dumping" % page)
				dumpFile("snatched_%04d.htm" % page, html)
				page += 1
				continue
				
			progressbar.message("Added %s snatched albums, now sleeping..." % (len(snatched),))
			page += 1
			
			# Sleep for five seconds, it's only polite
			time.sleep(self.wait_times['snatched_pages'])
		return snatched
		
	def snatchedPage(self, page):
		# filter snatches for music torrents only
		return self.request("GET", "/torrents.php?page=%s&type=snatched&userid=%s&categories%5B1%5D=1" % (page, self.userstats["user_id"]), "", self.headers).body

	def torrentdetails(self, album):
		return self.request("GET", "/" + album.torrent, "", self.headers).body
	
	def searchReplacements(self, searches, progressbar):
		foundalbums = []
		
		# Convert from list to set and back again as we are stripping junk and deduplicating
		advsearches = list(set([ ( search[0], re.sub(" *\([^\)]+\) *", "", search[1])) for search in searches ]))
		
		for i in range(len(advsearches)):
			advsearch = advsearches[i]
			progressbar.message("About to search what for %s: %s, sleeping for %d seconds to be polite..." % (advsearch + (self.wait_times['between_searches'],)))
			time.sleep(self.wait_times['between_searches'])
			
			advresponse = self.advsearch(advsearch[0], advsearch[1])
			if self.debug['dump_searches']:
				self.dumpPage('adv', advsearch[0], advsearch[1], advresponse)

			try:
				albums = self.parser.extractAlbumsSearch(advresponse)
			except:
				progressbar.message("Error parsing advanced search for %s: %s, dumping HTML" % advsearch)
				self.dumpPage('adv', advsearch[0], advsearch[1], advresponse)
				continue
				
			if len(albums) > 0:
				progressbar.message("Found %d albums, adding them to match list" % len(albums))
				foundalbums.extend(albums)
			else:
				progressbar.message("Nothing found on what.cd")
				
			ratio =  float(i + 1) / float(len(advsearches))
			progressbar.updateProgress(ratio)
		
		return foundalbums

	def grabart(self, folder, album, progressbar, imagepreview):
		htmldetail = self.torrentdetails(album)
		if self.debug['dump_detail_pages']:
			self.dumpPage('det', album.artist, album.title, htmldetail)
			
		# Throttle HTML request throughput
		time.sleep(self.wait_times['art_grabs'])

		try:
			album.art = self.parser.locateAlbumArt(htmldetail)
		except:
			progressbar.message("Error locating album art for %s: %s, dumping HTML" % (album.artist, album.title))
			self.dumpPage('det', album.artist, album.title, htmldetail)
			album.art = ""
		
		if not album.art.startswith('static/common/noartwork'):
			imagepreview.changeImage(album.downloadAlbumArt(folder, progressbar.message))
		else:
			progressbar.message("what.cd has no artwork for %s: %s, please submit some" % (album.artist, album.title))

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

	def dumpFile(self, filename, page):
		f = open(filename, "w")
		f.write(page)
		f.close
	
	def dumpPage(self, prefix, artist, album, page):
		filename = "%s_%s_%s.html" % (prefix, urllib.quote_plus(artist), urllib.quote_plus(album))
		self.dumpFile(filename, page)
		
	# Expecting a list of (artist, album, folder) tuples for local foldernames and refs to GUI progress objects
	def downloadImages(self, tuples, progressbar, imagepreview):
		pos = 0
		for artist, mangledalbum, folder in tuples:
			album = self.unmangle(mangledalbum)
			progressbar.message("Advanced search for %s: %s" % (artist, album))

			advresponse = self.advsearch(artist, album)
			if self.debug['dump_searches']:
				self.dumpPage('adv', artist, album, advresponse)

			# Sleep after a search plz
			time.sleep(self.wait_times['between_searches'])

			try:
				albums = self.parser.extractAlbumsSearch(advresponse)
			except:
				progressbar.message("Parse error processing search for %s: %s, dumping HTML" % (artist, album))
				self.dumpPage('adv', artist, album, advresponse)
				albums = []

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

			time.sleep(self.wait_times['art_grabs'])
			progressbar.message("Found exactly one album, grabbing art")
			imagepreview.changeImage(testimages[pos % len(testimages)])
			
			ratio =  float(pos + 1) / float(len(tuples))
			progressbar.updateProgress(ratio)		
			pos += 1
						
if __name__ == "__main__":
	print "Module to manage what.cd as a web service"
