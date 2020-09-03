import bisect
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
import datetime

trace_file = 'Amaral_TerminusTraces/TemporalSet/Jakobshavn/Jakobshavn10_2015-08-01_2015-08-23.geojson.json'

velocity_file = 'outputs/TSX_W69.10N_2008_2020_pism_filled.nc'

def iter_features(trace_files):
    for trace_file in trace_files:
        # https://stackoverflow.com/questions/42753745/how-can-i-parse-geojson-with-python
        with open(trace_file) as fin:
            gj = json.load(fin)

            assert gj['type'] == 'FeatureCollection'

            for feature in gj['features']:
                yield feature

def geojson_converter(vnc)

    """Creates a PROJ convert from geojson lon/lat coordinates to
    coordinates derived from the velocity file.

    vnc: netCDF4.Dataset
        velocity file, opened

    """
    wks_s = vnc.variables['polar_stereographic'].spatial_ref
    map_crs = pyproj.CRS.from_string(wks_s)
    # Debugging
    # with open('crs.wkt', 'w') as fout:
    #    fout.write(wks_s)

    # Standard GeoJSON Coordinate Reference System (CRS)
    # Same as epsg:4326, but the urn: string is preferred
    # http://wiki.geojson.org/Rethinking_CRS
    # This CRS is lat/lon, whereas GeoJSON is lon/lat.  Use always_xy to fix that (below)
    geojson_crs = pyproj.CRS.from_string('urn:ogc:def:crs:OGC::CRS84')
    # geojson_crs = pyproj.CRS.from_epsg(4326)

    # https://pyproj4.github.io/pyproj/dev/examples.html
    # Note that crs_4326 has the latitude (north) axis first

    # Converts from geojson_crs to map_crs
    # See for always_xy: https://proj.org/faq.html#why-is-the-axis-ordering-in-proj-not-consistent
    proj = pyproj.Transformer.from_crs(geojson_crs, map_crs, always_xy=True)

    return proj

def iter_traces(trace_files, proj):
    """proj:
        Converter from lon/lat to x/y
    """
    for feature in iter_features(trace_files):
        sdate = feature['properties']['date']
        date = datetime.datetime.fromisoformat(sdate).date()

        gline_lonlat = feature['geometry']['coordinates']
        gline_xx,gline_yy = proj.transform(
            np.array([x[0] for x in gline_lonlat]),
            np.array([x[1] for x in gline_lonlat]))

        yield date,(gline_xx,gline_yy)


class VelocitySeries(object):
    """Yields timeseries of which velocity fiels to use for a starting and ending date"""

    def __init__(self, vnc):
        """vnc: netCDF4.Dataset
            velocity file, opened
        """
        times_num = vnc.variables['time'][:]
    #    dates = cftime.num2date(times_num, vnc.variables['time'].units)
        cfdates = netCDF4.num2date(times_num, vnc.variables['time'].units)
        self.dates = [datetime.date(x.year, x.month, x.day) for x in cfdates]

    def __call__(self, dt0, dt1):
        """Iterator of a series of velocity fields for a given date range"""
        # Find starting interval
        time_index = bisect.bisect_right(self.dates,dt0)-1
        print('ti {} ({} -- {})'.format(time_index, self.dates[time_index],self.dates[time_index+1]))
        while self.dates[time_index] <= dt1:
            yield max(dt0,self.dates[time_index]), min(dt1,self.dates[time_index+1]), time_index
            time_index += 1

