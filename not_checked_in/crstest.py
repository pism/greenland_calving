What I learned:

1. Use the following Stereographic constructor for EPSG:3413:
    map_crs = cartopy.crs.Stereographic(
        central_latitude=90,
        central_longitude=-45,
        false_easting=0, false_northing=0,
        true_scale_latitude=70, globe=None)
   ... or just use the simpler class MyStereo.

2. in set_extent(), crs must be map_crs (the SOURCE crs of the extent specified).






import netCDF4
import cartopy.crs
# https://geohackweek.github.io/visualization/03-cartopy/
import cartopy.crs as ccrs                   # import projections
import cartopy.crs
import cartopy.feature as cf                 # import features
import pyproj.crs
from uafgi import gdalutil
import uafgi.data
from cartopy.io import shapereader
import cartopy._epsg
import matplotlib.pyplot as plt
import sys
import numpy as np
from cartopy._crs import (CRS, Geodetic, Globe, PROJ4_VERSION,
                          WGS84_SEMIMAJOR_AXIS, WGS84_SEMIMINOR_AXIS)
import shapely.geometry as sgeom




def _ellipse_boundary(semimajor=2, semiminor=1, easting=0, northing=0, n=201):
    """
    Define a projection boundary using an ellipse.

    This type of boundary is used by several projections.

    """

    t = np.linspace(0, -2 * np.pi, n)  # Clockwise boundary.
    coords = np.vstack([semimajor * np.cos(t), semiminor * np.sin(t)])
    coords += ([easting], [northing])
    return coords


class MyStereo(cartopy.crs.Projection):
    def __init__(self, proj4_params, globe=None):
        super(MyStereo, self).__init__(proj4_params, globe=globe)

        # TODO: Get these out of proj4_params
        false_easting = 0
        false_northing = 0

        # TODO: Let the globe return the semimajor axis always.
        a = np.float(self.globe.semimajor_axis or WGS84_SEMIMAJOR_AXIS)
        b = np.float(self.globe.semiminor_axis or WGS84_SEMIMINOR_AXIS)

        # Note: The magic number has been picked to maintain consistent
        # behaviour with a wgs84 globe. There is no guarantee that the scaling
        # should even be linear.
        x_axis_offset = 5e7 / WGS84_SEMIMAJOR_AXIS
        y_axis_offset = 5e7 / WGS84_SEMIMINOR_AXIS
        self._x_limits = (-a * x_axis_offset + false_easting,
                          a * x_axis_offset + false_easting)
        self._y_limits = (-b * y_axis_offset + false_northing,
                          b * y_axis_offset + false_northing)
        coords = _ellipse_boundary(self._x_limits[1], self._y_limits[1],
                                   false_easting, false_northing, 91)
        self._boundary = sgeom.LinearRing(coords.T)
        self._threshold = np.diff(self._x_limits)[0] * 1e-3

    @property
    def boundary(self):
        return self._boundary

    @property
    def threshold(self):
        return self._threshold

    @property
    def x_limits(self):
        return self._x_limits

    @property
    def y_limits(self):
        return self._y_limits









class _SubProj(cartopy._epsg._EPSGProjection):
    # https://stackoverflow.com/questions/54569028/ignore-projection-limits-when-setting-the-extent
    @property
    def y_limits(self):
        return (-5e9,5e9)
    @property
    def bounds(self):
        return (-5e9,5e9, -5e9,5e9)


map_crs = cartopy.crs.epsg(3413)
# https://stackoverflow.com/questions/31590152/monkey-patching-a-property
#map_crs.__class__ = _SubProj
#map_crs


globe_terms = [['datum', 'WGS84']]
other_terms = [['proj', 'stere'], ['lat_0', '90'], ['lat_ts', '70'], ['lon_0', '-45'], ['k', '1'], ['x_0', '0'], ['y_0', '0'], ['units', 'm'], ['no_defs', None]]

_GLOBE_PARAMS = {'datum': 'datum',
                 'ellps': 'ellipse',
                 'a': 'semimajor_axis',
                 'b': 'semiminor_axis',
                 'f': 'flattening',
                 'rf': 'inverse_flattening',
                 'towgs84': 'towgs84',
                 'nadgrids': 'nadgrids'}

globe = ccrs.Globe(**{_GLOBE_PARAMS[name]: value for name, value in
                              globe_terms})
# Setting glob here was messing it up
map_crs = MyStereo(other_terms, globe=None)


