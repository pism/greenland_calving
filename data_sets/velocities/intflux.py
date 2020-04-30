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
import numpy as np
import cf_units
import pickle
from giss import make
import subprocess
import pandas as pd

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
        mgy, mgx = np.meshgrid(y,x)
        spline = scipy.interpolate.RectBivariateSpline(
            x,y, vel,
            kx=1, ky=1)    # 1st degree bivariate spline (linear interpolation)
        data_at_points = spline(fluxgate.x, fluxgate.y, grid=False)
        vxy.append(data_at_points)

    # Inner product interpolated velocity field with fluxgate normal vectors
    # Normal flux (scalar) at each point in flux gate
    flux_along_profile = (vxy[0]*fluxgate.nx) + (vxy[1]*fluxgate.ny)
    return np.trapz(flux_along_profile, fluxgate.distance_from_start)
# -----------------------------------------------------------------------
class intflux(object):

    def __init__(self, makefile, glaciers, raster_paths, fluxgates_path, output):
        self.glaciers = glaciers
        self.raster_paths = raster_paths
        self.fluxgates_path = fluxgates_path
        inputs = list(raster_paths) + [fluxgates_path]
        self.rule = makefile.add(self.run, inputs, [output])

    def run(self):

        # Read the projection from any one of our input files
#        with netCDF4.Dataset(raster_path_pat.format(
#            grid=glaciers[0].nsidc_name)) as nc:
        with netCDF4.Dataset(self.raster_paths[0]) as nc:
            proj = pyproj.Proj(pypismtools.get_projection_from_file(nc))

        # Load the flux gates (profiles)
        fluxgates = {prof.name : prof for prof in
            extract_profiles.load_profiles(self.fluxgates_path, projection=proj, flip=False)}

        # Read the fluxgates based on that projection
        results = list()
        for gl,raster_path in zip(glaciers, self.raster_paths):
            fluxgate = fluxgates[gl.fluxgate_name]

#            with netCDF4.Dataset(raster_path_pat.format(
#                grid=glaciers[0].nsidc_name)) as nc:
            with netCDF4.Dataset(raster_path) as nc:

                # Read the grid; doesn't matter which file they are both the same
                xx = nc.variables['x'][:]
                yy = nc.variables['y'][:]
                times = nc.variables['time'][:]
                time_units = nc.variables['time'].units

#                for time_ix in range(0,len(times)):
                for time_ix in range(0,8):
                    vx = nc.variables['vx'][time_ix,:,:].transpose()
                    vy = nc.variables['vy'][time_ix,:,:].transpose()

                    flux = flux_across_gate(fluxgate, xx, yy, vx, vy)
                    dt = cf_units.num2date(times[time_ix], time_units, cf_units.CALENDAR_STANDARD)

                    result = (dt, gl.nsidc_name, flux)
                    print(result)
                    results.append(result)

        # Write it out
        df = pd.DataFrame(results, columns=['date', 'glacier', 'flux'])
        df.to_pickle(self.rule.outputs[0])


class epsg_profiles(object):
    def __init__(self, makefile, ipath, odir):
        idir,ileaf = os.path.split(ipath)
        iroot,ext = os.path.splitext(ileaf)
        opath = '{}_epsg3413{}'.format(iroot,ext)
        self.rule = makefile.add(self.run, (ipath,), (opath,))

    def run(self):
        cmd = ['ogr2ogr', '-t_srs', 'epsg:3413', self.rule.outputs[0], self.rule.inputs[0]]
        subprocess.run(cmd)

class sample_profiles(object):
    def __init__(self, makefile, ipath, nsamples, odir):
        self.nsamples = nsamples
        rule = epsg_profiles(makefile, ipath, odir).rule

        idir,ileaf = os.path.split(ipath)
        iroot,ext = os.path.splitext(ileaf)
        outputs = [
            os.path.join(odir, '{}_{}m{}'.format(iroot,nsamples,ext))
            for ext in ('.shp', '.shx', '.prj', '.dbf')]
        self.rule = makefile.add(self.run, [rule.outputs[0]], outputs)

    def run(self):
        cmd = ['ogr2ogr', '-t_srs', 'epsg:3413',
            '-segmentize', str(self.nsamples),
            self.rule.outputs[0], self.rule.inputs[0]]
        subprocess.run(cmd)


def main():
    makefile = make.Makefile()

    odir = 'outputs'
    r_sample_profiles = sample_profiles(
        makefile,
        os.path.join(os.environ['HARNESS'], 'gris-analysis', 'flux-gates', 'greenland-flux-gates-29.shp'),
        50, odir).rule

    raster_paths = [os.path.join(odir, 'TSX_{}_2008_2020.nc'.format(gl.nsidc_name)) for gl in glaciers]

    r_intflux = intflux(
        makefile, glaciers, raster_paths, r_sample_profiles.outputs[0],
        os.path.join(odir, 'intflux.pik')).rule


    # Outputs we want to keep
    outputs = r_sample_profiles.outputs + r_intflux.outputs
    make.build(makefile, outputs)
    # make.cleanup(makefile, outputs)


    # Print result
    df = pd.read_pickle(r_intflux.outputs[0])
    print(df)


main()
