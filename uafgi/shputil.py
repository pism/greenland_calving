import numpy as np
import pyproj
import subprocess
import pathlib

from osgeo import ogr,gdal
import shapefile
import shapely.geometry

from uafgi import cdoutil

shapely2ogr = {
    'Polygon' : ogr.wkbPolygon,
    'MultiPolygon' : ogr.wkbMultiPolygon,
}
    
def write_shapefile(shapely_obj, fname):
    """Writes a single Shapely object into a shapefile"""

    ogr_type = shapely2ogr[shapely_obj.geom_type]

    # Now convert it to a shapefile with OGR    
    driver = ogr.GetDriverByName('Esri Shapefile')
    ds = driver.CreateDataSource(fname)
    layer = ds.CreateLayer('', None, ogr_type)

    # Add one attribute
    layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))
    defn = layer.GetLayerDefn()

    ## If there are multiple geometries, put the "for" loop here

    # Create a new feature (attribute and geometry)
    feat = ogr.Feature(defn)
    feat.SetField('id', 123)

    # Make a geometry, from Shapely object
    geom = ogr.CreateGeometryFromWkb(shapely_obj.wkb)
    feat.SetGeometry(geom)

    layer.CreateFeature(feat)

    # ------- Local variables are all destroyed
    # feat = geom = None  # destroy these
    # Save and close everything
    # ds = layer = feat = geom = None



class ShapefileReader(object):
    """Shapefile reader, augmented to convert to desired projection."""

    def __init__(self, fname, crs1):
        self.fname = fname
        self.crs1 = crs1    # Projection to translate to

    def __enter__(self):
        self.reader = shapefile.Reader(self.fname)

        # Get CRS out of shapefile
        with open(self.fname[:-4] + '.prj') as fin:
            self.crs0 = pyproj.CRS.from_string(next(fin))

        # Converts from self.crs0 to self.crs1
        # See for always_xy: https://proj.org/faq.html#why-is-the-axis-ordering-in-proj-not-consistent
        self.proj = pyproj.Transformer.from_crs(self.crs0, self.crs1, always_xy=True)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.reader.__exit__(exc_type, exc_value, exc_traceback)

    def polygon(self, ix):
        """Read a shape, reproject and convert to Polygon"""
        shape = self.reader.shape(ix)
        if shape.shapeType != shapefile.POLYGON:
            raise ValueError('shapefile.POLYGON shapeType expected in file {}'.format(self.fname))

        gline_xx,gline_yy = self.proj.transform(
            np.array([xy[0] for xy in shape.points]),
            np.array([xy[1] for xy in shape.points]))
        return shapely.geometry.Polygon(zip(gline_xx, gline_yy))


class ShapefileWriter(object):
    """Writes Shapely objects into a shapefile"""

    def __init__(self, fname, shapely_type, field_defs):
        """
        fname:
            Name of file to create
        shapely_type: str
            Type of Shapely object that will be written here
            Eg: 'Polygon', 'MultiPolygon'
        field_defs: ((name,type), ...)
            name: Name of attribute field
            type: ogr.OFTInteger, etc.
                  https://gdal.org/java/org/gdal/ogr/ogrConstants.html
        """
        self.fname = fname
        self.field_defs = field_defs
        self.shapely_type = shapely_type

    def __enter__(self):
        ogr_type = shapely2ogr[self.shapely_type]

        # Now convert it to a shapefile with OGR    
        self.driver = ogr.GetDriverByName('Esri Shapefile')
        self.ds = self.driver.CreateDataSource(self.fname)
        self.layer = self.ds.CreateLayer('', None, ogr_type)

        # Add attributes
#        print('fd ',self.field_defs)
        for name,ftype in self.field_defs:
            self.layer.CreateField(ogr.FieldDefn(name, ftype))
        #self.layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger))

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.layer = None

    def write(self, shapely_obj, **fields):
#        if shapely_obj.geom_type != self.shapely_type:
#            raise TypeError('Trying to write an object of type {} to a file of type {}'.format(shapely_obj.geom_type, self.shapely_type))

#        ogr_type = shapely2ogr[shapely_obj.geom_type]

        ## If there are multiple geometries, put the "for" loop here

        # Create a new feature (attribute and geometry)
        defn = self.layer.GetLayerDefn()
        feat = ogr.Feature(defn)
        for field,value in fields.items():
            feat.SetField(field, value)

        # Make a geometry, from Shapely object
        geom = ogr.CreateGeometryFromWkb(shapely_obj.wkb)
        feat.SetGeometry(geom)

        self.layer.CreateFeature(feat)

        # ------- Local variables are all destroyed
        # feat = geom = None  # destroy these
        # Save and close everything
        # ds = self.layer = feat = geom = None


