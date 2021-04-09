from osgeo import gdal
import numpy as np
import scipy.optimize
from uafgi import shputil,ioutil,gdalutil,geotiffutil
import subprocess

# Classification values
OCEAN = 3
CLOUD = 2
ICE = 1
SNOW = 0


class _Offsides:
    """For a given snowline z, function determines how many snow and ice
    gridcells are "offsides;" meaning snow below the snowline or ice
    above the snowline.
    """

    def __init__(self, cls, ele):
        """cls: np.array
            Surface classification (ICE=1, SNOW=0)
        ele: np.array
            Elevations
        """
        self.icez = np.sort(ele[cls==ICE])
        self.snowz = np.sort(ele[cls==SNOW])


    def __call__(self, z):
        ice_of = len(self.icez) - np.searchsorted(self.icez, z)
        snow_of = np.searchsorted(self.snowz, z)
        return ice_of,snow_of


def get_snowline(cls0, ele, grid_info, outline_shp):
    """Computes the snowline within a (union of) polygons.
    cls0: np.array
        Surface type classification raster
    ele: np.array
        Elevation classification raster
    gridfile_nc:
        NetCDF file containing raster grid / domain info
    outline_shp:
        Polygons within which snowline will be computed.
        File can be in any projection.
    Returns: dict
        snowline_z:
            Best-fit snowline within the region of the outline polygon(s)
        offsides_std:
            Standard deviation of the distance (in z) of each offsides
            point from the snowline.  Smaller is better.  This is not
            a perfect metric of quality of fit.  But it IS independent
            of the area of the region (most of which might be far from
            the snowline)
    """

    # Overlap by union of polygons in outline_shp
    poly_ds = gdalutil.open(outline_shp, driver='ESRI Shapefile')
    poly_raster = gdalutil.rasterize_polygons(poly_ds, grid_info)


    # Include only pixels inside the polygon
    cls = np.copy(cls0)
    cls[np.logical_not(poly_raster)] = OCEAN

    # Get snowline
    offsides_fn = _Offsides(cls, ele)
    if offsides_fn.icez.shape[0]==0 or offsides_fn.snowz.shape[0]==0:
        return {'snowline_z': np.nan, 'offsides_std': np.nan}

    bounds = (offsides_fn.snowz[0], offsides_fn.icez[-1])
    opt = scipy.optimize.minimize_scalar(
        lambda x: sum(list(offsides_fn(x))),
        bounds=bounds, method='bounded')
    of = offsides_fn

    # Measure quality by standard deviation of distance of each
    # offside gridcell from the snowline.
    ice_of,snow_of = offsides_fn(opt.x)

    points = np.concatenate((
        offsides_fn.icez[len(offsides_fn.icez)-ice_of:],
        offsides_fn.snowz[:snow_of]))
    std = 0 if len(points) == 0 else np.std(points)

    return {'snowline_z': opt.x, 'offsides_std': std}


def snowline_by_region(elev_tif, class_tif, outlines_shp, shp_filter_fn):
    """
    elev_tif: GeoTIFF file
        Elevations file
    class_tif: GeoTIFF file
        Surface classification file
            SNOW = 0
            ICE = 1
            CLOUD = 2
            OCEAN = 3
    outlines_shp:
        Shapefile containing multiple region outlines
    shp_filter_fn: function: (dict) -> bool
        Function to be run on record from shapefile reader.
        Returns True if we wish to use this region.
    Yields: dict
        Metadata obtained from outlines_shp, PLUS:
        snowline_z:
            Snowline for the region
        offsides_std:
            Measure of quality for the snowline (smaller is better)
        
    """

    with ioutil.TmpDir() as tdir:

        # Convert GeoTIFF to NetCDF
        elev_nc = tdir.filename(suffix='.nc')
        gdal.Translate(elev_nc, elev_tif, format='NetCDF')
        grid_info = gdalutil.FileInfo(elev_nc)

        # Read the input GeoTIFF files
        class0 = geotiffutil.read(class_tif, 1)
        elev = geotiffutil.read(elev_tif, 1)

        for fid,rec in enumerate(shputil.read(outlines_shp, read_shape=False)):
            if not shp_filter_fn(rec):
                continue

            with tdir.subdir() as tdir2:
                # Create a shapefile with just a single shape
                outline_shp = tdir2.join('outline.shp')
                shputil.select_feature(outlines_shp, fid, outline_shp)

                rec.update(get_snowline(
                    class0, elev, grid_info, outline_shp))

                yield rec

def main():
    elev_tif = 'velocities_data/snowline/DEMMODIS_GIMP.tif'
    class_tif = 'velocities_data/snowline/20120715_classification.tif'
    outlines_shp = 'velocities_data/GreenlandDrainageBasins/GRE_Basins_IMBIE2_v1.3.shp'
# #    outlines_shp = 'velocities_data/GreenlandGlacierBasins/Greenland_Basins_PS_v1.4.2ext.shp'

#    elev_tif = '/home/raf/Documents/Columbia/Research/Albedo/Data/GIMP_DEM/DEMMODIS_GIMP.tif'
#    class_tif = '/home/raf/Documents/Columbia/Research/Albedo/20120715_classification.tif'
#    outlines_shp = '/home/raf/Documents/Columbia/Research/Albedo/Data/IMBIE/GRE_Basins_IMBIE2_v1.3/GRE_Basins_IMBIE2_v1.3.shp'

    for rec in snowline_by_region(elev_tif, class_tif, outlines_shp,
        lambda rec: rec['SUBREGION1'] != 'ICE_CAP'):
        print(rec)

main()
