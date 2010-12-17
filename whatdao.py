#!/usr/bin/python
import sqlite3 as sqlite
from what import Format, Album

LAST_ROWID = "select last_insert_rowid()"

ALBUM_INSERT = "insert into album (artist, title, year, torrent) values (?, ?, ?, ?)"

FORMAT_INSERT = """
insert into format (album_id, format, bitrate, source, edition, seeds, size, scene, freeleech, url) 
values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SNATCHED_QUERY = """
select a.artist, a.title, a.year, a.torrent, f.format, f.bitrate, f.source, f.edition, f.seeds
, f.size, f.scene, f.freeleech, f.url
from album a, format f
where a.id = f.album_id
"""

ALBUM_DELETE = "delete from album"

FORMAT_DELETE = "delete from format"

class WhatDAO:
	def __init__(self):
		self.conn = sqlite.connect('whatbot.db')
		self.conn.row_factory = sqlite.Row
		
	def saveSnatched(self, snatched):
		for album in snatched:
			self.conn.execute(ALBUM_INSERT, (album.artist, album.title, album.year, album.torrent))
			last_album = self.conn.execute(LAST_ROWID, ()).fetchone()[0]

			for f in album.formats:
				self.conn.execute(FORMAT_INSERT, (last_album, f.format, f.bitrate, f.source, f.edition, f.seeds, f.size, f.scene, f.freeleech, f.url))
		
		self.conn.commit()
		
	def replaceSnatched(self, snatched):
		self.conn.execute(ALBUM_DELETE, ())
		self.conn.execute(FORMAT_DELETE, ())
		self.saveSnatched(snatched)

	def loadSnatched(self):
		snatched = []
		for row in self.conn.execute(SNATCHED_QUERY, ()).fetchall():
			album = Album()
			album.artist = row["artist"]
			album.title = row["title"]
			album.year = row["year"]
			album.torrent = row["torrent"]
			format = Format()
			format.format = row["format"]
			format.bitrate = row["bitrate"]
			format.source = row["source"]
			format.edition = row["edition"]
			format.seeds = row["seeds"]
			format.size = row["size"]
			format.scene = row["scene"]
			format.freeleech= row["freeleech"]
			format.url = row["url"]
			album.formats = [format]
			
			snatched.append(album)
		
		return snatched

if __name__ == "__main__":
	print "Module to manage persistent data for the WhatBot"