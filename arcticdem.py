from uafgi import make,glaciers,flowfill
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
import shapefile
import re
from osgeo import gdal,gdalconst
from uafgi.nsidc import nsidc0481
from uafgi import nsidc
import io,shutil

dmap_file = 'outputs/TSX_W71.65N_2008_2020_filled.nc'


# -----------------------------------------------

ARCTICDEM_SHP = 'data/ArcticDEM/ArcticDEM_Strip_Index_Rel7'
#trace_file = 'Amaral_TerminusTraces/TemporalSet/Jakobshavn/Jakobshavn10_2015-08-01_2015-08-23.geojson.json'
dmap_file = 'outputs/TSX_W71.65N_2008_2020_filled.nc'

def iter_features(trace_files):
    for trace_file in trace_files:
        # https://stackoverflow.com/questions/42753745/how-can-i-parse-geojson-with-python
        with open(trace_file) as fin:
            gj = json.load(fin)

            assert gj['type'] == 'FeatureCollection'

            for ls in gj['features']:
                yield ls

# Fix buggy URLs
fileRE = re.compile(r'/.*/2m_temp/(.*)_dem.tif')
def read_shapes(fname):
    with shapefile.Reader(fname) as sf:
        field_names = [x[0] for x in sf.fields[1:]]
        for i in range(0, len(sf)):
            shape = sf.shape(i)
            rec = sf.record(i)
            attrs = dict(zip(field_names, rec))

            # Fix bug in ArcticDEM URLs
            if 'fileurl' in attrs:
                fileurl = attrs['fileurl']
                match = fileRE.match(fileurl)
                if match is not None:
                    fileurl = 'http://data.pgc.umn.edu/elev/dem/setsm/ArcticDEM/geocell/v3.0/2m/' + match.group(1) + '.tar.gz'
                    attrs['fileurl'] = fileurl
                
            yield (shape,attrs)

# -------------------------------------------------------
def read_terminus(trace_file):
    """Read the terminus line, as a Shapely LineString, out of the trace file."""

    feature = next(iter_features((trace_file,)))
    gline_lonlat = feature['geometry']['coordinates']


    gline_xx,gline_yy = proj.transform(
        np.array([x[0] for x in gline_lonlat]),
        np.array([x[1] for x in gline_lonlat]))

    #print('grounding line: ', gline_xx, gline_yy)

    gline = shapely.geometry.LineString([
        (gline_xx[i], gline_yy[i]) for i in range(len(gline_xx))])

    return gline
# -------------------------------------------------------
def get_dmap_polygon(fname):
    """fname:
        Name of file with dmap variable in it (from flowfill.py)
    """
#    with ioutil.tmp_dir() as tdir:
    tdir = 'tmp'
    if True:
        # Copy (and modify) just the dmap variable to a temporary netCDF file
        with netCDF4.Dataset(fname) as nc:
            with netCDF4.Dataset(os.path.join(tdir, 'dmap.nc'), 'w') as ncout:
                cnc = ncutil.copy_nc(nc, ncout)
                cnc.define_vars(['x','y','polar_stereographic','dmap'], zlib=True)
                for vname in ('x','y','polar_stereographic'):
                    cnc.copy_var(vname)

                # Copy just the dmap variable
                dmap = nc.variables['dmap'][:]
                dmap[dmap != 0] = 1
                ncout.variables['dmap'][:] = dmap

        # Convert to dmap.tif
        cmd = ['gdal_translate',
            'NETCDF:{}:dmap'.format(os.path.join(tdir,'dmap.nc')),
#            'NETCDF:{}:dmap'.format(fname),
            os.path.join(tdir,'dmap.tif')]
        subprocess.run(cmd, check=True)

        # Polygonize dmap.tif
        cmd = ['gdal_polygonize.py', os.path.join(tdir,'dmap.tif'), os.path.join(tdir,'dmap.shp')]
        subprocess.run(cmd, check=True)

        # Read dmap.tif for the domain
        for shape,attrs in read_shapes(os.path.join(tdir,'dmap.tif')):
            # Search for the polygon surrounding value=1
            if attrs['DN'] == 1:
                break

        # Convert shapeful to Shapely polygon format
        poly = shapely.geometry.Polygon(shape.points)
        return poly
