import sys
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

# Removes ice from downstream of a calving front.

trace_file = 'Amaral_TerminusTraces/TemporalSet/Jakobshavn/Jakobshavn10_2015-08-01_2015-08-23.geojson.json'
velocity_file = 'outputs/TSX_W69.10N_2008_2020_pism_filled.nc'
bedmachine_file = 'outputs/BedMachineGreenland-2017-09-20_pism_W69.10N.nc'

def iter_features(trace_files):
    for trace_file in trace_files:
        # https://stackoverflow.com/questions/42753745/how-can-i-parse-geojson-with-python
        with open(trace_file) as fin:
            gj = json.load(fin)

            assert gj['type'] == 'FeatureCollection'

            for ls in gj['features']:
                yield ls


# --------------------------------------------------------------------
# Get projection
# https://pyproj4.github.io/pyproj/dev/examples.html

with netCDF4.Dataset(velocity_file) as nc:
    wks_s = nc.variables['polar_stereographic'].spatial_ref
    bounding_xx = nc.variables['x'][:]
    bounding_yy = nc.variables['y'][:]

with netCDF4.Dataset(bedmachine_file) as nc:
    thk = nc.variables['thickness'][:]

map_crs = pyproj.CRS.from_string(wks_s)
with open('crs.wkt', 'w') as fout:
    fout.write(wks_s)


# Standard GeoJSON Coordinate Reference System (CRS)
# Same as epsg:4326, but the urn: string is preferred
# http://wiki.geojson.org/Rethinking_CRS
# This CRS is lat/lon, whereas GeoJSON is lon/lat.  Use always_xy to fix that (below)
geojson_crs = pyproj.CRS.from_string('urn:ogc:def:crs:OGC::CRS84')
# geojson_crs = pyproj.CRS.from_epsg(4326)
# print(geojson_crs.to_proj4())

# https://pyproj4.github.io/pyproj/dev/examples.html
# Note that crs_4326 has the latitude (north) axis first

# Converts from geojson_crs to map_crs
# See for always_xy: https://proj.org/faq.html#why-is-the-axis-ordering-in-proj-not-consistent
proj = pyproj.Transformer.from_crs(geojson_crs, map_crs, always_xy=True)

# -------------------------------------------------------
# Convert grounding line from (lon,lat) to (x,y)

#gline_lonlat = [[-49.53145799513044,69.13045757980224],[-49.53308877821149,69.12895928288714]]

feature = next(iter_features((trace_file,)))
gline_lonlat = feature['geometry']['coordinates']


gline_xx,gline_yy = proj.transform(
    np.array([x[0] for x in gline_lonlat]),
    np.array([x[1] for x in gline_lonlat]))

print('grounding line: ', gline_xx, gline_yy)

gline = shapely.geometry.LineString([
    (gline_xx[i], gline_yy[i]) for i in range(len(gline_xx))])

# --------------------------------------------------------------------
# Get least squares fit through the points
slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(gline_xx,gline_yy)

# Determine Polygon of bounding box (xy coordinates; cell centers is OK)
bb = (
    (bounding_xx[0],bounding_yy[0]), (bounding_xx[-1],bounding_yy[0]),
    (bounding_xx[-1],bounding_yy[-1]), (bounding_xx[0],bounding_yy[-1]))
bounding_box = shapely.geometry.Polygon(bb)

dx = bounding_xx[-1] - bounding_xx[0]
dy = bounding_yy[-1] - bounding_yy[0]

x0 = 2*bounding_xx[0] - bounding_xx[-1]    # x0-dx
x1 = 2*bounding_xx[-1] - bounding_xx[0]    # x1+dx

regline = shapely.geometry.LineString((
    (x0, slope*x0 + intercept),
    (x1, slope*x1 + intercept)))

#regline = shapely.geometry.LineString(((0.,intercept), (1.,intercept+slope)))


print('area ',bounding_box.area)
print('bounds ',bounding_box.bounds)
print('regline ',regline)
#print(' ',bounding_box.)
#print(' ',bounding_box.)
#print(' ',bounding_box.)
#print(' ',bounding_box.)


#print(bb)
#print(bounding_box)
#print(shapely.geometry.polygon.orient(bounding_box,-1))

# -------------- Intersect bounding box and lsqr fit to terminus
intersection = bounding_box.intersection(regline)
print('intersection ',list(intersection.coords))
print(intersection.wkt)

# -------------- Extend gline LineString with our intersection points
intersection_ep = intersection.boundary
gline_ep = gline.boundary
# Make sure intersection[0] is closets to gline[0]
if intersection_ep[0].distance(gline_ep[0]) > intersection_ep[0].distance(gline_ep[1]):
    intersection_ep = (intersection_ep[1],intersection_ep[0])

# Extend gline
#print(list(intersection_ep[0].coords))
print(intersection_ep[0].coords[0])
glinex = shapely.geometry.LineString(
    [intersection_ep[0].coords[0]] + list(gline.coords) + [intersection_ep[1].coords[0]])

# Split our bounding_box polygon based on glinex
# https://gis.stackexchange.com/questions/232771/splitting-polygon-by-linestring-in-geodjango
merged = shapely.ops.linemerge([bounding_box.boundary, glinex])
borders = shapely.ops.unary_union(merged)
polygons = list(shapely.ops.polygonize(borders))

# Write out the two polygons as WKB
# https://readthedocs.org/projects/shapely/downloads/pdf/latest/
#with open('crs.wkt', 'w') as fout:
#    fout.write(shapely.wkt.dumps(map_crs))

for i,poly in enumerate(polygons):
    with open('poly{}.wkt'.format(i), 'w') as fout:
        fout.write('wkt\n')
        fout.write(shapely.wkt.dumps(poly))
        fout.write('\n')


# https://gis.stackexchange.com/questions/52705/how-to-write-shapely-geometries-to-shapefiles
print('yyyyyyyyyyy')
for i,poly in enumerate(polygons):
    print('xxxxxxxxxxxxxx ',i)

    # Now convert it to a shapefile with OGR    
    driver = ogr.GetDriverByName('Esri Shapefile')
    ds = driver.CreateDataSource('poly{}.shp'.format(i))
    layer = ds.CreateLayer('', None, ogr.wkbPolygon)

    # Add one attribute
    layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
    defn = layer.GetLayerDefn()

    ## If there are multiple geometries, put the "for" loop here

    # Create a new feature (attribute and geometry)
    feat = ogr.Feature(defn)
    feat.SetField('id', 123)

    # Make a geometry, from Shapely object
    geom = ogr.CreateGeometryFromWkb(poly.wkb)
    feat.SetGeometry(geom)

    layer.CreateFeature(feat)
    feat = geom = None  # destroy these

    # Save and close everything
    ds = layer = feat = geom = None



# Make masks out of both polygons (masks that will cover the entire space

sys.exit(0)

#print(gline_xy)

for feature in iter_features((trace_file,)):
    # ['geometry', 'id', 'properties', 'type']
    assert feature['geometry']['type'] == 'LineString'
    points = feature['geometry']['coordinates']
    print(points)



#        print(type(feature),feature['type'],list(feature.keys()))
#    #    print(feature['geometry'])
#        print(feature['id'])
#        print(feature['properties'])
#        print(feature['type'])


