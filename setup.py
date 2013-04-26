from distutils.core import setup
import py2exe, sys, os

sys.argv.append('py2exe')

setup(windows=['whatbot.py'])