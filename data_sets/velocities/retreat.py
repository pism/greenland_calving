import cf_units
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
from uafgi import ioutil,ncutil,cfutil,argutil,make,geoutil,flowfill
import datetime
import PISM
from uafgi.pism import calving0
from uafgi.make import ncmake
import subprocess
import shapefile
from scipy import signal

def iter_features(trace_files):
    """Reads features out of a GeoJSON file"""
    for trace_file in trace_files:
        # https://stackoverflow.com/questions/42753745/how-can-i-parse-geojson-with-python
        with open(trace_file) as fin:
            gj = json.load(fin)

            assert gj['type'] == 'FeatureCollection'

            for feature in gj['features']:
                yield feature

def geojson_converter(velocity_file):

    """Creates a PROJ convert from geojson lon/lat coordinates to
    coordinates derived from the velocity file.

    vnc: netCDF4.Dataset
        velocity file (filename)

    """
    with netCDF4.Dataset(velocity_file) as vnc:
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

    def __init__(self, velocity_file):
        """vnc: netCDF4.Dataset
            velocity file, opened
        """
        with netCDF4.Dataset(velocity_file) as vnc:
            nctime = vnc.variables['time']
            sunits = nctime.units
            times_d = vnc.variables['time'][:]    # "days since <refdate>

            # Convert to "seconds since <refdate>"
            time_units = cf_units.Unit(nctime.units, nctime.calendar)
            self.units_s = cfutil.replace_reftime_unit(time_units, 'seconds')
            self.times_s = [time_units.convert(t_d, self.units_s) for t_d in times_d]

            # Obtain coordinate reference system
            wks_s = vnc.variables['polar_stereographic'].spatial_ref
            self.map_crs = pyproj.CRS.from_string(wks_s)


    def __call__(self, t0_s, t1_s):
        """Iterator of a series of velocity fields for a given date range"""
        # Find starting interval
        time_index = bisect.bisect_right(self.times_s,t0_s)-1
        while self.times_s[time_index] <= t1_s:
            yield time_index,max(t0_s,self.times_s[time_index]), min(t1_s,self.times_s[time_index+1])
            time_index += 1


def replace_thk(bedmachine_file0, bedmachine_file1, thk):
    """Copies bedmachine_file0 to bedmachine_file1, using thk in place of original 'thickness'
    bedmachien_file0:
        Name of original BedMachine file
    bedmachine_file1:
        Name of output BedMachine file
    thk:
        Replacement thickness field"""

    with netCDF4.Dataset(bedmachine_file0, 'r') as nc0:
        with netCDF4.Dataset(bedmachine_file1, 'w') as ncout:
            cnc = ncutil.copy_nc(nc0, ncout)
            vars = list(nc0.variables.keys())
            cnc.define_vars(vars)
            for var in vars:
                if var not in {'thickness'}:
                    cnc.copy_var(var)
            ncout.variables['thickness'][:] = thk


class IceRemover(object):

    def __init__(self, bedmachine_file):
        """bedmachine-file: Local extract from global BedMachine"""
        self.bedmachine_file = bedmachine_file
        with netCDF4.Dataset(self.bedmachine_file) as nc:

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


    def get_thk(self, trace0):
        """Yields an ice thickness field that's been cut off at the terminus trace0
        trace0: (gline_xx,gline_yy)
            output of iter_traces()
        """

        # --------- Cut off ice at trace0
        # Convert raw trace0 to LineString gline0
        gline0 = shapely.geometry.LineString([
            (trace0[0][i], trace0[1][i]) for i in range(len(trace0[0]))])

        # Get least squares fit through the points