# -------------------------------------------------------
def intersecting_strips(arcticdem_index_shp, polygon):
    """
    arcticdem_index_shp:
        ArcticDEM index Shapefile (downloaded locally)
        The file is located at:
            http://data.pgc.umn.edu/elev/dem/setsm/ArcticDEM/indexes/ArcticDEM_Strip_Index_Rel7.zip
        
    polygon: shapely.Polygon
        Bounding box or area of interest to search
    yields: attrs (dict).  Interesting keys:
        fileurl: URL of .tar.gz file to download for this strip
        See other attribut fields at:
            https://services.arcgis.com/8df8p0NlLFEShl0r/ArcGIS/rest/services/PGC_ArcticDEM_Strip_Index_Rel7/FeatureServer/0
    """
    for shape,attrs in read_shapes(arcticdem_index_shp):
        # Convert to
        poly = shapely.geometry.Polygon(shape.points)
        if poly.intersects(polygon):
            yield attrs

# -------------------------------------------------------
def main0():
    # Read map projection from shapefile
    with open(ARCTICDEM_SHP + '.prj') as fin:
        wks_s = next(fin)
    map_crs = pyproj.CRS.from_string(wks_s)

    # -------------------------------------------------------
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
    dmap_polygon = get_dmap_polygon(dmap_file)

    # --------------------------------------------------------
    files = list()
    for shape,attrs in read_shapes(ARCTICDEM_SHP):
        # Convert to
        poly = shapely.geometry.Polygon(shape.points)
        if poly.intersects(dmap_polygon):
    #        if attrs['fileurl'][0] == '/':
    #            print(attrs)
    #        print(attrs['fileurl'])
            files.append(attrs)
    #        files.append((attrs['acquisitio'], attrs['name']))

    files.sort(key=lambda attrs: (attrs['acquisitio'], attrs['name']))
    for attrs in files:
    #   print(attrs)
        print(attrs['fileurl'])
# -------------------------------------------------------
    # The xyz correction file
    reg_file = dem_file.replace('_dem.tif', '_reg.txt')


transRE = re.compile(r'Translation Vector \(dz,dx,dy\)\(m\)=\s*(.*),\s*(.*),\s*(.*)')
def read_reg_offsets(reg_file):
    """Reads the xyz offset out of a _reg.txt file
    Returns: [dx, dy, dz]
        The offsets"""

    with open(reg_file) as fin:
        for line in fin:
            match = transRE.match(line)
            if match is not None:
                return [float(match.group(i)) for i in range(1,4)]

    raise ValueError('Could not find Translation Vector in {}'.format(reg_file))

def read_domain_dims(dim_file):
    """
    dim_file:
        Any old file with the x and y variables showing the bounds
        Eg: outputs/TSX_W71.65N_2008_2020_pism.nc
    """

    # Get bounding box
    with netCDF4.Dataset(dim_file) as nc:
        xx = nc.variables['x'][:]
        dx = xx[1]-xx[0]
        half_dx = .5 * dx
        x0 = round(xx[0] - half_dx)
        x1 = round(xx[-1] + half_dx)

        yy = nc.variables['y'][:]
        dy = yy[1]-yy[0]
        half_dy = .5 * dy
        y0 = round(yy[0] - half_dy)
        y1 = round(yy[-1] + half_dy)

    return (x0,x1,dx,y0,y1,dy)

