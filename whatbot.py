#!/usr/bin/python
import pickle, sqlite3, time
import tkMessageBox, tkFileDialog
import mediamonkey, what, whatdao

from Tkinter import *
from whatconfig import WhatConfigParser
from rankingselector import *

# PIL would be nice, but we can manage without
try:
	from PIL import Image, ImageTk
	usePIL = True
except ImportError:
	usePIL = False

class WhatBotGui(Tk):
	lossyformats = sorted(["M4A", "AAC", "MP3", "MPC", "OGG", "WMA"])

	def __init__(self):
		Tk.__init__(self)

		self.title("Search specification")
		self.ready = False
		menu = Menu(self)
		self.config(menu=menu)

		filemenu = Menu(menu, tearoff=0)
		menu.add_cascade(label="File", menu=filemenu)
		filemenu.add_command(label="Saved Search...", command=self.loadRemoteSearch)
		filemenu.add_command(label="Missing Art...", command=lambda: MissingArt(self, mm.missingArt()))
		filemenu.add_command(label="My snatches...", command=lambda: Snatched(self), state=DISABLED)
		filemenu.add_command(label="Options...", command=self.changeOptions)
		filemenu.add_separator()
		filemenu.add_command(label="Exit", command=exit)
		
		helpmenu = Menu(menu, tearoff=0)
		menu.add_cascade(label="Help", menu=helpmenu)
		helpmenu.add_command(label="About...", command=self.about)

		l1 = Label(self, text="Bitrate Cutoff")
		self.cutoff = Entry(self, justify="right")
		self.cutoff.insert(END, "160000")
		
		l1.grid(row=0, column=0)
		self.cutoff.grid(row=0, column=1)
		
		l2 = Label(self, text="Replaceable Formats")
		self.checkframe = Frame(self)

		l2.grid(row=1, column=0)
		self.checkframe.grid(row=1, column=1)
		
		self.checkboxes = {}
		self.checkboxvalues = {}
		
		for lossyformat in self.lossyformats:
			self.checkboxvalues[lossyformat] = IntVar()
			self.checkboxes[lossyformat] = \
				Checkbutton(self.checkframe, text=lossyformat, variable=self.checkboxvalues[lossyformat])
			self.checkboxes[lossyformat].grid(row=len(self.checkboxes), column=0)

		l3 = Label(self, text="Max search results\n(0 means unlimited)")
		self.searchlimit = Entry(self, justify="right")
		self.searchlimit.insert(END, "0")

		l3.grid(row=2, column=0)
		self.searchlimit.grid(row=2, column=1)
		
		self.gobutton = Button(self, text="Run search...", command=self.runLocalSearch, state=DISABLED)
		self.gobutton.grid(row=3, column=0, columnspan=2, pady=5)
		
		self.statusbar = StatusBar(self)
		self.statusbar.grid(row=4, column=0, columnspan=2, sticky="EW")

		self.protocol("WM_DELETE_WINDOW", exit)
		
		self.update()
		self.login()
		
	def changeOptions(self):
		OptionsDialog(self)
		self.login()
		
	def runLocalSearch(self):
		# Do some validation on the search spec
		try:
			bitrate = int(self.cutoff.get())
			
			if bitrate < 32000 or bitrate > 320000:
				raise ValueError("Bitrate must be an integer between 32000 and 320000")
			
			searchformats=[]
			for k in iter(self.checkboxes):
				if (self.checkboxvalues[k].get() == 1):
					searchformats.append(k)
			
			if len(searchformats) == 0:
				raise ValueError("Please select at least one format to replace")
						
			limitrows = abs(int(self.searchlimit.get()))
			
			#print "run search with cutoff = %d and formats in (%s), max %d rows" % (bitrate, str(searchformats), limitrows)
			LocalSearchResults(self, mm.localSearch(searchformats, bitrate, limitrows))
			
		except ValueError, v:
			tkMessageBox.showwarning("Validation failed", str(v))
			
	def about(self):
		tkMessageBox.showinfo("lapsed's WhatBot", "Brought to you in association with what.cd\n...move along\n\nVersion 0.5 alpha")
				
	def jumpBackToStart(self):
		self.remoteresults.destroy()
		self.deiconify()
		
	def loadRemoteSearch(self):
		savefilename = tkFileDialog.askopenfilename(parent=self)
		if savefilename:
			savefile = open(savefilename, "rb")
			results = pickle.load(savefile)
			savefile.close()
			self.withdraw()
			self.remoteresults = RemoteSearchResults(results, self.jumpBackToStart)
	
	def login(self):
		self.gobutton.config(state=DISABLED)
		self.statusbar.set("Logging into what...")
		self.update()
		if whatcd.login():
			if mm.connected():
				self.statusbar.set("All options OK, ready to search")
				self.ready = True;
				self.gobutton.config(state=NORMAL)
			else:
				self.statusbar.set("No MediaMonkey database, please review options")
		else:
			self.statusbar.set("Cannot log in to what, please review options")
			