def get_crs(shapefile):
    """Reads the coordinate reference system (CRS) of a shapefile.

    shapefile: *.shp
        The .shp fork of a shapefile
    Returns:
        String of CRS
    """

    with open(shapefile[:-4] + '.prj') as fin:
        wks_s = next(fin)
    termini_crs = pyproj.CRS.from_string(wks_s)


def select_feature(ishapefile, fid, oshapefile):
    """Selects a single feature out of a shapefile and stores into a new shapefile
    ishapefile:
        Input shapefile
    fid:
        ID of feature to select (0-based)
    oshapefile:
        Output shapefile
    """

    # Select a single polygon out of the shapefile
    cmd = ['ogr2ogr', oshapefile, ishapefile, '-fid', str(fid)]
    subprocess.run(cmd, check=True)

def fjord_mask(termini_closed_file, index, geometry_file, tdir):
    """Converts a closed polygon in a shapefile into

    termini_closed_file:
        Shapefile containing the closed terminus polygons.
        One side of the polygon is the terminus; the rest is nearby parts of the fjord.
    index:
        Which polygon (stargin with 0) in the terminus shapefile to use.
    tdir: ioutil.TmpDir
        Location for temporary files
    """

    with ioutil.tmp_dir(odir, tdir='tdir') as tdir:

        one_terminus = os.path.join(tdir, 'one_terminus.shp')
        select_feature(termini_closed_file, index, one_terminus)

        # Cut the bedmachine file based on the shape
        cut_geometry_file = os.path.join(tdir, 'cut_geometry_file.nc')
        cmd = ['gdalwarp', '-cutline', one_terminus, 'NETCDF:{}:bed'.format(geometry_file), cut_geometry_file]
        subprocess.run(cmd, check=True)

        # Read the fjord mask from that file
        with netCDF4.Dataset(cut_geometry_file) as nc:
            fjord = nc.variables['Band1'][:].mask

    return fjord


def check_error(err):
    if err != 0:
        raise 'GDAL Error {}'.format(err)

def rasterize_polygons(shapefile, fids, gridfile, tdir):
    """Generator yields rasterized version of polygons from shapefile.

    shapefile:
        Name of the shapefile containing the polygon to rasterize
    layers:
        Iterable of layers (sections of the shapefile) to rasterize
        Can be either indices (0-based), or names of layers
    gridfile:
        Name of NetCDF file containing projection, x, y etc. variables of local grid.
        Fine if it also contains data.
    Yields:
        Each specified layer in the shapefile, rasterized
    """


    fb = cdoutil.FileBounds(gridfile)

    maskvalue = 1

    for fid in fids:

        # Select single feature into a file
        # https://gis.stackexchange.com/questions/330811/how-to-rasterize-individual-feature-polygon-from-shapefile-using-gdal-ogr-in-p
        one_shape = tdir.join('one_shape.shp')
        select_feature(shapefile, fid, one_shape)
        print(pathlib.Path(one_shape).stat().st_size)

        src_ds = ogr.Open(one_shape)
        src_lyr = src_ds.GetLayer()   # Put layer number or name in her

        dst_ds = gdal.GetDriverByName('netCDF').Create('x{}.nc'.format(fid), int(fb.nx), int(fb.ny), 1 ,gdal.GDT_Byte)
#        dst_ds = gdal.GetDriverByName('MEM').Create('', int(fb.nx), int(fb.ny), 1 ,gdal.GDT_Byte)
        dst_rb = dst_ds.GetRasterBand(1)
        dst_rb.Fill(0) #initialise raster with zeros
        dst_rb.SetNoDataValue(0)
        dst_ds.SetGeoTransform(fb.geotransform)

        check_error(gdal.RasterizeLayer(dst_ds, [1], src_lyr, burn_values=[maskvalue]))

        dst_ds.FlushCache()

        mask_arr=dst_ds.GetRasterBand(1).ReadAsArray()
        yield mask_arr

def crs(shapefile):
    """Reads the coordinate reference system (CRS) out of a shapefile.
    (Actually, out of a shapefile's .prj file)

    shapefile:
        Name of the shapefile (with or without .shp extension)
    Returns:
        CRS as a string
    """
    fname = os.path.splitext(shapefile)[0] + '.prj'
    with open(fname) as fin:
        crs = pyproj.CRS.from_string(next(fin))
    return crs
