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
import shapefile
import re
from osgeo import gdal

strip_file = 'xx/SETSM_WV01_20130218_1020010020394400_1020010020602500_seg1_2m_v3.0_dem.tif'
dim_file = 'outputs/TSX_W71.65N_2008_2020_pism.nc'    # Any old file with the x and y variables showing the bounds


# Get bounding box
with netCDF4.Dataset(dim_file) as nc:
    xx = nc.variables['x'][:]
    dx = xx[1]-xx[0]
    half_dx = .5 * dx
    x0 = round(xx[0] - half_dx)
    x1 = round(xx[-1] + half_dx)

    yy = nc.variables['y'][:]
    dy = yy[1]-yy[0]
    half_dy = .5 * dy
    y0 = round(yy[0] - half_dy)
    y1 = round(yy[-1] + half_dy)


cmd = ['gdal_translate',
    '-r', 'average',
    '-projwin', str(x0), str(y1), str(x1), str(y0),
    '-tr', str(dx), str(dy),
    strip_file,
    'x2.nc']
subprocess.run(cmd, check=True)