class ScrollGridSelect(Frame):
	# headings is a tuple, data must be a list of tuples of the same width as the headings (surprise)
	# TODO: do some data validation and exception handling, there are a large number of assumptions here
	def __init__(self, parent, headings, widths, height, data, selectcallback = None):
		Frame.__init__(self, parent)
		self.selectcallback = selectcallback
		self.scrollbar = Scrollbar(self, orient=VERTICAL, command=self.yview)
		
		self.labels = []
		self.listboxes = []
		self.selected = []
		
		for index in range(len(headings)):
			newlabel = Label(self, text = headings[index])
			self.labels.append(newlabel)
			
			newlb = Listbox(self, selectmode=MULTIPLE, yscrollcommand=self.yscroll, exportselection=0 \
				, width=widths[index], selectborderwidth=0, highlightthickness=0, height=height)
			
			newlb.columnconfigure(0, weight=1)
			
			# Only bind the listbox if there is data to put in it
			if len(data) > 0:
				newlb.bind("<<ListboxSelect>>", self.select)
				
			self.listboxes.append(newlb)

		for datum in data:
			for i in range(len(datum)):
				self.listboxes[i].insert(END, datum[i])

		allb = Button(self, text="Select All", command=self.selectall)
		noneb = Button(self, text="Select None", command=self.selectnone)
	
		for i in range(len(self.labels)):
			self.labels[i].grid(row=0, column=i)
			self.listboxes[i].grid(row=1, column=i, sticky=N+S+E+W)
			self.grid_columnconfigure(i, weight=widths[i])
			
		self.scrollbar.grid(row=1, column=len(self.labels), sticky=N+S)

		allb.grid(row=2, column=0)
		noneb.grid(row=2, column=1)
		self.grid_rowconfigure(1, weight=1)

	# Can call out whenever the select list changes if required
	def changeSelection(self, nowselected):
		self.selected = nowselected
		if self.selectcallback:
			self.selectcallback(self.selected)
		
	# Event handlers
	def yscroll(self, *args):
		self.scrollbar.set(*args)
		
		for lb in self.listboxes:
			apply(lb.yview, ("moveto", args[0]))
		
	def yview(self, *args):
		for lb in self.listboxes:
			apply(lb.yview, args)

	def select(self, *args):
		clickedlb = args[0].widget
		nowselected = clickedlb.curselection()
		if len(nowselected) > len(self.selected):
			# item added
			for lb in self.listboxes:
				if lb != clickedlb:
					lb.select_set((set(nowselected) - set(self.selected)).pop())
		else:
			# item removed
			for lb in self.listboxes:
				if lb != clickedlb:
					lb.select_clear((set(self.selected) - set(nowselected)).pop())
		
		self.changeSelection(nowselected)

	# Button handlers
	def selectall(self):
		for lb in self.listboxes:
			lb.select_set(0, END)

		self.changeSelection(self.listboxes[0].curselection())
	
	def selectnone(self):
		for lb in self.listboxes:
			lb.select_clear(0, END)

		self.changeSelection(self.listboxes[0].curselection())
		
	def getSelectedData(self, columns):
		selectedData = []
		for item in self.selected:
			datum = []
			for col in columns:
				datum.append(self.listboxes[col].get(item))
			selectedData.append(tuple(datum))
		
		return selectedData

