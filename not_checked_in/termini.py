from uafgi import geoutil
import datetime

# --------- Questionable imports
from uafgi import make,glaciers,flowfill
import sys,os,subprocess
import numpy as np
import netCDF4
import geojson
import json
import pyproj
#import scipy
import scipy.stats
#import shapely
import shapely.geometry
from osgeo import ogr
import shapely.ops
import shapely.wkt, shapely.wkb
from uafgi import ioutil,ncutil
import re
from osgeo import gdal,gdalconst
from uafgi.nsidc import nsidc0481
from uafgi import nsidc
import io,shutil


def fix_shapes(fname):
    for shape,attrs in geoutil.read_shapes(fname):
        attrs['Date'] = datetime.datetime.strptime(attrs['Date'], '%Y-%m-%d').date()
        yield shape,attrs


def main0():
    """Rifle through a terminus file"""
    termini_file = 'data/calfin/domain-termini/termini_1972-2019_Rink-Isbrae_v1.0.shp'
    for shape,attrs in fix_shapes(termini_file):
        print(attrs)

main0()
