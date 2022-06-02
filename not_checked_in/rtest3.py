from uafgi import cdoutil,shputil,ioutil,jsonutil,gdalutil
import subprocess
import netCDF4
from osgeo import ogr,gdal
import numpy as np

shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Isbrae_closed_v1.0.shp'
#gridfile = 'outputs/W71.65N-grid.nc'
gridfile = 'z.nc'
polyfile = 'troughs/Rink-Isbrae.geojson'

with ioutil.TmpDir('.') as tdir:
    poly_ds = ogr.GetDriverByName('GeoJSON').Open(polyfile)
    ras = gdalutil.rasterize_polygons(poly_ds, gridfile)
    print(np.sum(np.sum(ras)))
    print(ras.shape[0]*ras.shape[1])

#    jsonutil.rasterize_polygon(polyfile, gridfile, tdir)
#    jsonutil.load_layer(polyfile, gridfile)

#    for polygon_feature in jsonutil.iter_features('troughs/Rink-Isbrae.geojson'):
#        print(polygon_feature)


#    for poly in shputil.rasterize_polygons(shapefile, range(0,10), gridfile, tdir):
#        print(np.sum(np.sum(poly)))