#        slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(gline0[0], gline0[1])
        slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(trace0[0], trace0[1])

        regline = shapely.geometry.LineString((
            (self.x0, slope*self.x0 + intercept),
            (self.x1, slope*self.x1 + intercept)))


        # -------------- Intersect bounding box and lsqr fit to terminus
        intersection = self.bounding_box.intersection(regline)
        print('intersection ',list(intersection.coords))
        print(intersection.wkt)

        # -------------- Extend gline LineString with our intersection points
        intersection_ep = intersection.boundary
        gline_ep = gline0.boundary
        # Make sure intersection[0] is closets to gline[0]
        if intersection_ep[0].distance(gline_ep[0]) > intersection_ep[0].distance(gline_ep[1]):
            intersection_ep = (intersection_ep[1],intersection_ep[0])

        # Extend gline
        #print(list(intersection_ep[0].coords))
        print(intersection_ep[0].coords[0])
        glinex = shapely.geometry.LineString(
            [intersection_ep[0].coords[0]] + list(gline0.coords) + [intersection_ep[1].coords[0]])

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
            cmd =  ('gdalwarp', '-cutline', poly_fname, 'NETCDF:{}:bed'.format(self.bedmachine_file), bed_masked_fname)
            subprocess.run(cmd)

            # Read bed_maksed
            with netCDF4.Dataset(bed_masked_fname) as nc:
                bmask = nc.variables['Band1'][:].mask

        # Set bmask to the "downstream" side of the grounding line
        bmask_false = np.logical_not(bmask)
        if np.sum(np.sum(self.thk[bmask]==0)) < np.sum(np.sum(self.thk[bmask_false]==0)):
            bmask = bmask_false

        # Remove downstream ice
        thk = np.zeros(self.thk.shape)
        thk[:] = self.thk[:]
        thk[np.logical_and(bmask, self.bed<-100)] = 0

#        thk *= 0.5

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





class IceRemover2(object):

    def __init__(self, bedmachine_file):
        """bedmachine-file: Local extract from global BedMachine"""
        self.bedmachine_file = bedmachine_file
        with netCDF4.Dataset(self.bedmachine_file) as nc:

            # ------- Read original thickness and bed
            self.thk = nc.variables['thickness'][:]

    def get_thk(self, termini_closed_file, index, odir):
        """Yields an ice thickness field that's been cut off at the terminus trace0
        trace0: (gline_xx,gline_yy)
            output of iter_traces()
        """

        with ioutil.tmp_dir(odir, tdir='tdir') as tdir:
#        if True:
            # Select a single polygon out of the shapefile
            one_terminus = os.path.join(tdir, 'one_terminus_closed.shp')
            cmd = ['ogr2ogr', one_terminus, termini_closed_file, '-fid', str(index)]
            subprocess.run(cmd, check=True)

            # Cut the bedmachine file based on the shape
            cut_geometry_file = os.path.join(tdir, 'cut_geometry_file.nc')
            cmd = ['gdalwarp', '-cutline', one_terminus, 'NETCDF:{}:bed'.format(self.bedmachine_file), cut_geometry_file]
            subprocess.run(cmd, check=True)

            # Read the fjord mask from that file
            with netCDF4.Dataset(cut_geometry_file) as nc:
                fjord = np.logical_not(nc.variables['Band1'][:].mask)
            print('fjord sum: {} {}'.format(np.sum(np.sum(fjord)), fjord.shape[0]*fjord.shape[1]))


            # Remove downstream ice
            thk = np.zeros(self.thk.shape)
            thk[:] = self.thk[:]
            thk[fjord] = 0

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










def iterate_termini(termini_file, map_crs):
    """Iterate through the terminus shapefiles from the CALFIN terminus dataset
    yields: date, (gline_xx, gline_yy)
        date: datetime.date
            Date of terminus
        gline_xx, gline_yy: [],[]
            X and Y coordinates of the terminus
    """

    # The CRS associated with shapefile
    with open(termini_file[:-4] + '.prj') as fin:
        wks_s = next(fin)
    termini_crs = pyproj.CRS.from_string(wks_s)
