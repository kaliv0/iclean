import os
import urllib.parse
from os import scandir
from os import path as osp

from bar import (
    func,
    munc,
    Fizz,
)

from dataclasses import dataclass
import logging
from pprint import pprint as pp

# from hack import skunk, trunk
# from difflib import *


@dataclass
class Buzz(Fizz):
    pass


if __name__ == "__main__":
    print("bar")
    pp({"john": "doe"})
    # urllib.parse.urlencode({"fizz": "buzz"})
    logging.warning("func")
    munc()
