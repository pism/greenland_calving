import sys
import numpy as np
import netCDF4
import geojson
import json
import pyproj

# Removes ice from downstream of a calving front.

trace_file = 'Amaral_TerminusTraces/TemporalSet/Jakobshavn/Jakobshavn10_2015-08-01_2015-08-23.geojson.json'
velocity_file = 'outputs/TSX_W69.10N_2008_2020_pism_filled.nc'

def iter_features(trace_files):
    for trace_file in trace_files:
        # https://stackoverflow.com/questions/42753745/how-can-i-parse-geojson-with-python
        with open(trace_file) as fin:
            gj = json.load(fin)

            assert gj['type'] == 'FeatureCollection'

            for ls in gj['features']:
                yield ls


# Get projection
# https://pyproj4.github.io/pyproj/dev/examples.html

with netCDF4.Dataset(velocity_file) as nc:
    wks_s = nc.variables['polar_stereographic'].spatial_ref
map_crs = pyproj.CRS.from_string(wks_s)

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

line_lonlat = [[-49.53145799513044,69.13045757980224],
[-49.53308877821149,69.12895928288714]]
line_xy0 = proj.transform(
    np.array([x[0] for x in line_lonlat]),
    np.array([x[1] for x in line_lonlat]))

line_xy = [(line_xy0[0][i], line_xy0[1][i]) for i in range(len(line_xy0[0]))]




print(line_xy)

sys.exit(0)

trans = pyproj.transformer.Transformer()

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