#    print('termini_crs = {}'.format(termini_crs.to_proj4()))
#    print('    map_crs = {}'.format(map_crs.to_proj4()))
#    print('EQUAL: {}'.format(termini_crs.equals(map_crs)))

    # Converts from termini_crs to map_crs
    # See for always_xy: https://proj.org/faq.html#why-is-the-axis-ordering-in-proj-not-consistent
    proj = pyproj.Transformer.from_crs(termini_crs, map_crs, always_xy=True)

    for shape,attrs in geoutil.read_shapes(termini_file):
        if shape.shapeType != shapefile.POLYGON:
            raise ValueError('shapefile.POLYGON shapeType expected in file {}'.format(termini_file))

        gline_xx,gline_yy = proj.transform(
            np.array([xy[0] for xy in shape.points]),
            np.array([xy[1] for xy in shape.points]))

        dt = datetime.datetime.strptime(attrs['Date'], '%Y-%m-%d').date()
        print(attrs)
        yield dt, (gline_xx, gline_yy)

def fjord_mask(termini_closed_file, index, geometry_file, odir):
    """Converts a closed polygon in a shapefile into
    termini_closed_file:
        Shapefile containing the closed terminus polygons.
        One side of the polygon is the terminus; the rest is nearby parts of the fjord.
    index:
        Which polygon (stargin with 0) in the terminus shapefile to use.
    odir:
        Output directory.  Won't create any files, but WILL put temporary files here.
    """

    with ioutil.tmp_dir(odir, tdir='tdir') as tdir:

        # Select a single polygon out of the shapefile
        one_terminus = os.path.join(tdir, 'one_terminus.shp')
        cmd = ['ogr2ogr', one_terminus, termini_closed_file, '-fid', str(index)]
        subprocess.run(cmd, check=True)

        # Cut the bedmachine file based on the shape
        cut_geometry_file = os.path.join(tdir, 'cut_geometry_file.nc')
        cmd = ['gdalwarp', '-cutline', one_terminus, 'NETCDF:{}:bed'.format(geometry_file), cut_geometry_file]
        subprocess.run(cmd, check=True)

        # Read the fjord mask from that file
        with netCDF4.Dataset(cut_geometry_file) as nc:
            fjord = nc.variables['Band1'][:].mask

    return fjord


def main1():
    termini_closed_file = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Isbrae_closed_v1.0.shp'
    geometry_file = 'outputs/BedMachineGreenland-2017-09-20_pism_W71.65N.nc'
    odir = 'outputs'

    # The main CRS we are working in
    with netCDF4.Dataset(geometry_file) as nc:
        wks_s = nc.variables['polar_stereographic'].spatial_ref
    map_crs = pyproj.CRS.from_string(wks_s)
#    print('map_crs = {}'.format(map_crs))

    # Read attributes from the shapefile
    remover = IceRemover2(geometry_file)
    attrss = [attrs for _,attrs in geoutil.read_shapes(termini_closed_file)]
    for ix in range(1,len(attrss)):
        if ix < 34:
            continue

        thk = remover.get_thk(termini_closed_file, ix, odir)



        with ioutil.tmp_dir(odir, tdir='tdir') as tdir:

            # Select a single polygon out of the shapefile
            one_terminus = os.path.join(tdir, 'one_terminus.shp')
            cmd = ['ogr2ogr', one_terminus, termini_file, '-fid', str(ix)]
            subprocess.run(cmd, check=True)

            # Cut the bedmachine file based on the shape
            cut_geometry_file = os.path.join(tdir, 'cut_geometry_file.nc')
            cmd = ['gdalwarp', '-cutline', one_terminus, 'NETCDF:{}:bed'.format(geometry_file), cut_geometry_file]
            subprocess.run(cmd, check=True)

            # Read the fjord mask from that file
            with netCDF4.Dataset(cut_geometry_file) as nc:
                bmask = nc.variables['Band1'][:].mask



#            dt0 = datetime.datetime.strptime(attrs0['Date'], '%Y-%m-%d').date()

            break



#main1()
#sys.exit(0)

def get_fjord(bed, terminus_location):
    passq


