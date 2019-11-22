"""
Following code is used to add integration test dirs into PATH
"""
from os.path import join, realpath
import sys


sys.path.insert(0, realpath(join(__file__, "../../../")))