class RemoteProgress(Toplevel):
	_width = 400
	_height = 50

	def __init__(self, parent):
		Toplevel.__init__(self)
		self.title("Remote activity progress")
		self.parent = parent
		self.transient(parent)
		
		l1 = Label(self, text="Messages")
		l2 = Label(self, text="Progress")
		scrollbar = Scrollbar(self)
		self.txt = Text(self, state=DISABLED)
		scrollbar.config(command=self.txt.yview)
		self.txt.config(yscrollcommand=scrollbar.set)
		self.progcanvas = Canvas(self, width=self._width, height=self._height)
		
		l1.grid(row=0, column=0, columnspan=2)
		self.txt.grid(row=1, column=0)
		scrollbar.grid(row=1, column=1, sticky=N+S)
		l2.grid(row=2, column=0, columnspan=2, sticky=E+W)
		self.progcanvas.grid(row=3, column=0, columnspan=2)

	def close(self):
		self.destroy()
		
	def updateProgress(self, ratio):
		self.progcanvas.delete(ALL)
		self.progcanvas.create_rectangle(0, 0, self._width * ratio, self._height, fill='blue')
		
		self.update()
		
	def message(self, message):
		f = open('whatbot.log', 'a')
		f.write("%s\n" % message)
		f.close
		self.txt.config(state=NORMAL)
		self.txt.insert(END, message + "\n")
		self.txt.see(END)
		self.txt.config(state=DISABLED)
	
		self.update()

class ImagePreview(Toplevel):
	def __init__(self, parent, geometry, width=300, height=300):
		Toplevel.__init__(self)
		self.width = width
		self.height = height
		self.title("Last image preview")
		self.parent = parent
		self.transient(parent)
		self.preview = Label(self)
		if not usePIL:
			self.preview.config(text="PIL not installed, no preview available")
			self.preview.config(width=35, height=20)

		self.statusbar = StatusBar(self)
		
		self.preview.grid(row=0, sticky="NSEW")
		self.statusbar.grid(row=1, sticky="EW")
		self.geometry(geometry)
		self.withdraw()

	def close(self):
		self.destroy()
	
	def changeImage(self, imagefilename):
		self.statusbar.set(imagefilename)
		if usePIL:
			try:
				self.image = Image.open(imagefilename).resize((self.width, self.height), Image.BICUBIC)
				self.photo = ImageTk.PhotoImage(self.image)
				self.preview.config(image=self.photo)
			except IOError:
				self.statusbar.set("IOError rendering image")
			
		if self.state != NORMAL:
			self.deiconify()
		self.update_idletasks()
		
class Snatched(Toplevel):
	def __init__(self, parent):
		Toplevel.__init__(self)
		self.parent = parent
		self.snatched = dao.loadSnatched()
		parent.withdraw()
		self.title("My snatched albums")
		
		self.scrollframe = ScrollGridSelect(self, ("Artist", "Album"), (50, 50), 20, [ (snatch.artist, snatch.title) for snatch in self.snatched ])
		backbutton = Button(self, text="Back", command=self.goBackToStart)
		refreshbutton = Button(self, text="Refresh...", command=self.refreshSnatched)
		artbutton = Button(self, text="Download Art...", command=self.downloadArt)
		
		self.scrollframe.grid(row=0, column=0, columnspan=3, sticky="NSEW")
		backbutton.grid(row=1, column=0)
		refreshbutton.grid(row=1, column=1)
		artbutton.grid(row=1, column=2)
		
		self.protocol("WM_DELETE_WINDOW", self.goBackToStart)
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=1)
		
	def goBackToStart(self):
		self.destroy()
		self.parent.deiconify()
		
	def refreshSnatched(self):
		progressbar = RemoteProgress(self)
		progressbar.updateProgress(0)
		snatched = whatcd.snatched(progressbar)
		dao.replaceSnatched(snatched)
		
		progressbar.close()
	
	def downloadArt(self):
		progressbar = RemoteProgress(self)
		progressbar.updateProgress(0)
		preview_geometry = "+%d+%d" % (progressbar.winfo_rootx() + progressbar.winfo_width() + 50, self.parent.winfo_rooty())
		imagepreview = ImagePreview(self, preview_geometry)

		whatcd.downloadSnatchedArt(self.snatched, progressbar, imagepreview)
		
		tkMessageBox.showinfo("Downloaded art", "MediaMonkey library should be refreshed before a repeat run")
		imagepreview.close()
		progressbar.close()
				
				
		
