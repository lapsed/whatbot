import re

from bs4 import BeautifulSoup

from whatbase import WhatBase
from whatbeans import Format, Edition, Album, Request, Collage

class Parser(WhatBase):
	_XHTML_NS="http://www.w3.org/1999/xhtml"

	def getText(self, nodelist):
		rc = ""
		for node in nodelist:
			if node.nodeType == node.TEXT_NODE:
				rc = rc + node.data
		return rc

	def parseRequests(self, page):
		soup = BeautifulSoup(page)
		requests = []
		for tab in soup.find_all('table'):
			if tab.get('id') == 'request_table':
				# Skip over the table header 
				for tr in tab.find_all('tr')[1:]:
					request = Request()
					td = tr.find_all('td')
					release = td[0].find_all('a')
					request.artist_ids=[]
					request.artist_names=[]
					for i in range(0, len(release)):
						link = release[i].get('href')
						if link.startswith("artist.php"):
							request.artist_ids.append(link.split("=")[1])
							request.artist_names.append(release[i].get_text())
						if link.startswith("requests.php"):
							request.request_id = link.split("=")[2]
							request.request_name = release[i].get_text()
							request.tags = [ tag.get_text() for tag in release[i+1:] ]
							break
					request.reward = self.bytesFromString(td[2].get_text().strip())
					request.filled = td[3].get_text().strip()
					if request.filled != "No":
						request.filled = "Yes"
					if len(request.artist_ids) == 0:
						request.artist_ids = [0]
						request.artist_names = ['Various Artists']
					requests.append(request)
				break

		return requests
	
	def parseRequest(self, page):
		torrent_group = None
		soup = BeautifulSoup(page)
		for div in soup.find_all('div'):
			if div.get('class') == ['main_column']:
				tds = div.find_all('td')
				for i in range(0, len(tds)):
					if tds[i].get('class') == ['label']:
						if tds[i].get_text() == "Torrent group":
							torrent_group = int(tds[i+1].get_text().strip().split("=")[1])
			
		return torrent_group

	def parseGroup(self, page):
		soup = BeautifulSoup(page)
		flac_present = False
		for table in soup.find_all('table'):
			if 'torrent_table' in table.get('class'):
				for tr in table.find_all('tr'):
					trclass = tr.get('class')
					if trclass and 'torrent_row' in trclass:
						for a in tr.find_all('a'):
							if a.get('href') == '#':
								if a.get_text().split('/')[0].strip() == 'FLAC':
									flac_present = True

		return flac_present

	def locateAlbumArt(self, page):
		soup = BeautifulSoup(page)
		
		for div in soup.find_all('div'):
			# Class is not a mandatory attribute of a div apparently
			if div.get('class') and "box_image_albumart" in div.get('class'):
				return div.img.get('src')

	def extractAlbumsSearch(self, page):
		soup = BeautifulSoup(page)
		albums = []
		for table in soup.find_all('table'):
			if 'torrent_table' in table.get('class'):
				albums = self.parseTorrentTable(table)
		
		return albums

	# Page has already been filtered by type - only music torrents will be included
	def extractAlbumsSnatched(self, page):
		soup = BeautifulSoup(page)
		albums = []
		for table in soup.find_all('table'):
			if 'torrent_table' in table.get('class'):
				# Unfortunately we cannot just directly reuse parse of torrent table from search
				# Snatched list is quite different - no editions in it and row classes are different
				for tr in table.find_all('tr')[1:]:
					for div in tr.find_all('div'):
						if "group_info" in div.get('class'):
							album = self.parseTorrentRow(div)
							break
					celltext = [ td.get_text() for td in tr.find_all('td') ]
					album.formats[0].size = celltext[3]
					album.formats[0].seeds = celltext[5]
					albums.append(album)		
					
		return albums
		
	def parseTorrentRow(self, div):
		# Create and link up a blank hierarchy of objects, we only have some of the data here
		album = Album()
		edition = Edition()
		album.editions = [edition]
		format = Format()
		format.edition = edition
		edition.formats = [format]
		album.formats = [format]
		# Default to Various Artists as no link to the artist page will exist in that case
		album.artist = 'Various Artists'
		# Default a fields where we just can't tell from the torrents snatched page
		album.type = 'Unknown'
		edition.original = False
		edition.medium = 'Unknown'
		
		for i, link in enumerate(div.find_all('a')[2:]):
			if link.get("href").startswith("artist.php?id="):
				if i == 0:
					album.artist = link.get_text()
				else:
					album.artist = album.artist + " and " + link.get_text()
			if link.get("href").startswith("torrents.php?id="):
				album.torrent = link.get("href")
				album.title = link.get_text()
			if link.get("href") == "#":
				# We've gone past album and artist data
				break
		
		# Load the stripped strings into a list so we can look forward in it
		slist = [ sts for sts in div.stripped_strings]
		for i, s in enumerate(slist):
			match = re.search("\[([0-9]{4})\] - (.*)", s)
			if match:
				if len(match.groups()) == 2:
					edition.year = match.group(1)
					album.year = match.group(1)
					formatitems = match.group(2).split(" / ")
					self.parseFormatItems(format, formatitems)					
			else:
				match = re.search("\[([0-9]{4})\] \[", s)
				if match:
					if len(match.groups()) == 1:
						edition.year = match.group(1)
						album.year = match.group(1)
						j=i+1
						while True:
							if slist[j].startswith("Vote"):
								break
							s = s + slist[j]
							j += 1
						formatitems = [ item.strip() for item in s.split(" - ")[1].split("/") ]
						self.parseFormatItems(format, formatitems)	
					
		return album

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

		# First item is format, everything else makes up the "bitrate" field
		format.format = formatitems[0]
		format.bitrate = "/".join(formatitems[1:len(formatitems)])

	def parseAlbumData(self, row):
		album = Album() 
		topnode = row.find_all("td")[2]
		yeartype = re.search("\[([0-9]{4})\] \[([A-Za-z ]+)\]", str(topnode))
		album.year = yeartype.group(1)
		album.type = yeartype.group(2)
		# Default to Various Artists as no link will exist for multi-artist torrents
		album.artist = "Various Artists" 
		links = topnode.find_all("a") 
		for link in links:
			if link.get("href").startswith("artist.php?id="):
				album.artist = link.get_text()
			elif link.get("href").startswith("torrents.php?id="): 
				album.title = link.get_text()
				album.torrent = link.get("href")

		album.editions = []
		album.formats = [] 
		return album
		
	def parseEditionData(self, row, album):
		edition = Edition()
		editiondata = row.find("strong").get_text().split(" / ")
		yearlabel = editiondata[0].split(' - ')
		if yearlabel[0].strip().endswith("Original Release"):
			edition.year = album.year
			edition.original = True
		elif yearlabel[0].strip().endswith("Unknown Release(s)"):
			edition.year = 'Unknown'
			edition.original = False
		else:
			edition.year = re.search("([0-9]{4})", yearlabel[0]).group(1)
			edition.label = yearlabel[1].strip()
			edition.original = False
		
		edition.medium = editiondata[-1].strip()
		if len(editiondata) == 4:
			edition.catalog = editiondata[1].strip()
			edition.title = editiondata[2].strip()
		elif len(editiondata) == 3:
			edition.catalog = editiondata[1].strip()
		
		edition.formats = []
		return edition
	
	def parseTorrentTable(self, torrent_table):
		albums = []
		current_edition = None
		rows = torrent_table.find_all("tr")

		for row in rows:
			if "group" in row.get("class"):
				album = self.parseAlbumData(row)
				albums.append(album)
				
			if "edition" in row.get("class"):
				current_edition = self.parseEditionData(row, album)
				album.editions.append(current_edition)

			elif "group_torrent" in row.get("class"):
				format = Format()

				links = row.find_all("a")
				if len(links) == 3:
					format.url = links[0].get("href")
					formatitems = links[2].get_text().split(" / ")
					self.parseFormatItems(format, formatitems)

					cells = row.find_all("td")
					format.size = cells[3].get_text()
					format.seeds = cells[5].get_text()
					
					# We are linking all the formats onto the editions and vice versa to make scoring and data retrieval 
					# as simple as possible
					album.formats.append(format)
					current_edition.formats.append(format)
					format.edition = current_edition

		return albums
	
	def getUserStats(self, page):
		userStats = {}
		soup = BeautifulSoup(page)
		
		for node in soup.find_all('ul'):
			if node.get("id") == "userinfo_username":
				for url in [ link.get("href") for link in node.find_all("a") ]:
					if url.startswith("user.php?id="):
						userStats["user_id"] = url.split("=")[1]
						break
						
			if node.get("id") == "userinfo_stats":
				for li in node.find_all('li'):
					id = li.get("id")
					
					# This bit's just great, don't ask me why span tags are nested for the user's ratio
					if id == "stats_ratio":
						val = li.find_all('span')[1].get_text()
					else:
						val = li.find_all('span')[0].get_text()
						
					# Rebase seed/leech user stats to bytes
					if id in ["stats_seeding", "stats_leeching"]:
						val = self.bytesFromString(val)
					
					userStats[id] = val
		
		return userStats

if __name__ == "__main__":
	print "Class to parse responses from what.cd using BeautifulSoup"
