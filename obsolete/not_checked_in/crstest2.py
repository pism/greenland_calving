import cartopy
from uafgi import cartopyutil
import pyproj.crs

map_crs = cartopy.crs.epsg(3413)
print('----------------')
print(map_crs.proj4_init)
map_crs = cartopyutil.crs(3413)
print('----------------')
print(map_crs.proj4_init)

print(cartopy.crs.NorthPolarStereo().proj4_init)

print('==================================================')
with netCDF4.Dataset('jj2020.nc') as nc:
    wkt = nc.variables['crs'].spatial_ref
map_crs = cartopyutil.crs(wkt)
print(map_crs.proj4_init)

#pp_crs = pyproj.crs.CRS.from_epsg(3413)
#print(type(pp_crs))
#print('---------------------------------')
#print(pp_crs.srs)
#print('---------------------------------')
#print(pp_crs.name)
#print('---------------------------------')
#print(pp_crs.type_name)
#print('---------------------------------')
#print(pp_crs.to_dict())
#print('---------------------------------')
#print(pp_crs.to_proj4())
#print('---------------------------------')
#print(pp_crs.to_wkt())
#
#
#
##print(type(map_crs))
##print(map_crs)
#