class MissingArt(Toplevel):
	def __init__(self, parent, tuples):
		Toplevel.__init__(self)
		self.parent = parent
		self.tuples = [ (artist, album, mm.fullpath(idfolder)) for artist, album, idfolder in tuples ]
		parent.withdraw()
		self.title("Albums missing artwork")
		
		self.scrollframe = ScrollGridSelect(self, ("Artist", "Album", "Folder"), (30, 30, 40), 20, self.tuples)
		backbutton = Button(self, text="Back", command=self.goBackToStart)
		findbutton = Button(self, text="Find art...", command=self.findArt)
		
		self.scrollframe.grid(row=0, column=0, columnspan=2, sticky="NSEW")
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=1)
		backbutton.grid(row=1, column=0)
		findbutton.grid(row=1, column=1)
		
		self.protocol("WM_DELETE_WINDOW", self.goBackToStart)
		
	def goBackToStart(self):
		self.destroy()
		self.parent.deiconify()

	def findArt(self):
		try:
			if len(self.scrollframe.selected) == 0:
				raise ValueError("Please select something to search for")

			progressbar = RemoteProgress(self)
			progressbar.updateProgress(0)
			preview_geometry = "+%d+%d" % (progressbar.winfo_rootx() + progressbar.winfo_width() + 50, self.parent.winfo_rooty())
			imagepreview = ImagePreview(self, preview_geometry)
		
			whatcd.downloadImages(self.scrollframe.getSelectedData([0, 1, 2]), progressbar, imagepreview)
			#whatcd.fakeDownloadImages(self.scrollframe.getSelectedData([0, 1, 2]), progressbar, imagepreview)

			tkMessageBox.showinfo("Downloaded art", "MediaMonkey library should be refreshed before a repeat run")
			imagepreview.close()
			progressbar.close()
		except ValueError, v:
			tkMessageBox.showwarning("Validation failed", str(v))
	
		
class LocalSearchResults(Toplevel):
	def __init__(self, parent, tuples):
		Toplevel.__init__(self)
		self.parent = parent
		self.parent.withdraw()
		self.title("Local Search Results")

		self.scrollframe = ScrollGridSelect(self, ("Artist", "Album", "Format", "Bitrate"), (25, 25, 6, 10), 20, tuples)
		backbutton = Button(self, text="Back", command=self.goBackToStart)
		replacebutton = Button(self, text="Replace releases...", command=self.replaceReleases)
		
		self.scrollframe.grid(row=0, column=0, columnspan=2, sticky="NSEW")
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=1)
		backbutton.grid(row=1, column=0)
		replacebutton.grid(row=1, column=1)
		
		self.protocol("WM_DELETE_WINDOW", self.goBackToStart)
		
	def goBackToStart(self):
		self.destroy()
		self.parent.deiconify()
		
	def replaceReleases(self):
		try:
			selection = self.scrollframe.getSelectedData([0, 1])
			if len(selection) == 0:
				raise ValueError("Please select something to replace")

			progressbar = RemoteProgress(self)				
			progressbar.updateProgress(0)
		
			# Search for the list of (artist, album) tuples currently selected
			results = whatcd.searchReplacements(self.scrollframe.getSelectedData([0, 1]), progressbar)

			progressbar.close()
			self.withdraw()
			self.remoteresults = RemoteSearchResults(results, self.goBackToLocal)
		except ValueError, v:
			tkMessageBox.showwarning("Validation failed", str(v))
			
	def goBackToLocal(self):
		self.remoteresults.destroy()
		self.deiconify()			
			