class ReadExtents(object):
    """Reads extents from NetCDF file.
    May be used, eg, as:
                '-projwin', str(x0), str(y1), str(x1), str(y0),
                '-tr', str(dx), str(dy),
    """
    def __init__(self, data_path):
        with netCDF4.Dataset(data_path) as nc:
            xx = nc.variables['x'][:]
            self.dx = xx[1]-xx[0]
            half_dx = .5 * self.dx
            self.x0 = round(xx[0] - half_dx)
            self.x1 = round(xx[-1] + half_dx)

            yy = nc.variables['y'][:]
            self.dy = yy[1]-yy[0]
            half_dy = .5 * self.dy
            self.y0 = round(yy[0] - half_dy)
            self.y1 = round(yy[-1] + half_dy)


            self.wks_s = nc.variables['polar_stereographic'].spatial_ref


class compute(object):

    default_kwargs = dict(calving0.FrontEvolution.default_kwargs.items())
    default_kwargs['min_ice_thickness'] = 50.0

    def __init__(self, makefile, geometry_file, velocity_file, termini_file, termini_closed_file, otemplate, **kwargs0):
        """kwargs0:
            See default_kwargs above
        otemplate:
            Template used to construct output filenames, including directory
            May include: {dt0}, {dt1}
        """
        self.kwargs = argutil.select_kwargs(kwargs0, self.default_kwargs)

        self.geometry_file = geometry_file
        print('geometry_file = {}'.format(self.geometry_file))
        self.velocity_file = velocity_file
        print('velocity_file = {}'.format(self.velocity_file))
        self.termini_file = termini_file
        self.termini_closed_file = termini_closed_file
#        print('trace_file = {}'.format(self.trace_file))


        # Determine terminus pairs
        self.terminus_pairs = list()    # [ ((dt0,ix0), (dt1,ix1)) ]
        attrss = enumerate(iter([attrs for _,attrs in geoutil.read_shapes(termini_closed_file)]))
        self.odir = os.path.split(otemplate)[0]
        ix0,attrs0 = next(attrss)
        dt0 = datetime.datetime.strptime(attrs0['Date'], '%Y-%m-%d').date()
        self.output_files = list()
        for ix1,attrs1 in attrss:
            dt1 = datetime.datetime.strptime(attrs1['Date'], '%Y-%m-%d').date()

