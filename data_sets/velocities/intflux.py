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
import scipy.interpolate

GlacierInfo = collections.namedtuple('GlacierInfo', (
    'nsidc_name',            # Code used in NSDIC-0481 dataset
    'fluxgate_name',        # Name within the fluxgate file
))

glaciers = (
    GlacierInfo('W69.10N', 'Jakobshavn Isbræ'),
)

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
    for vel in (vx,vy):

        spline = scipy.interpolate.RectBivariateSpline(
            x,y, vel,
            kx=1, ky=1, grid=True)    # 1st degree bivariate spline (linear interpolation)
        data_at_points = spline(fluxgate.x, fluxgate.y)
        vxy.append(data_at_points)

    # Inner product interpolated velocity field with fluxgate normal vectors
    return sum(vxy[0]*fluxgate.nx) + sum(vxy[1]*fluxgate.ny)
# -----------------------------------------------------------------------
def intflux(raster_path_pat, fluxgates_path, glaciers):

    # Read the project from any one of our input files
    with netCDF4.Dataset(raster_path_pat.format(
        grid=glaciers[0].nsidc_name)) as nc:
        proj = pyproj.Proj(pypismtools.get_projection_from_file(nc))

    # Load the flux gates (profiles)
    fluxgates = {prof.name : prof for prof in
        extract_profiles.load_profiles(fluxgates_path, projection=proj, flip=False)}

    # Read the fluxgates based on that projection
    for gl in glaciers:
        fluxgate = fluxgates[gl.fluxgate_name]

        with netCDF4.Dataset(raster_path_pat.format(
            grid=glaciers[0].nsidc_name)) as nc:

            # Read the grid; doesn't matter which file they are both the same
            xx = nc.variables['x'][:]
            yy = nc.variables['y'][:]
            times = nc.variables['time'][:]

            for time_ix in range(0,len(times)):
                vx = nc.variables['vx'][time_ix,:,:].transpose()
                vy = nc.variables['vy'][time_ix,:,:].transpose()
                print(vx.shape)

                flux = flux_across_gate(fluxgate, xx, yy, vx, vy)
                yield (times[time_ix], gl.nsidc_name, flux)


def main():
    # Read a shapefile
    for x in intflux(
        os.path.join('outputs', 'TSX_{grid}_2008_2020.nc'),
        os.path.join(os.environ['HARNESS'], 'gris-analysis', 'flux-gates', 'greenland-flux-gates-29.shp'),
        glaciers):

        print(x)

main()