class RemoteSearchResults(Toplevel):
	def __init__(self, tuples, breadcrumb):
		Toplevel.__init__(self)

		self.remotetuples = tuples
		self.title("Remote search results")
		
		# Scroller widget frame
		headings = ('Artist', 'Title', 'Year', 'Format', 'Bitrate' \
			, 'Source', 'Scene', 'Edition', 'Freeleech', 'Seeds', 'Size')
		widths = (20, 25, 5, 6, 10, 6, 8, 15, 8, 5, 10)
		displaydata = []
		for album in tuples:
			# The album bean knows all about what editions and formats are available so the sensible thing is to put the clever 
			# scoring in there 
			best = album.bestFormat(config)
			display = (album.artist, album.title, album.year, best.format, best.bitrate \
				, best.edition.medium, best.isscene(), best.edition.strOriginal(), best.isfree(), best.seeds, best.size)
			displaydata.append(display)
		
		# Three frames here
		self.scrollframe = ScrollGridSelect(self, headings, widths, 20, displaydata, self.sumSelectionCost)
		statframe = Frame(self)
		butframe = Frame(self)
		
		self.scrollframe.grid(row=0, column=0, sticky="NSEW")
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=1)		
		statframe.grid(row=1, column=0)
		butframe.grid(row=2, column=0)

		# first column of stats
		l1 = Label(statframe, text="Selected torrents")
		l2 = Label(statframe, text="Total cost")
		l3 = Label(statframe, text="Total freeleech")
		
		self.countentry = Entry(statframe, justify="right")
		self.countentry.insert(END, "0")
		self.countentry.config(state=DISABLED)
		self.costentry = Entry(statframe, justify="right")
		self.costentry.insert(END, "0 MB")
		self.costentry.config(state=DISABLED)
		self.freeentry = Entry(statframe, justify="right")
		self.freeentry.insert(END, "0 MB")
		self.freeentry.config(state=DISABLED)
		
		l1.grid(row=0, column=0, sticky="E")
		self.countentry.grid(row=0, column=1, sticky="W")
		l2.grid(row=1, column=0, sticky="E")
		self.costentry.grid(row=1, column=1, sticky="W")
		l3.grid(row=2, column=0, sticky="E")
		self.freeentry.grid(row=2, column=1, sticky="W")
		
		# second column of stats
		l4 = Label(statframe, text="username")
		l5 = Label(statframe, text="uploaded")
		l6 = Label(statframe, text="downloaded")
		usernameentry = Entry(statframe, justify="right")
		usernameentry.insert(END, config.get("what", "username"))
		usernameentry.config(state=DISABLED)
		uploadentry = Entry(statframe, justify="right")
		uploadentry.insert(END, str(whatcd.getUpload() / 1048576.0) + "MB")
		uploadentry.config(state=DISABLED)
		downloadentry = Entry(statframe, justify="right")
		downloadentry.insert(END, str(whatcd.getDownload() / 1048576.0) + "MB")
		downloadentry.config(state=DISABLED)
		
		l4.grid(row=0, column=2, sticky="E")
		usernameentry.grid(row=0, column=3, sticky="W")
		l5.grid(row=1, column=2, sticky="E")
		uploadentry.grid(row=1, column=3, sticky="W")
		l6.grid(row=2, column=2, sticky="E")
		downloadentry.grid(row=2, column=3, sticky="W")

		# And a third column of stats
		l7 = Label(statframe, text="current ratio")
		l8 = Label(statframe, text="projected ratio")
		currententry = Entry(statframe, justify="right")
		currententry.insert(END, str(whatcd.getRatio()))
		currententry.config(state=DISABLED)
		self.projectedentry = Entry(statframe, justify="right")
		self.projectedentry.insert(END, str(whatcd.getRatio()))
		self.projectedentry.config(state=DISABLED)		
		
		l7.grid(row=0, column=4, sticky="E")
		currententry.grid(row=0, column=5, sticky="W")
		l8.grid(row=1, column=4, sticky="E")
		self.projectedentry.grid(row=1, column=5, sticky="W")

		# Button frame
		backbutton = Button(butframe, text="Back", command=breadcrumb)
		grabbutton = Button(butframe, text="Grab torrents", command=self.grabTorrents)
		savebutton = Button(butframe, text="Save search results", command=self.saveRemoteSearch)
		
		backbutton.grid(row=0, column=0)
		grabbutton.grid(row=0, column=1)
		savebutton.grid(row=0, column=2)

		# Window globals
		self.protocol("WM_DELETE_WINDOW", breadcrumb)

	def saveRemoteSearch(self):
		savefilename = tkFileDialog.asksaveasfilename(parent=self)
		if savefilename:
			savefile = open(savefilename, "wb")
			pickle.dump(self.remotetuples, savefile, -1)
			savefile.close()

	def grabTorrents(self):
			progressbar = RemoteProgress(self)				
			progressbar.updateProgress(0)
		
			# iterate over the list of albums to download
			albums = [ self.remotetuples[int(i)] for i in self.scrollframe.selected ]
			for i in range(len(albums)):
				progressbar.message("Downloading torrent for %s: %s" % (albums[i].artist, albums[i].title))
				albums[i].bestFormat(config).downloadTorrent(albums[i])
				progressbar.updateProgress(float(i + 1) / float(len(albums)))
				# TODO: bring the data in scope.  simply cannot be bothered!
				progressbar.message("Sleeping for 2 seconds to be polite")
				time.sleep(2)

			progressbar.close()

	def sumSelectionCost(self, selected):
		totalbytes = 0
		totalfreebytes = 0
		for i in selected:
			best = self.remotetuples[int(i)].bestFormat(config)
			if best.freeleech:
				totalfreebytes = totalfreebytes + best.bytes()
			else:
				totalbytes = totalbytes + best.bytes()
			
		self.countentry.config(state=NORMAL)
		self.costentry.config(state=NORMAL)
		self.freeentry.config(state=NORMAL)
		self.projectedentry.config(state=NORMAL)
		
		self.countentry.delete(0, END)
		self.costentry.delete(0, END)
		self.freeentry.delete(0, END)
		self.projectedentry.delete(0, END)

		self.countentry.insert(END, str(len(selected)))
		self.costentry.insert(END, str(totalbytes / 1048576.0) + " MB")
		self.freeentry.insert(END, str(totalfreebytes / 1048576.0) + " MB")
		self.projectedentry.insert(END, "%.2f" % (whatcd.getUpload() / (whatcd.getDownload() + float(totalbytes)),))
		
		self.countentry.config(state=DISABLED)
		self.costentry.config(state=DISABLED)
		self.freeentry.config(state=DISABLED)
		self.projectedentry.config(state=DISABLED)
		
