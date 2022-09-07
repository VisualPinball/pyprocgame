__all__ = [
	'config',
	'dmd',
	'events',
	'alphanumeric',
	'auxport',
	'game',
	'highscore',
	'lamps',
	'modes',
	'service',
	'sound',
	'util',
	'tools',
	]
from config import *
from dmd import *
from events import *
from alphanumeric import *
from auxport import *
from game import *
from highscore import *
from lamps import *
from modes import *
from service import *
from sound import *
from util import *
from tools import *

from _version import __version_info__
__version__ = '.'.join(map(str, __version_info__))

def check_version(version):
	"""Returns true if the version of pyprocgame is greater than or equal to the supplied version tuple."""
	vi = __version_info__
	for n in version:
		if vi[0] > n:
			return True
		if vi[0] < n:
			return False
		vi = vi[1:]
	return True
