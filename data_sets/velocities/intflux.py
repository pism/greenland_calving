import os
import collections
import ogr
import netCDF4
from pypismtools import pypismtools
from pypismtools.scripts import extract_profiles
import pyproj
from giss import memoize
import importlib
flux_gate_analysis = importlib.import_module('gris-analysis.flux-gates.flux-gate-analysis')
DATA_DIR = os.path.join(os.environ['HOME'], 'data')
VELOCITIES = 'outputs/TSX_W69.10N_vx_merged.nc'


GlacierInfo = collections.namedtuple('GlacierInfo', (
    'nsidc',            # Code used in NSDIC-0481 dataset
    'fluxgate',        # Name within the fluxgate file
))

glaciers = (
    GlacierInfo('W69.10N', 'Jakobshavn Isbræ'),
)

GREENLAND_FLUX_GATES = os.path.join(os.environ['HARNESS'], 'gris-analysis', 'flux-gates', 'greenland-flux-gates-29.shp')


def flux_across_gate(fluxgate, x, y, vx, vy):
    """
    A dict, giutil.LazyDict or giutil.LambdaDict with the following keys:
    'fluxgate':
        The loaded profile of this fluxgate (from shapefile)
    'x':
        X coordinates of grid
    'y':
        Y coordinates of grid
    ('vx', 'velocity'):
        x coordinate of glacier surface flow velocity
    ('vy', 'velocity'):
        y coordinate of glacier surface flow velocity
    """

    # Obtain interpolated velocity fields, evaluated at flux gate points
    vxy = list()
    for vname in ('vx', 'vy'):

        spline = scipy.interpolate.RectBivariateSplit(
            vals['x'], vals['y'], vals[(vname, 'velocity')],
            1, 1)    # 1st degree bivariate spline (linear interpolation)
        data_at_points = spline(fluxgate.x, fluxgate.y)
        vxy.append(data_at_points)

    # Inner product interpolated velocity field with fluxgate normal vectors
    return sum(vxy[0]*fluxgate.nx) + sum(vxy[1]*fluxgate.ny)
# -----------------------------------------------------------------------
def intflux(pathx, pathy, fluxgates):
    with netCDF4.Dataset(path_vx) as ncx:
        with netCDF4.Dataset(path_vy) as ncy:
            # Read the grid; doesn't matter which file they are both the same
            xx = ncx.variables['x'][:]
            yy = ncx.variables['y'][:]
            times = nc.variables['time'][:]

            for time_ix in range(0,len(times)):
                vx = ncx.variables['vx'][time_ix,:,:]
                vy = ncy.variables['vy'][time_ix,:,:]

                for fluxgate in fluxgates:
                    flux = flux_across_gate(fluxgate, x, y, vx, vy)
                    yield (times[time_ix], fluxgate.name, flux_across_gat


def intflux(raster_dir, source, grid, fluxgates):
    """
    fluxgates:
        List of fluxgate Profiles over which to integrate
    """

    vals = giutil.LambdaDict()
    for parameter in ('vx', 'vy'):
        os.path.join(raster_dir, '{}_{}_{}_merged.nc'.format(source, grid, parameter))
        vals.lazy[('vx', 'velocity')] = lambda: 
$$$


@memoize.local()
def get_proj():
    """Gets the (single) projection used for all glaciers in this project.
    Do so by looking into a single file for a single glacier; assuming all are the same."""
    gl = glaciers[0]    # Pick a glacier, any glacier

    # Obtain a projection from the raster file
    raster_path_fmt = os.path.join('outputs', 'TSX_{}_{}_merged.nc')
    with netCDF4.Dataset(raster_path_fmt.format(gl.nsidc, 'vx')) as nc:
        return pyproj.Proj(pypismtools.get_projection_from_file(nc))

@memoize.local()
def get_fluxgates(**kwargs):
    """Loads the flux gate profiles
    Kwargs include:
    flip:
        Flip the direction of the fluxgate?"""
    proj = get_proj()
    return {prof.name : prof for prof in
        extract_profiles.load_profiles(GREENLAND_FLUX_GATES, projection=proj, **kwargs)}


def do_glacier(gl, pfile):
    fluxgate = get_fluxgates(flip=False)[gl.fluxgate]    # Type: Profile
    print(type(fluxgate))
    pfile = dict(pfile_base.items())

    # Obtain interpolated velocity fields, evaluated at flux gate points
    vxy = list()
    for vname in ('vx', 'vy'):
        ncpath = os.path.join('outputs', '{}_{}_{}_merged.nc'.format(pfile['source'], pfile['grid'], vname))

        with netCDF4.Dataset(ncpath, 'r') as nc:
            # get the dimensions (string names)
            xsdim, ysdim, zsdim, tsdim = pypismtools.get_dims(nc)

            # Read the grid
            xx = nc.variables[xsdim][:]
            yy = nc.variables[ysdim][:]

            # Read the data.  NOTE: NetCDF file is data(y,x)
            data = nc.variables[vname][:].transpose()

        spline = scipy.interpolate.RectBivariateSplit(
            x, y, data,
            1, 1)    # 1st degree bivariate spline (linear interpolation)
        data_at_points = spline(fluxgate.x, fluxgate.y)
        vxy.append(data_at_points)

    # Inner product interpolated velocity field with fluxgate normal vectors
    return sum(vxy[0]*fluxgate.nx) + sum(vxy[1]*fluxgate.ny)





get_data('vx', 

'x'
'y'
('vx', 'data')
('vy', 'data')























def main():
    # Read a shapefile
    do_glacier(glaciers[0])
    return

main()
