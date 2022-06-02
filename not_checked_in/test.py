import pandas as pd
import importlib
import csv,os
import numpy as np
import pandas as pd
import itertools
from uafgi import ioutil,shputil,greenland
import pyproj
import shapely
import copy
from uafgi import gicollections

def main():
    fj = greenland.read_fj(greenland.map_wkt)
    ns642 = greenland.read_ns642(greenland.map_wkt)
    ns642x = greenland.ns642_by_glacier_id(ns642)
    match = greenland.match_point_poly(ns642x, 'ns642_points', fj, 'fj_poly')
    print(match.df)

main()