#            if ix0 == 34:    # DEBUGGING: just one
            if dt0.year >= 2012:   # DEBUGGING
                self.terminus_pairs.append((ix0,dt0,ix1,dt1))
                sdt0 = datetime.datetime.strftime(dt0, '%Y%m%d')
                sdt1 = datetime.datetime.strftime(dt1, '%Y%m%d')
                self.output_files.append(otemplate.format(dt0=sdt0, dt1=sdt1))

            ix0,dt0 = ix1,dt1

        self.rule = makefile.add(self.run,
            [geometry_file, velocity_file, termini_file, termini_closed_file],
            self.output_files)

    def run(self):
        with ioutil.tmp_dir(self.odir, tdir='tdir') as tdir:
            proj = geojson_converter(self.velocity_file)
            remover = IceRemover2(self.geometry_file)
            vseries = VelocitySeries(self.velocity_file)


            # Get CRS out of shapefile
            with open(self.termini_file[:-4] + '.prj') as fin:
                termini_crs = pyproj.CRS.from_string(next(fin))

            # Converts from termini_crs to map_crs
            # See for always_xy: https://proj.org/faq.html#why-is-the-axis-ordering-in-proj-not-consistent
            proj = pyproj.Transformer.from_crs(termini_crs, vseries.map_crs, always_xy=True)

            # Run the glacier between timesteps
            for (ix0,dt0,ix1,dt1),output_file4 in zip(self.terminus_pairs, self.output_files):
                output_file3 = output_file4 + '3'    # .nc3


                # Get ice thickness, adjusted for the present grounding line
                thk = remover.get_thk(self.termini_closed_file, ix0, self.odir)
                print('thk sum: {}'.format(np.sum(np.sum(thk))))
    #            print('********* thk sum: {}'.format(np.sum(np.sum(thk))))
                # Create custom geometry_file (bedmachine_file)
                geometry_file1 = output_file4[:-3] + '_bedmachine.nc'
                replace_thk(self.geometry_file, geometry_file1, thk)

                # Convert to "seconds since..." units                       
                t0_s = vseries.units_s.date2num(datetime.datetime(dt0.year,dt0.month,dt0.day))
                t1_s = vseries.units_s.date2num(datetime.datetime(dt1.year,dt1.month,dt1.day))

                # ---------------------- Where to look for ice changing

                # ----- Determine trough of this glacier.  Get sample terminus based
                # on first terminus in our run
                #ix0,dt0,_,_ = self.terminus_pairs[0]
                #t0_s = vseries.units_s.date2num(datetime.datetime(dt0.year,dt0.month,dt0.day))
                itime0,_,_ = next(vseries(t0_s,t1_s))    # Get a sample time for sample velocities
                #with netCDF4.Dataset(self.velocity_file) as nc:
                #    vsvel = nc.variables['v_ssa_bc'][itime0,:]
                #    usvel = nc.variables['u_ssa_bc'][itime0,:]
                with netCDF4.Dataset(self.geometry_file) as nc:
                    bed = nc.variables['bed'][:]
                    thk = nc.variables['thickness'][:]
                    yy = nc.variables['y'][:]
                    xx = nc.variables['x'][:]
                dyx = (yy[1]-yy[0], xx[1]-xx[0])

                # trough = flowfill.single_trough(thk, bed, vsvel, usvel, terminus_centroid, 20000)
                #with netCDF4.Dataset(geometry_file1, 'a') as nc:
                #    ncv = nc.createVariable('trough', 'i1', ('y','x'))
                #    ncv[:] = trough
                # trough_d = trough.astype('d')

                # ----- Rasterize the terminus trace
                ext = ReadExtents(self.geometry_file)
                one_terminus = os.path.join(tdir, 'one_terminus.shp')
                cmd = ['ogr2ogr', one_terminus, self.termini_file, '-fid', str(ix0)]
                subprocess.run(cmd, check=True)

                terminus_raster = os.path.join(tdir, 'terminus_raster.nc')
                cmd = ['gdal_rasterize', 
                    '-a_srs', ext.wks_s,
                    '-tr', str(ext.dx), str(ext.dy),
                    '-te', str(ext.x0), str(ext.y0), str(ext.x1), str(ext.y1),
                    '-burn', '1', one_terminus, terminus_raster]
                print(' '.join(cmd))
                subprocess.run(cmd, check=True)
                with netCDF4.Dataset(terminus_raster) as nc:
                    terminus_d = nc.variables['Band1'][:]

                #with shapefile.Reader(self.termini_file) as sf:
                #    terminus_sf = sf.shape(ix0)
                #    gline_xx,gline_yy = proj.transform(
                #        [xy[0] for xy in terminus_sf.points],
                #        [xy[1] for xy in terminus_sf.points])
                #    glxy = list(zip(gline_xx,gline_yy))
                #    terminus= shapely.geometry.LineString(glxy)
                #terminus_centroid = terminus.centroid.coords[0]

                # ------------ Find points close to the terminus trace
                stencil = flowfill.disc_stencil(300., dyx)
                terminus_domain = (signal.convolve2d(terminus_d, stencil, mode='same') != 0)
                if np.sum(np.sum(terminus_domain)) == 0:
                    raise ValueError('Nothing found in the domain, something is wrong...')

                # Debug
                with netCDF4.Dataset(geometry_file1, 'a') as nc:
                    ncv = nc.createVariable('terminus', 'i1', ('y','x'))
                    ncv[:] = terminus_domain



                # ---------------------------------------------------------------

                print('============ Running {} - {}'.format(dt0,dt1))






