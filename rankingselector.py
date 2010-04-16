#!/usr/bin/python
from Tkinter import *

class FormatRankingRule:
	def __init__(self, format, bitrate):
		self.format = format
		self.bitrate = bitrate

class FormatDisplayWidget(Frame):
	def __init__(self, parent, format):
		Frame.__init__(self, parent)
		self.l1 = Label(self, text=format.format, width=5)
		self.l2 = Label(self, text=self.formatBitrate(format.bitrate))
		self.l1.grid(row=0, column=0, sticky=W)
		self.l2.grid(row=0, column=1, sticky=W)
		
	@staticmethod
	def formatBitrate(bitrate):
		if bitrate == "":
			return "Any Bitrate"
		else:
			return bitrate

	def update(self, format):
		self.l1.config(text=format.format)
		self.l2.config(text=self.formatBitrate(format.bitrate))
		
class FormatEntryWidget(Frame):		
	legalFormats = ("FLAC", "MP3", "AAC", "OGG")

	def __init__(self, parent):
		Frame.__init__(self, parent)
		self.format = StringVar(self)
		self.format.set(self.legalFormats[0])
		option = apply(OptionMenu, (self, self.format) + self.legalFormats)
		option.configure(width=4)
		option.grid(row=0, column=0)
		self.e2 = Entry(self)
		self.e2.grid(row=0, column=1)
	
	def get(self):
		return FormatRankingRule(self.format.get(), self.e2.get())
		
class RankingSelector(Frame):
	def __init__(self, parent, initialrankings):
		Frame.__init__(self, parent)
		self.items = initialrankings
		self.layout()
		
	def layout(self):
		self.datawidgets = upbuttons = downbuttons = delbuttons = []

		for i in range(len(self.items)):
			datawidget = FormatDisplayWidget(self, self.items[i])
			self.datawidgets.append(datawidget)
			upbut = Button(self, text = "^", command = lambda x = i: self.upButtonPressed(x))
			downbut = Button(self, text = "v", command = lambda x = i: self.downButtonPressed(x))
			delbut = Button(self, text = "x", command = lambda x = i: self.delButtonPressed(x))
			
			
			datawidget.grid(row=i, column=0, sticky=W)
			upbut.grid(row=i, column=1)
			downbut.grid(row=i, column=2)
			delbut.grid(row=i, column=3)
			
		self.entrywidget = FormatEntryWidget(self)
		self.entrywidget.grid(row=len(self.items), column=0)

		addbutton = Button(self, text = "+", command = self.addItem)
		addbutton.grid(row=len(self.items), column=1)
		
		self.update_idletasks()
	
	def swapItems(self, i, j):
		temp = self.items[i]
		self.items[i] = self.items[j]
		self.items[j] = temp
		
	def refreshLabels(self):
		for i in range(len(self.items)):
			self.datawidgets[i].update(self.items[i])
			
		self.update_idletasks()
	
	def redraw(self):
		for widget in self.winfo_children():
			widget.destroy()
		
		self.layout()
	
	def upButtonPressed(self, caller):
		if caller > 0:
			self.swapItems(caller, caller - 1)
			self.refreshLabels()

	def downButtonPressed(self, caller):
		if caller < len(self.items) - 1:
			self.swapItems(caller, caller + 1)
			self.refreshLabels()

	def delButtonPressed(self, caller):
		del self.items[caller]
		self.redraw()
		
	def addItem(self, *args):
		self.items.append(self.entrywidget.get())
		self.redraw()
		
if __name__ == "__main__":
	print "Compound widget to rank available formats"
