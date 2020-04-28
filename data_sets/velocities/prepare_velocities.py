from netCDF4 import Dataset as NC
from cdo import Cdo
cdo = Cdo()
from datetime import datetime, timedelta
from osgeo import gdal
from glob import glob
import os.path
import time
import collections,re,sys
import gc
import netCDF4
import numpy as np
import csv
from giss import ioutil,iopfile,nsidc,cdoutil

reftime = "2008-01-01"
components = ["vx", "vy", "vv"]
download_dir = "data"

# These are files for which domain_checksum2() == 0
blacklist_raw = (
    'TSX_W69.10N_02Jun18_13Jun18_09-48-58_{parameter}_v02.0{ext}',
    'TSX_W69.10N_29May15_20Jun15_09-48-37_{parameter}_v02.0{ext}',
    'TSX_W69.10N_31May14_11Jun14_09-48-32_{parameter}_v02.0{ext}',
    'TSX_W69.10N_03Jul09_14Jul09_09-48-07_{parameter}_v02.0{ext}',
    'TSX_W69.10N_13Jun18_05Jul18_09-48-58_{parameter}_v02.0{ext}',
    'TSX_W69.10N_05Jul18_27Jul18_09-49-00_{parameter}_v02.0{ext}',
    'TSX_W69.10N_26May16_17Jun16_09-48-43_{parameter}_v02.0{ext}',
    'TSX_W69.10N_18Jul17_09Aug17_09-48-53_{parameter}_v02.0{ext}',
    'TSX_W69.10N_16Jul13_18Aug13_09-48-29_{parameter}_v02.0{ext}',
    'TSX_W69.10N_30Apr18_02Jun18_09-48-57_{parameter}_v02.0{ext}',
    'TSX_W69.10N_10Nov15_21Nov15_09-48-42_{parameter}_v02.0{ext}',
    'TSX_W69.10N_23Aug11_14Sep11_09-48-21_{parameter}_v02.0{ext}',
    'TSX_W69.10N_18Sep09_29Sep09_09-48-11_{parameter}_v02.0{ext}',
    'TSX_W69.10N_28Apr09_09May09_09-48-04_{parameter}_v02.0{ext}',
    'TSX_W69.10N_09Sep18_20Sep18_09-49-03_{parameter}_v02.0{ext}',
    'TSX_W69.10N_30Jan09_10Feb09_09-48-02_{parameter}_v02.0{ext}',
    'TSX_W69.10N_06Feb11_28Feb11_09-48-12_{parameter}_v02.0{ext}',
    'TSX_W69.10N_21Apr12_02May12_09-48-19_{parameter}_v02.0{ext}',
    'TSX_W69.10N_10Feb14_21Feb14_09-48-29_{parameter}_v02.0{ext}',
    'TSX_W69.10N_23Nov14_04Dec14_09-48-46_{parameter}_v02.0{ext}',
    'TSX_W69.10N_25Aug10_05Sep10_09-48-16_{parameter}_v02.0{ext}',
    'TSX_W69.10N_21Nov10_02Dec10_09-48-17_{parameter}_v02.0{ext}',
    'TSX_W69.10N_14Feb17_25Feb17_09-48-47_{parameter}_v02.0{ext}',
    'TSX_W69.10N_18May15_29May15_09-48-36_{parameter}_v02.0{ext}',
    'TSX_W69.10N_04Feb12_15Feb12_09-48-17_{parameter}_v02.0{ext}',
    'TSX_W69.10N_19Apr18_30Apr18_09-48-57_{parameter}_v02.0{ext}',
    'TSX_W69.10N_21Jul11_01Aug11_09-48-19_{parameter}_v02.0{ext}',
    'TSX_W69.10N_12Feb13_23Feb13_09-48-22_{parameter}_v02.0{ext}',
    'TSX_W69.10N_24Apr11_05May11_09-48-14_{parameter}_v02.0{ext}',
    'TSX_W69.10N_26Apr10_07May10_09-48-11_{parameter}_v02.0{ext}',
    # Right domain but Missing a LOT
    'TSX_W69.10N_03Jul19_25Jul19_20-42-06_{parameter}_v02.0{ext}',
    'TSX_W69.10N_10Sep17_02Oct17_10-06-06_{parameter}_v02.0{ext}', 
)

