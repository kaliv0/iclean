import urllib.parse
import os
from dataclasses import dataclass
from os import scandir

# from bar import munc, func

from bar import func, munc
import logging

# from hack import skunk, trunk

# from difflib import *
from pprint import pprint as pp
from os import path as osp

from resources.hack import Fizz


@dataclass
class Buzz(Fizz):
    pass


if __name__ == "__main__":
    print("bar")
    pp({"john": "doe"})
    # urllib.parse.urlencode({"fizz": "buzz"})
    logging.warning("func")
    munc()
