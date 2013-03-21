import re, urllib2

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
		
	def nvl(self, str1, str2):
		if str1 == "":
			return str2 
		else:
			return str1

if __name__ == "__main__":
	print "Base class for what.cd beans"
