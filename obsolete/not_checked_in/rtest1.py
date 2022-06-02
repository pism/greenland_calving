from uafgi import cdoutil
import subprocess
import netCDF4
from osgeo import ogr,gdal
import numpy as np

#shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Gletsjer_closed_v1.0.shp'
#shapefile = 'retreated_advret.shp'
#shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Gletsjer_closed_v1.0.shp'
shapefile = 'oneshape.shp'
gridfile = 'outputs/W71.65N-grid.nc'

fb = cdoutil.FileBounds(gridfile)
print('xx ',fb.x0,fb.x1,fb.y0,fb.y1)
print('dxy', fb.dx, fb.dy)


with netCDF4.Dataset(gridfile) as nc:
    sgeotransform = nc.variables['polar_stereographic'].GeoTransform
print('geotransform "{}"'.format(sgeotransform))
geotransform = tuple(float(x) for x in sgeotransform.split(' ') if len(x) > 0)




maskvalue = 1

src_ds = ogr.Open(shapefile)
src_lyr=src_ds.GetLayer()   # Put layer number or name in her

dst_ds = gdal.GetDriverByName('MEM').Create('', int(fb.nx), int(fb.ny), 1 ,gdal.GDT_Byte)
#dst_ds = gdal.GetDriverByName('netCDF').Create('x.nc', fb.nx, fb.ny, 1 ,gdal.GDT_Byte)
dst_rb = dst_ds.GetRasterBand(1)
dst_rb.Fill(0) #initialise raster with zeros
dst_rb.SetNoDataValue(0)
dst_ds.SetGeoTransform(geotransform)

err = gdal.RasterizeLayer(dst_ds, [1], src_lyr, burn_values=[maskvalue])
print('err ',err)

dst_ds.FlushCache()

mask_arr=dst_ds.GetRasterBand(1).ReadAsArray()

print(np.sum(np.sum(mask_arr)))
print(mask_arr.shape)





#layer_name = 'termini_1972-2019_Rink-Gletsjer_closed_v1.0'
#
## Do it
#cmd = [str(x) for x in ['gdal_rasterize', '-add', '-burn', '1',
#    '-a_srs', fb.crs,
#    '-te', fb.x0,fb.y0,fb.x1,fb.y1,
#    '-tr', fb.dx, fb.dy,
#    '-l', layer_name,
#    shapefile, 'y.nc']]
#print(cmd)
#subprocess.run(cmd, check=True)
