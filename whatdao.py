#!/usr/bin/python
import sqlite3 as sqlite
from what import Format, Album, Request

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

LOAD_REQUEST_QUERY = """
select r.request_id, r.request_name, r.reward, r.filled, r.torrent_group_id, r.flac_present
, a.artist_id, a.artist_name, t.tag
from request r, request_artist a, request_tag t
where t.request_id = r.request_id
and a.request_id = r.request_id
and r.request_id = ?
order by a.artist_id, t.tag
"""

REQUEST_INSERT = "insert into request(request_id, request_name, reward, filled, torrent_group_id, flac_present) values (?, ?, ?, ?, ?, ?)"

ARTIST_INSERT = "insert into request_artist(request_id, artist_id, artist_name) values (?, ?, ?)"

TAG_INSERT = "insert into request_tag (request_id, tag) values (?, ?)"

REQUEST_UPDATE = "update request set reward = ?, filled = ? where request_id = ?"

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
		
	def loadRequest(self, request_id):
		request = Request()
		rows = 0
		last_artist = 0
		last_tag = ""
		tags_done = False
		for row in self.conn.execute(LOAD_REQUEST_QUERY, (request_id,)).fetchall():
			if rows == 0:
				request.in_db = 1
				request.request_id = row["request_id"]
				request.request_name = row["request_name"]
				request.reward = row["reward"]
				request.filled = row["filled"]
				request.torrent_group_id = row["torrent_group_id"]
				request.flac_present = row["flac_present"]
				request.artist_ids = [row["artist_id"]]
				last_artist = [row["artist_id"]]
				request.artist_names = [row["artist_name"]]
				request.tags=[row["tag"]]
				last_tag =[row["tag"]]
			else:
				if row["artist_id"] != last_artist:
					request.artist_ids.append(row["artist_id"])
					request.artist_names.append(row["artist_name"])
					last_artist = row["artist_id"]
					tags_done = True
				if row["tag"] != last_tag and not tags_done:
					request.tags.append(row["tag"])
					last_tag = row["tag"]
			
			rows = rows + 1
		
		return request
	
	def storeRequest(self, request):
		if (request.in_db):
			# All we do here is update the filled flag and the reward, assuming everything else to be static
			self.conn.execute(REQUEST_UPDATE, (request.reward, request.filled, request.request_id))
			self.conn.commit()
		else:
			# Must insert rows
			self.conn.execute(REQUEST_INSERT, (request.request_id, request.request_name, request.reward, request.filled, request.torrent_group_id, request.flac_present))
			for artist in zip(request.artist_ids, request.artist_names):
				self.conn.execute(ARTIST_INSERT, (request.request_id,) + artist)
			for tag in request.tags:
				self.conn.execute(TAG_INSERT, (request.request_id, tag))
			self.conn.commit()

if __name__ == "__main__":
	print "Module to manage persistent data for the WhatBot"