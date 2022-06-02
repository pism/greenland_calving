from uafgi import cdoutil,shputil,ioutil
import subprocess
import netCDF4
from osgeo import ogr,gdal
import numpy as np

shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Isbrae_closed_v1.0.shp'
gridfile = 'outputs/W71.65N-grid.nc'


with ioutil.TmpDir('.') as tdir:
    for poly in shputil.rasterize_polygons(shapefile, range(0,10), gridfile, tdir):
        print(np.sum(np.sum(poly)))

