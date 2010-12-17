#!/usr/bin/python
import re
import sqlite3 as sqlite

class MediaMonkey:
	# Local low bitrate search
	LOW_BITRATE_QUERY = """
select v.albumartist, v.album, s.extension, v.bitrate from
( select case 
    when albumartist = 'Various' then 'Various Artists'
    when albumartist = 'VA' then 'Various Artists'
    else albumartist
  end albumartist
  , album, extension, count(*), cast(avg(bitrate) as integer) bitrate 
  , min(id) id
  from songs
  where extension in (%s) -- Change this if you want to filter by different formats
  and albumartist != '' and album != ''
  and genre not in ('Comedy', 'Audiobooks')
  group by albumartist, album 
  having count(*) > 3 -- "Albums" with less than this number of tracks will be skipped
) v, songs s
where s.id = v.id
and v.bitrate <= %d -- Change this number to alter the threshold at which tracks are considered to be "low bitrate"
order by v.albumartist, v.album %s"""	

	# Local missing art search
	MISSING_ART_QUERY = """
select albumartist, album, idfolder
from (
select
 case
   when s.albumartist = 'VA' then 'Various Artists'
   when s.albumartist = 'Various' then 'Various Artists'
   else s.albumartist
 end albumartist
, s.album album, f.id idfolder
from songs s, folders f
where s.idfolder = f.id
and s.album != '' and s.albumartist != ''
and not exists
( select * from covers c where c.idsong = s.id ) 
group by albumartist, album, folder 
having count(*) >= 3
) order by albumartist, album"""

	# Collapse folder hierarchy
	COLLAPSE_FOLDER_QUERY = """
select m.driveletter, f.folder
from foldershier h, folders f, medias m
where f.idmedia = m.idmedia
and f.id = h.idfolder
and h.idchildfolder = ?
order by f.id"""

	# Create the parameter
	def __init__(self, config):
		self._dbfile = config.get("mediamonkey", "dbfile")
		self.conn = None
		if self.testConnection(self._dbfile):
			self.connect(self._dbfile)

	# IUNICODE collation function, this only simulates the Windows one MediaMonkey uses
	# It is possible that sort order will vary between python and MM but that is not a big deal
	def iUnicodeCollate(self, s1, s2):
		return cmp(s1.lower(), s2.lower())
		
	def connected(self):
		return self.conn and True or False
		
	def testConnection(self, dbfile = None):
		if not dbfile:
			dbfile = self._dbfile
			
		try:
			testconn = sqlite.connect(dbfile)
			testconn.execute("select count(*) from medias").fetchall()
		except sqlite.Error, oe:
			testconn = None
		
		return testconn

	def connect(self, dbfile):
		# destroy existing connection if applicable
		if self.conn:
			self.conn.close()
	
		# connect to database
		self.conn = sqlite.connect(dbfile)

		# register our custom IUNICODE collation function
		self.conn.create_collation('IUNICODE', self.iUnicodeCollate)

	def loaderdump(self, tuples):
		"""Dump tuple data in a format that is useful for SQL*Loader"""
		for tuple in tuples:
			munged = (str(v).replace('"', '""') for v in tuple)
			print  '"' + '"~"'.join(munged) + '"' + "|"

	def prettyprint(self, tuples):
		for tuple in tuples:
			print "|".join(str(v) for v in tuple)

	def dumpquery(self, sql):
		self.loaderdump(self.conn.execute(sql, ()).fetchall())

	def query(self, sql):
		self.prettyprint(self.conn.execute(sql, ()).fetchall())

	def querylist(self, sql):
		return self.conn.execute(sql, ()).fetchall()
		
	def queryBoundList(self, sql, binds):
		return self.conn.execute(sql, binds).fetchall()

	def start(self, sqlfile):
		f = open(sqlfile, 'r')
		sql = f.read()
		f.close()
		self.query(sql)

	def fullpath(self, folderid):
		folders = self.conn.execute(self.COLLAPSE_FOLDER_QUERY, (folderid,)).fetchall()
		path=chr(65 + folders[0][0]) + ":"
		for dummy, folder in folders[1:]:
			path = path + '/' + folder
			
		return path

	def localSearch(self, formats, bitrate, limitrows):
		formatbind = "'" + "','".join(formats) + "'"

		if limitrows == 0:
			limitbind = ""
		else:
			limitbind = "limit %d" % limitrows
	
		return self.querylist(self.LOW_BITRATE_QUERY % (formatbind, bitrate, limitbind))
		
	def missingArt(self):
		return self.querylist(self.MISSING_ART_QUERY)
	
if __name__ == "__main__":
	print "Simple sqlite3 DAO for MediaMonkey"
	