def apply_reg_offsets(istrip_file, ostrip_file, offsets, domain_dims, tdir):
    """Two steps combined:
     1. Regrids to low(er)-res MEASURES grid
     2. Applys xyz correction to a raw ArcticDEM strip

    istrip_file: (_dem.tif)
        The main DEM file to read, the _dem.tif file from the ArcticDEM strip
    ostrip_file:
        Name of registered DEM file to create.
        (Will be netCDF format)
    offsets: (dx,dy,dz)
        The offset [m] to apply; obtained from _reg.txt file from ArcticDEM strip
    domain_dims: (x0,x1,dx,y0,y1,dy)
        The domain to which we regrid; obtained from a MEASURES file
    tdir:
        Write temporary files in this directory
    """

    x0,x1,dx,y0,y1,dy = domain_dims
    odir,oleaf = os.path.split(ostrip_file)
    vdt_file = os.path.join(tdir, os.path.splitext(oleaf)[0]+'.vdt')
    lowres_file = os.path.join(tdir, os.path.splitext(oleaf)[0]+'_lr.tif')

    offset_x,offset_y,offset_z = offsets
    sds = None
    vds = None
    try:
        sds = gdal.Open(istrip_file, gdalconst.GA_ReadOnly)

        gtf = sds.GetGeoTransform()
        trans_origin_x = gtf[0] + offset_x    # origin_x = gtf[0]
        trans_origin_y = gtf[3] + offset_y    # origin_y = gtf[3]

        ##  get new image geom, not nodata trimmed
        minx = trans_origin_x
        maxx = minx + sds.RasterXSize * gtf[1]
        maxy = trans_origin_y
        miny = maxy + sds.RasterYSize * gtf[5]
        
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(minx, miny)
        ring.AddPoint(minx, maxy)
        ring.AddPoint(maxx, maxy)
        ring.AddPoint(maxx, miny)
        ring.AddPoint(minx, miny)
        
        geom = ogr.Geometry(ogr.wkbPolygon)
        geom.AddGeometry(ring)
        
        # [-projwin ulx uly lrx lry]
        target_extent = "{} {} {} {}".format(minx, maxy, maxx, miny)

        VRTdrv = gdal.GetDriverByName("VRT")
        vds = VRTdrv.CreateCopy(vdt_file, sds, 0)
        dgtf = (trans_origin_x,gtf[1],gtf[2],trans_origin_y,gtf[4],gtf[5])
        vds.SetGeoTransform(dgtf)

    finally:
        if sds is not None:
            # https://gis.stackexchange.com/questions/80366/why-close-a-dataset-in-gdal-python
            del sds
        if vds is not None:
            del vds


    # Resample to target resolution
    cmd = ['gdal_translate',
        '-r', 'average',
        '-projwin', str(x0), str(y1), str(x1), str(y0),
        '-tr', str(dx), str(dy),
        vdt_file, lowres_file]
    print(cmd)
    subprocess.run(cmd, check=True)


    ## use gdal_calc to modify for z offset if raster is a DEM only
    cmd = ['gdal_calc.py',
        '-A', '{}'.format(lowres_file),
        '--calc', 'A+{}'.format(offset_z),
        '--outfile={}'.format(ostrip_file+'.nc'),
        '--format=netCDF',
        #'--co', 'COMPRESS=LZW',    # For GeoTIFF
        #'--co', 'TILED=YES',
        '--co', 'COMPRESS=DEFLATE',    # For netCDF
        '--co', 'FORMAT=NC4C',
        '--overwrite']
    print(cmd)
    subprocess.run(cmd, check=True)
# -------------------------------------------------------
def download_one_strip(url, ofname, domain_dims):
    """url:
        URL to download
    ofname:
        Name of final grid-limited strip to write.
    grid_file:
        Grid file to use in regridding the strip
    """

    odir = os.path.split(ofname)[0]
    uscoreRE = re.compile(r'.*_([^_]+)$')