#NO... we need to find the FJORD, not the TROUGH.  That is easy, based on bed depth.  Just make sure you find the portion of the fjord close to the terminus line.

#            geometry_file1 = self.geometry_file    # DEBUG
            try:

                # The append_time=True argument of prepare_output
                # determines if after this call the file will contain
                # zero (append_time=False) or one (append_time=True)
                # records.
                output = PISM.util.prepare_output(output_file3, append_time=False)

                #### I need to mimic this: Ross_combined.nc plus the script that made it
                # Script in the main PISM repo, it's in examples/ross/preprocess.py
                #self.geometry_file = "~/github/pism/pism/examples/ross/Ross_combined.nc"
                # self.geometry_file = "Ross_combined.nc"
                ctx = PISM.Context()
                # TODO: Shouldn't this go in calving0.init_geometry()?
                ctx.config.set_number("geometry.ice_free_thickness_standard", self.kwargs['min_ice_thickness'])

                grid = calving0.create_grid(ctx.ctx, geometry_file1, "thickness")
                geometry = calving0.init_geometry(grid, geometry_file1, self.kwargs['min_ice_thickness'])


                ice_velocity = calving0.init_velocity(grid, self.velocity_file)
                print('ice_velocity sum: '.format(np.sum(np.sum(ice_velocity))))

                # NB: For debugging I might use a low value of sigma_max to make SURE things retreat
                # default_kwargs = dict(
                #     ice_softness=3.1689e-24, sigma_max=1e6, max_ice_speed=5e-4)
#                fe_kwargs = dict(sigma_max=0.1e6)
                fe_kwargs = dict(sigma_max=1e6)
                front_evolution = calving0.FrontEvolution(grid, **fe_kwargs)

                # ========== ************ DEBUGGING *****************
#                xout = PISM.util.prepare_output('x.nc', append_time=False)
#                PISM.append_time(xout, front_evolution.config, 17)
#                geometry.ice_thickness.write(xout)
#                geometry.cell_type.write(xout)
            

                # Iterate through portions of (dt0,dt1) with constant velocities
                print('TIMESPAN: {} {}'.format(t0_s, t1_s))
                for itime,t0i_s,t1i_s in vseries(t0_s,t1_s):
                    print('ITIME: {} {} ({} -- {})'.format(t0i_s, t1i_s, dt0, dt1))
                    ice_velocity.read(self.velocity_file, itime)   # 0 ==> first record of that file (if time-dependent)

                    front_evolution(geometry, ice_velocity,
                        t0_s, t1_s,
                        output=output)
            finally:
                output.close()


            # Compress output file while correcting time units
            cmd = ['ncks', '-4', '-L', '1', '-O', output_file3, output_file4]
            subprocess.run(cmd, check=True)
            os.remove(output_file3)
            with netCDF4.Dataset(output_file4, 'a') as nc:
                nc.variables['time'].units = str(vseries.units_s) # 'seconds since {:04d}-{:02d}-{:02d}'.format(dt0.year,dt0.month,dt0.day)
                nc.variables['time'].calendar = 'proleptic_gregorian'


    #            # Add dummy var to output_file; helps ncview
    #            with netCDF4.Dataset(output_file, 'a') as nc:
    #                nc.createVariable('dummy', 'i', ('x',))

def main():
    makefile = make.Makefile()
    geometry_file = 'outputs/BedMachineGreenland-2017-09-20_pism_W71.65N.nc'
    velocity_file = 'outputs/TSX_W71.65N_2008_2020_filled.nc'
    termini_file = 'data/calfin/domain-termini/termini_1972-2019_Rink-Isbrae_v1.0.shp'
    termini_closed_file = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Isbrae_closed_v1.0.shp'
    otemplate = 'outputs/retreat_calfin_W71.65N_{dt0}_{dt1}.nc'

    compute(makefile,
        geometry_file, velocity_file, termini_file, termini_closed_file, otemplate).run()

main()