def get_blacklist(**kwargs):
    return set(x.format(**kwargs) for x in blacklist_raw)

# --------------------------------------------------------------
# https://stackoverflow.com/questions/11144513/cartesian-product-of-x-and-y-array-points-into-single-array-of-2d-points
def np_cartesian_product(x,y):
    xx = np.transpose(np.tile(x, (len(y),1)))
    yy = np.tile(y, (len(x),1))
    ret = xx+yy
    return ret

def domain_checksum1(time_ncfile, parameter):
    with netCDF4.Dataset(time_ncfile) as nc:
        ncvar = nc.variables[parameter]
        var = ncvar[0,:,:]
        FillValue = ncvar._FillValue

    weights = np_cartesian_product(
        np.array([float(j) for j in range(0,var.shape[0])]),
        np.array([float(i) for i in range(0,var.shape[1])]))
    mask = np.not_equal(var, FillValue)

    return np.sum(np.sum(weights*mask))

def in_rectangle(xx, yy):
    def fn(pf):
        with netCDF4.Dataset(pf.path) as nc:
            ncvar = nc.variables[pf['parameter']]
            var = ncvar[0,:,:]
            FillValue = ncvar._FillValue

        mask = np.zeros(var.shape)
        mask[xx[0]:xx[1],yy[0]:yy[1]] = 1

        exist = np.not_equal(var, FillValue)

        return np.sum(np.sum(exist*mask)) > 0
    return fn


# --------------------------------------------------------------


# --------------------------------------------------------------
def merge_glacier(idir, odir, ofpattern, parameters, filter_nc_fn, max_files=99999999, all_files=None, **attrs0):
    """attrs should contain soure, grid
    ofpattern:
        Eg: '{source}_{grid}_2008_2020.nc'
    """
    os.makedirs(odir, exist_ok=True)

    # for parameter in ('vx', 'vy', 'vv'):
    ofnames = []
    mergefiles = list()
    for parameter in parameters:
        # Convert GeoTIFF to NetCDF
        attrs = dict(attrs0.items())
        attrs['parameter'] = parameter
        attrs['ext'] = '.tif'

        # Get list of .tif files
        pfiles_tif = iopfile.listdir(idir, nsidc.parse_0481,
            iopfile.filter_attrs(attrs))

        # Start a new mergefile
        merge_path = os.path.join(
            odir, '{source}_{grid}_{parameter}_merged.nc'.format(**attrs))
        mergefiles.append(merge_path)
        if all_files is not None:
            all_files.append(merge_path)


        if os.path.exists(merge_path):
            continue

#        try:
#            os.remove(merge_path)
#        except FileNotFoundError:
#            pass

        # Go through each file
        pfiles_nc = list()
        blacklist = get_blacklist(**attrs)
        for ix,pf_tif in enumerate(pfiles_tif):

            # Don't iterate over blacklisted items
            if pf_tif.leaf in blacklist:
                continue

            print('{}: {}'.format(ix, pf_tif.path))

            # Cut it off early
            if ix >= max_files:
                break

            # Convert to NetCDF
            pf_nc = nsidc.tiff_to_netcdf(pf_tif, odir, all_files=all_files, reftime=reftime)

#            # Determine if it covers Jakobshavn
#            if not filter_nc_fn(pf_nc):
#                continue

            # Save for later
            pfiles_nc.append(pf_nc)


        # Merge into the mergefile
        if not os.path.exists(merge_path):
            cdoutil.large_merge(
                cdo.mergetime,
                input=[x.path for x in pfiles_nc],
                output=merge_path, options="-f nc4 -z zip_2",
                max_merge=50)


    # Create the final merged file
    print(mergefiles)
    cdo.merge(
        input=mergefiles,
        output=ofpattern.format(**attrs0),
        options="-f nc4 -z zip_2")

#print(domain_checksum('outputs/TSX_W69.10N_03Mar09_14Mar09_10-05-12_vx_v02.0.nc', 'vx'))

#sys.exit(0)

all_files = list()
merge_glacier('data', 'outputs', os.path.join('outputs', '{source}_{grid}_2008_2020.nc'),
    ('vx','vy',), source='TSX', grid='W69.10N',
    filter_nc_fn = in_rectangle((373,413),(387,439)),
    all_files=all_files,
    max_files=10000)

#    ('vx', 'vy', 'vv'), source='TSX', grid='W69.10N')