#    with ioutil.tmp_dir(odir, tdir=os.path.join(odir,'tmp')) as tdir:
    with ioutil.tmp_dir(odir) as tdir:
        # Download the .tar.gz file
        cmd = ['curl', '-L', '--output', os.path.join(tdir, 'strip.tar.gz'), url]
        subprocess.run(cmd, check=True)

        # Untar it
        cmd = ['tar', 'xvfz', 'strip.tar.gz']
        untarred = dict()    # Map of files we untarred
        output = subprocess.run(cmd, cwd=tdir, check=True, capture_output=True)
        for bline in io.BytesIO(output.stdout):
            line = bline[:-1].decode()
            match = uscoreRE.match(line)
            key = match.group(1)
            fname = os.path.normpath(os.path.join(tdir, line))  # Absolute path w.r.t tdir
            untarred[key] = fname
            print('untarred[{}] = {}'.format(key,fname))


        # ---------------------------------
        # Shift horizontally (or not)
        if 'reg.txt' not in untarred:
            dem_shifted_vdt = untarred['dem.tif']
            offset_z = 0
        else:
            dem_shifted_vdt = os.path.join(tdir, 'dem_shifted.vdt')
            # Read offsets
            offsets = read_reg_offsets(untarred['reg.txt'])

            # Shift horizontally
            offset_x,offset_y,offset_z = offsets
            sds = None
            vds = None
            try:
                sds = gdal.Open(untarred['dem.tif'], gdalconst.GA_ReadOnly)

                gtf = sds.GetGeoTransform()
                trans_origin_x = gtf[0] + offset_x    # origin_x = gtf[0]
                trans_origin_y = gtf[3] + offset_y    # origin_y = gtf[3]

                ##  get new image geom, not nodata trimmed
                minx = trans_origin_x
                maxx = minx + sds.RasterXSize * gtf[1]
                maxy = trans_origin_y
                miny = maxy + sds.RasterYSize * gtf[5]
                
                ring = ogr.Geometry(ogr.wkbLinearRing)
                ring.AddPoint(minx, miny)
                ring.AddPoint(minx, maxy)
                ring.AddPoint(maxx, maxy)
                ring.AddPoint(maxx, miny)
                ring.AddPoint(minx, miny)
                
                geom = ogr.Geometry(ogr.wkbPolygon)
                geom.AddGeometry(ring)
                
                # [-projwin ulx uly lrx lry]
                target_extent = "{} {} {} {}".format(minx, maxy, maxx, miny)

                VRTdrv = gdal.GetDriverByName("VRT")
                vds = VRTdrv.CreateCopy(dem_shifted_vdt, sds, 0)
                dgtf = (trans_origin_x,gtf[1],gtf[2],trans_origin_y,gtf[4],gtf[5])
                vds.SetGeoTransform(dgtf)

            finally:
                if sds is not None:
                    # https://gis.stackexchange.com/questions/80366/why-close-a-dataset-in-gdal-python
                    del sds
                if vds is not None:
                    del vds
        # ---------------------------------

        # Resample to target resolution
        x0,x1,dx,y0,y1,dy = domain_dims
        lr_tif = os.path.join(tdir, 'lr.tif')
        cmd = ['gdal_translate',
            '-r', 'average',
            '-projwin', str(x0), str(y1), str(x1), str(y0),
            '-tr', str(dx), str(dy),
            dem_shifted_vdt, lr_tif]
        print(cmd)
        subprocess.run(cmd, check=True)


        ## use gdal_calc to modify for z offset if raster is a DEM only
        cmd = ['gdal_calc.py',
            '-A', '{}'.format(lr_tif),
            '--calc', 'A+{}'.format(offset_z),
            '--outfile={}'.format(ofname),
            '--format=netCDF',
            #'--co', 'COMPRESS=LZW',    # For GeoTIFF
            #'--co', 'TILED=YES',
            '--co', 'COMPRESS=DEFLATE',    # For netCDF
            '--co', 'FORMAT=NC4C',
            '--overwrite']
        print(cmd)
        subprocess.run(cmd, check=True)

        # Keep original file(s)
        for key in ('mdf.txt',):
            if key in untarred:
                leaf = os.path.split(untarred[key])[1]
                shutil.move(untarred[key], os.path.join(odir,leaf)) # overwrite if exists



# -------------------------------------------------------
class strip_list(object):
    """Creates a file defining the list of strips to download from
    ArcticDEM for a given grid."""

    def __init__(self, makefile, arcticdem_index_shp, grid_file, odir):
        # Hack: Parse grid out of the grid_file name
        match = re.match(r'([^-]+)-.*', os.path.split(grid_file)[1])
        self.grid = match.group(1)

        self.arcticdem_index_shp = arcticdem_index_shp
        self.grid_file = grid_file
        self.rule = makefile.add(self.run,
            (self.grid_file,),
            (os.path.join(odir, '{}-arcticdem-strips.txt'.format(self.grid)),))

    def run(self):
        # Get the list of strips
        x0,x1,dx,y0,y1,dy = read_domain_dims(self.grid_file)
        bounding_box = shapely.geometry.Polygon(((x0,y0), (x1,y0), (x1,y1), (x0,y1)))

        with open(self.rule.outputs[0], 'w') as out:
            for attrs in intersecting_strips(self.arcticdem_index_shp, bounding_box):
                print('ArcticDEM strip for {}: {}'.format(self.grid, attrs['fileurl']))
                out.write(attrs['fileurl'])
                out.write('\n')


