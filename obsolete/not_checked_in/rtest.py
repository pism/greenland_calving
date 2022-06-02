from uafgi import cdoutil
import subprocess


#shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Gletsjer_closed_v1.0.shp'
#shapefile = 'retreated_advret.shp'
#shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Gletsjer_closed_v1.0.shp'
shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Isbrae_closed_v1.0.shp'
gridfile = 'outputs/W71.65N-grid.nc'

shapefile1 = 'oneshape.shp'
cmd = [str(x) for x in ('ogr2ogr', shapefile1, shapefile, '-fid', 1)]
subprocess.run(cmd, check=True)


fb = cdoutil.FileBounds(gridfile)
print('xx ',fb.x0,fb.x1,fb.y0,fb.y1)
print('dxy', fb.dx, fb.dy)


layer_name = 'termini_1972-2019_Rink-Gletsjer_closed_v1.0'

# Do it
cmd = [str(x) for x in ['gdal_rasterize',
    '-a_srs', fb.crs,
    '-te', fb.x0,fb.y0,fb.x1,fb.y1,
    '-tr', fb.dx, fb.dy,
#    '-l', layer_name,
    '-burn', '1',
    shapefile1, 'y.nc']]
print(cmd)
subprocess.run(cmd, check=True)

# Just use gdal_cut...


# ========================================
#                terminus_raster = os.path.join(tdir, 'terminus_raster.nc')
#                 cmd = ['gdal_rasterize', 
#                     '-a_srs', ext.wks_s,
#                     '-tr', str(ext.dx), str(ext.dy),
#                     '-te', str(ext.x0), str(ext.y0), str(ext.x1), str(ext.y1),
#                     '-burn', '1', one_terminus, terminus_raster]
#                 print(' '.join(cmd))
#                 subprocess.run(cmd, check=True)
#                 with netCDF4.Dataset(terminus_raster) as nc:
#                     terminus_d = nc.variables['Band1'][:]
#                 # Change fill value to 0
#                 terminus_d.data[terminus_d.mask] = 0
#                 # Throw away the mask
#                 terminus_d = terminus_d.data
# 