class OptionsDialog(Toplevel):
	def __init__(self, parent):
		Toplevel.__init__(self)
		self.parent = parent
		self.transient(parent)
		self.title("Edit options")
		
		# Rather than having a single grid, have four Frames - one for each optionset 
		# and one for the buttons
		mmframe = Frame(self)
		credframe = Frame(self)
		self.rankingselector = RankingSelector(self, config.loadRankings())
		butframe = Frame(self)
		
		mmframe.grid(row=0, column=0, padx=5, pady=5)
		credframe.grid(row=1, column=0, padx=5, pady=5)
		self.rankingselector.grid(row=2, column=0, padx=5, pady=5)
		butframe.grid(row=3, column=0, padx=5, pady=5)
		
		# MediaMonkey options frame
		l1 = Label(mmframe, text="MediaMonkey DB file")
		self.dbfentry = Entry(mmframe, justify="left", width=60, exportselection=False)
		self.dbfentry.insert(END, config.get("mediamonkey", "dbfile"))
		self.dbfentry.config(state=DISABLED)
		choosebutton = Button(mmframe, text="Select file", command=self.opendbfile)

		l1.grid(row=0, column=0, sticky=W)
		self.dbfentry.grid(row=1, column=0)
		choosebutton.grid(row=1, column=1)

		# Credentials frame
		l2 = Label(credframe, text="what.cd username")
		l3 = Label(credframe, text="what.cd password")
		self.userentry = Entry(credframe, exportselection=False)
		self.userentry.insert(END, config.get("what", "username"))
		self.passentry = Entry(credframe, show="*", exportselection=False)
		self.passentry.insert(END, config.get("what", "password"))
		testcredbutton = Button(credframe, text="Test credentials", command=self.testcred)

		l2.grid(row=0, column=0)
		self.userentry.grid(row=0, column=1)
		l3.grid(row=1, column=0)
		self.passentry.grid(row=1, column=1)
		testcredbutton.grid(row=0, column=2)
				
		# Button frame
		okbutton = Button(butframe, text="OK", command=self.ok)
		cancelbutton = Button(butframe, text="Cancel", command=self.cancel)

		okbutton.grid(row=0, column=0)
		cancelbutton.grid(row=0, column=1)
		
		# Dialog global binds and geometry
		self.protocol("WM_DELETE_WINDOW", self.cancel)
		self.geometry("+%d+%d" % (self.parent.winfo_rootx()+50,self.parent.winfo_rooty()+50))
		self.wait_window(self)
		
	def testcred(self):
		# This is going to the config file immediately as it permanently changes the app's state
		config.set("what", "username", self.userentry.get())
		config.set("what", "password", self.passentry.get())
		config.write(open("whatbot.cfg", "w"))
		if whatcd.login():
			tkMessageBox.showinfo("Login successful", "Now logged into what as %s\nUp: %.0fMB\nDown: %.0fMB\nRatio: %.2f" \
				% (self.userentry.get(), whatcd.getUpload() / 1048576.0, whatcd.getDownload() / 1048576.0, float(whatcd.getRatio())))
			return True
		else:
			tkMessageBox.showwarning("Login failed", "Unable to log into what, please check credentials")
			return False
		
	def opendbfile(self):
		newdbfile = tkFileDialog.askopenfilename(parent=self.parent)
		if newdbfile:
			if mm.testConnection(newdbfile):
				self.dbfentry.config(state=NORMAL)
				self.dbfentry.delete(0, END)
				self.dbfentry.insert(END, newdbfile)
				self.dbfentry.config(state=DISABLED)
			else:
				tkMessageBox.showwarning("Validation failed", "Cannot open file, may not be a MediaMonkey DB?")

	def cancel(self):
		self.parent.focus_set()
		self.destroy()
	
	def ok(self):
		# Log into what if necessary
		if self.userentry.get() != config.get("what", "username") or self.passentry.get() != config.get("what", "password"):
			if not self.testcred():
				# Drop out of the handler immediately without closing the dialog
				return False
			
		# Set MediaMonkey options
		config.set("mediamonkey", "dbfile", self.dbfentry.get())
		mm.connect(self.dbfentry.get())
		
		# Set format rankings
		config.saveRankings(self.rankingselector.items)

		# Save config file
		config.write(open("whatbot.cfg", "w"))
		
		self.parent.focus_set()
		self.destroy()

class StatusBar(Frame):
	def __init__(self, master):
		Frame.__init__(self, master)
		self.label = Label(self, bd=1, relief=SUNKEN, anchor=W)
		self.label.pack(fill=X)

	def set(self, format, *args):
		self.label.config(text=format % args)
		self.label.update_idletasks()

	def clear(self):
		self.label.config(text="")
		self.label.update_idletasks()
		
if __name__ == "__main__":
	# Create and initialise singletons
	config = WhatConfigParser()
	config.read('whatbot.cfg')
	mm = mediamonkey.MediaMonkey(config)
	whatcd = what.WhatCD(config, mm)
	dao = whatdao.WhatDAO()

	# Create and start GUI
	gui = WhatBotGui()
	gui.mainloop()
