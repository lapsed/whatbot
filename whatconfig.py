#!/usr/bin/python
import re
from ConfigParser import SafeConfigParser
from rankingselector import FormatRankingRule

class WhatConfigParser(SafeConfigParser):
	# Transform between an ordered list of FormatRankingRule and the .cfg format
	def loadRankings(self):
		rankings=[]
		# mmmm tasty
		for format, bitrate in [ item[1].split("|") for item in sorted(self.items("format"), key=lambda x:(int(x[0]))) ]:
			rankings.append(FormatRankingRule(format, bitrate))
			
		return rankings
	
	def saveRankings(self, rankings):
		self.remove_section("format")
		self.add_section("format")
		rank = 100
		for format, bitrate in [(r.format, r.bitrate) for r in rankings]:
			value = format + "|" + re.sub("%", "%%", bitrate)
			self.set("format", str(rank), value)
			rank += 100
			
	# Return ranking as list of tuples (format, bitrate, rank)
	def getRankingRules(self):
		rules = []
		for item in self.items("format"):
			format, bitrate = item[1].split("|")
			rules.append((format, bitrate, item[0]))
		
		return rules

if __name__ == "__main__":
	print "Extended config parser for the WhatBot"