class IceRemover(object):

    def __init__(self, bedmachine_file):
        """bedmachine-file: Local extract from global BedMachine"""
        with netCDF4.Dataset(bedmachine_file) as nc:

            bounding_xx = nc.variables['x'][:]
            bounding_yy = nc.variables['y'][:]

            # Determine Polygon of bounding box (xy coordinates; cell centers is OK)
            bb = (
                (bounding_xx[0],bounding_yy[0]), (bounding_xx[-1],bounding_yy[0]),
                (bounding_xx[-1],bounding_yy[-1]), (bounding_xx[0],bounding_yy[-1]))

            self.bounding_box = shapely.geometry.Polygon(bb)

            # ----- Determine regline: line going from end of 
            #dx = bounding_xx[-1] - bounding_xx[0]
            #dy = bounding_yy[-1] - bounding_yy[0]

            # Shift to cell edges (not cell centers)
            self.x0 = 2*bounding_xx[0] - bounding_xx[-1]    # x0-dx
            self.x1 = 2*bounding_xx[-1] - bounding_xx[0]    # x1+dx

            # ------- Read original thickness and bed
            self.thk = nc.variables['thickness'][:]
            self.bed = nc.variables['bed'][:]


    def thk(trace0):
        """Yields an ice thickness field that's been cut off at the terminus trace0
        trace0: (gline_xx,gline_yy)
            output of iter_traces()
        """

        # --------- Cut off ice at trace0
        # Convert raw trace0 to LineString gline0
        gline0 = shapely.geometry.LineString([
            (trace0[0][i], trace0[1][i]) for i in range(len(trace0[0]))])

        # Get least squares fit through the points
        slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(gline0[0], gline0[1])

        regline = shapely.geometry.LineString((
            (self.x0, slope*self.x0 + intercept),
            (self.x1, slope*self.x1 + intercept)))


        # -------------- Intersect bounding box and lsqr fit to terminus
        intersection = self.bounding_box.intersection(regline)
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
        merged = shapely.ops.linemerge([self.bounding_box.boundary, glinex])
        borders = shapely.ops.unary_union(merged)
        polygons = list(shapely.ops.polygonize(borders))

        with ioutil.tmp_dir() as tmp:

            # https://gis.stackexchange.com/questions/52705/how-to-write-shapely-geometries-to-shapefiles
        #    for i,poly in enumerate(polygons):
            i,poly = (0,polygons[0])
            if True:

                # Now convert it to a shapefile with OGR    
                driver = ogr.GetDriverByName('Esri Shapefile')
                poly_fname = os.path.join(tmp, 'poly{}.shp'.format(i))
                print('poly_fname ',poly_fname)
                ds = driver.CreateDataSource(poly_fname)
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

            # Mask out based on that polygon
            bed_masked_fname = os.path.join(tmp, 'bed_masked.nc')
        #    bed_masked_fname = 'x.nc'
            cmd =  ('gdalwarp', '-cutline', poly_fname, 'NETCDF:{}:bed'.format(bedmachine_file), bed_masked_fname)
            subprocess.run(cmd)

            # Read bed_maksed
            with netCDF4.Dataset(bed_masked_fname) as nc:
                bmask = nc.variables['Band1'][:].mask

        # Set bmask to the "downstream" side of the grounding line
        bmask_false = np.logical_not(bmask)
        if np.sum(np.sum(self.thk[bmask]==0)) < np.sum(np.sum(self.thk[bmask_false]==0)):
            bmask = bmask_false

        # Remove downstream ice
        thk = np.zeros(self.tnk.shape)
        thk[np.logical_and(bmask, self.bed<-100)] = 0

        return thk

        ## Store it...
        #with netCDF4.Dataset(bedmachine_file, 'r') as nc0:
        #    with netCDF4.Dataset('x.nc', 'w') as ncout:
        #        cnc = ncutil.copy_nc(nc0, ncout)
        #        vars = list(nc0.variables.keys())
        #        cnc.define_vars(vars)
        #        for var in vars:
        #            if var not in {'thickness'}:
        #                cnc.copy_var(var)
        #        ncout.variables['thickness'][:] = thk



def main():
    remover = IceRemover(bedmachine_file)
    with netCDF4.Dataset(velocity_file, 'r') as vnc:

        # Compu
        vseries = VelocitySeries(vnc)

        iter = iter_traces((trace_file,))
        for dt0,trace0 in iter:
            dt1,trace1 = next(iter)

            # Get ice thickness, adjusted for the present grounding line
            thk = remover.thk(trace0)

            # Iterate through portions of (dt0,dt1) with constant velocities
            for dti0,dti1,itime in vseries(dt0,dt1):
                uu = vnc.variables['u_ssa_bc'][itime,:,:]
                vv = vnc.variables['v_ssa_bc'][itime,:,:]







        print('------------- Trace for ', dt0, dt1)
        for dt0i,dt1i,ix in vseries(dt0,dt1):
            print('    {} {} {} (full range {} - {})'.format(dt0i,dt1i,ix,vseries.dates[ix],vseries.dates[ix+1]))



#    print(date, len(trace))

sys.exit(0)

for feature in iter_features((trace_file,)):
    # ['geometry', 'id', 'properties', 'type']
    assert feature['geometry']['type'] == 'LineString'
    points = feature['geometry']['coordinates']
    sdate = feature['properties']['date']
    date = datetime.datetime.fromisoformat(sdate).date()
    print(type(date),date)
    print(sdate, len(points))
#    print(points)