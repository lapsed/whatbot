# Request finder
import time

from mediamonkey import MediaMonkey
from what import WhatCD
from whatdao import WhatDAO
from whatconfig import WhatConfigParser
from whatparser import Parser

class RequestFinder():
	def dump_page(self, filename, page):
		f = open(filename, 'w')
		f.write(page)
		f.close()
		
	def find_requests(self):
		sleep_time = int(config.get('request', 'sleep_time'))
		# iterate over request pages specified on command line
		for i in range(int(config.get('request', 'startpage')), int(config.get('request', 'endpage')) + 1):
			print 'Processing request page ' + str(i)
			try:
				page = whatcd.getRequests(i)
				requests = parser.parseRequests(page)
			except:
				print "Error processing request page i, dumping source"
				self.dump_page('request_%03d.htm' % i)
				continue
				
			# for each request
			for request in requests:
				# Sleep before hitting the site to avoid flooding
				print request
				time.sleep(sleep_time)
				local_request = dao.loadRequest(request.request_id)
				# if doesn't already exist in local database
				if local_request.request_id == 0:
					print "Getting details of remote request..."
					# Sleep before hitting the site to avoid flooding
					time.sleep(sleep_time)
					# load request page
					try:
						page = whatcd.getRequest(request.request_id)
						torrent_group_id = parser.parseRequest(page)
					except:
						print "Error processing request ID %d, dumping source"
						self.dump_page('request_details_%d.htm' % request.request_id)
						continue
						
					if torrent_group_id:
						request.torrent_group_id = torrent_group_id
						time.sleep(sleep_time)
						# load torrent details page and check for FLAC
						try:
							page = whatcd.getTorrentGroup(torrent_group_id)
							request.flac_present = parser.parseGroup(page)
					except:
						print "Error processing torrent ID %d, dumping source"
						self.dump_page('torrent_details_%d.htm' % torrent_group_id)
						continue
					# store request details in local sql database
					print "Storing request..."
					dao.storeRequest(request)
				else:
					print "Updating local copy of top level request data"
					# update filled status and reward only if present in local db
					local_request.filled = request.filled
					local_request.reward = request.reward
					dao.storeRequest(local_request)
  

if __name__ == "__main__":
	# Create and initialise singletons
	config = WhatConfigParser()
	config.read('whatbot.cfg')
	mm = MediaMonkey(config)
	whatcd = WhatCD(config, mm)
	parser = Parser()
	dao = WhatDAO()
	# If we can log in to what.cd, go look for requests
	if whatcd.login():
		rf = RequestFinder()
		rf.find_requests()
	else:
		print "Aborting: Unable to log in to what.cd"
		