grid = 'W69.95N'
grid_file = uafgi.data.measures_grid_file(grid)
with netCDF4.Dataset(grid_file) as nc:
    ps = nc.variables['polar_stereographic']
    map_crs = cartopy.crs.Stereographic(
        central_latitude=90,
        central_longitude=-45,
        false_easting=0, false_northing=0,
        true_scale_latitude=70, globe=globe)

# ---------------------------


ll_crs = ccrs.PlateCarree()

p4str = '+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs '
ps = pyproj.CRS(p4str)
pl = pyproj.CRS.from_proj4("+proj=latlon")
ptrans = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:3413')

for lon,lat in [(-50.,70.)]:
    print()
    print(ptrans.transform(lat,lon))
    print(map_crs.transform_point(lon,lat,ll_crs))
print()
#print(map_crs.boundary)
#print(ll_crs.bounds



ax = plt.axes(projection = map_crs)  # create a set of axes with Mercator projection
extents = [-218150.0, -163150.0, -2149950.0, -2218150.0]
ax.set_extent(extents=extents, crs=map_crs)
#ax.set_extent(extents=[-218150.0, -163150.0, 20,50])

sys.exit(0)
# ---------------------------


# https://pyproj4.github.io/pyproj/stable/crs_compatibility.html
#map_wkt = uafgi.data.wkt.nsidc_ps_north

#map_crs = cartopy.crs.epsg(3413)
#map_crs.bounds = (-50000000.0, 50000000.0, -50000000.0, 50000000.0)
print(map_crs.x_limits)
ll_crs = ccrs.PlateCarree()


grid = 'W69.95N'
grid_file = uafgi.data.measures_grid_file(grid)

#with netCDF4.Dataset(grid_file) as nc:
#    ps = nc.variables['polar_stereographic']
#
#    #crs = ccrs.NorthPolarStereo(central_longitude=-45.)
#    crs = cartopy.crs.Stereographic(
#        central_latitude=ps.latitude_of_projection_origin,
#        #central_latitude=ps.standard_parallel,
#        central_longitude=ps.straight_vertical_longitude_from_pole,
#        false_easting=ps.false_easting, false_northing=ps.false_northing,
#        true_scale_latitude=None, globe=None)
#
## https://nsidc.org/data/polar-stereo/ps_grids.html    
#crs = cartopy.crs.epsg(3413)
    
gs = gdalutil.FileInfo(grid_file)
print(gs.geotransform)


geoTransform = gs.geotransform
x0 = geoTransform[0]
x1 = x0 + geoTransform[1] * gs.nx

y0 = geoTransform[3]
y1 = y0 + geoTransform[5] * gs.ny

# W68.60N_grid
#GeoTransform = GT = [-235050, 100, 0, -2290050, 0, -100]
#nx=730xn
#ny=760


fjord_outlines = '/Users/eafischer2/data_sets/velocities_data/fj/fjord_outlines.shp'

# Read shape file
#wgs84_crs = cartopy.crs.epsg(4326)     # Coord system of THIS shapefile
# https://scitools.org.uk/cartopy/docs/v0.8/crs/index.html
#wgs84_crs = cartopy.crs.Geodetic()
reader = shapereader.Reader(fjord_outlines)
## Filter for a specific country
fjords = [x.geometry for x in reader.records()]
print(fjords[1])
shape_feature = cf.ShapelyFeature(fjords, ll_crs, facecolor="lime", edgecolor='black', lw=1)

#mypoint = shapely.geometry.Point(-55,70.)
#print(mypoint)
#shape_feature = cf.ShapelyFeature([mypoint], ccrs.PlateCarree(), facecolor="lime", edgecolor='black', lw=1)



ax = plt.axes(projection = map_crs)  # create a set of axes with Mercator projection




# Set the extent (x0, x1, y0, y1) of the map in the given coordinate system.
extents = [x0,x1,y0,y1]
print('extents: {}'.format(extents))
#extents[3] = -2280000
print(extents)
#extents = (x0-1e6,x0+1e6,y0,0)      # Much of Greenland
ax.set_extent(extents=extents)


import sys
sys.exit(0)


#ax.tissot(lats=range(43, 51), lons=range(-124, -116), alpha=0.4, rad_km=20000, color='orange')
ax.add_feature(shape_feature)
#ax.add_feature(cf.COASTLINE)                 # plot some data on them
ax.coastlines(resolution='50m')

#ax.stock_img()

# https://scitools.org.uk/cartopy/docs/latest/matplotlib/gridliner.html
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

# Here's plotting raseter data...
# https://scitools.org.uk/cartopy/docs/v0.16/tutorials/understanding_transform.html

ax.scatter([-55],[75], color='blue',s=20,transform=ll_crs)

ax.set_title("Title")                        # label it
plt.show()