# -------------------------------------------------------
class download_strips(object):
    """Downloads and regrids ArcticDEM strips matching a particular grid."""
    def __init__(self, makefile, strip_file, grid_file, odir):
        """grid:
            Name of grid (eg: W70.55N)
        grid_file:
            File containing the projection and x/y gridpoint info
        odir:
            output dir in which to create a subdir in which strips will go
        """

        # Hack: Parse grid out of the grid_file name
        match = re.match(r'([^-]+)-.*', os.path.split(grid_file)[1])
        grid = match.group(1)

        self.subdir = os.path.join(odir, '{}-arcticdem-strips'.format(grid))
        self.rule = makefile.add(self.run,
            (strip_file,),
            (self.subdir + '.done',))

        self.grid_file = grid_file
        self.strip_file = strip_file
        self.makefile = makefile

    def run(self):
        domain_dims = read_domain_dims(self.grid_file)
        print('domain_dims: ',domain_dims)
        with netCDF4.Dataset(self.grid_file) as nc:
            grid = nc.grid

        os.makedirs(self.subdir, exist_ok=True)
        with open(self.strip_file) as fin:
            for url in fin:
                url = url[:-1]    # Remove \n
                tar_gz = url.rsplit('/', 1)[-1]  # thing after last slash in URL
                oleaf = '{}-{}.nc'.format(tar_gz[:-7], grid)
                ofname = os.path.join(self.subdir, oleaf)
                if not os.path.exists(ofname):
                    print('Downloading to {}'.format(ofname))
                    download_one_strip(url, ofname, domain_dims)

                # Abort (debugging)
                #return

            ## Write dummy "done" file to signify we've downloaded everything
            #with open(self.rule.outputs[0], 'w') as out:
            #    out.write('Done')


# -------------------------------------------------------
def main1():
    offsets = read_reg_offsets('xx/SETSM_WV02_20130224_103001001FD83200_10300100203EE400_seg1_2m_v3.0_reg.txt')
    domain_dims = read_domain_dims('outputs/TSX_W71.65N_2008_2020_pism.nc')
    with ioutil.tmp_dir(tdir='tmp') as tdir:
        apply_reg_offsets(
            'xx/SETSM_WV02_20130224_103001001FD83200_10300100203EE400_seg1_2m_v3.0_dem.tif',
            'x.nc',
            offsets, domain_dims, tdir)
# -------------------------------------------------------
def main2():
    outputs = list()

    makefile = make.Makefile()

    for grid in ('W71.65N', 'W69.10N', 'W70.55N'):
        # Get grid file
        rule = nsidc.extract_grid(
            makefile, os.path.join('data', grid),
            nsidc0481.parse, 'outputs', grid).rule
        outputs.extend(rule.outputs)
        grid_file = rule.outputs[0]

        # Get list of ArcticDEM strips to download/process
        rule = strip_list(makefile, ARCTICDEM_SHP, grid_file, 'outputs').rule
        outputs.extend(rule.outputs)
        strip_file = rule.outputs[0]

        # Process them
        rule = download_strips(makefile, strip_file, grid_file, 'outputs').rule
        outputs.extend(rule.outputs)



    make.build(makefile, outputs)    
    return


    x0,x1,dx,y0,y1,dy = read_domain_dims('outputs/TSX_W71.65N_2008_2020_pism.nc')
    bounding_box = shapely.geometry.Polygon(((x0,y0), (x1,y0), (x1,y1), (x0,y1)))

    for attrs in intersecting_strips(ARCTICDEM_SHP, bounding_box):
        print(attrs['fileurl'])


main2()
