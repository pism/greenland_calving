import numpy as np
import pandas as pd
from uafgi import gdalutil,bedmachine,glacier,make,pdutil
import uafgi.wkt
import uafgi.data
import uafgi.data.ns642
import uafgi.data.itslive
from uafgi.pism import flow_simulation
import datetime

"""Set up bedmachine files --- both global and local --- as required
for our experiment."""


def bedmachine_global_rule():
    """Creates a compressed global BedMachine file, suitable for use with PISM"""
    def action(tdir):
        from uafgi import bedmachine
        import uafgi.data

        bedmachine.fixup_for_pism(uafgi.data.BEDMACHINE_ORIG, uafgi.data.BEDMACHINE_PISM, tdir)

    return make.Rule(
        action,
        [uafgi.data.BEDMACHINE_ORIG],
        [uafgi.data.BEDMACHINE_PISM])

def bedmachine_local_rule(ns481_grid):
    """Creates a localized BedMachine file for a MEASURES grid"""
    ifname = uafgi.data.measures_grid_file(ns481_grid)
    ofname = uafgi.data.bedmachine_local(ns481_grid)

    def action(tdir):
        from uafgi import cdoutil
        import uafgi.data

        cdoutil.extract_region(
            uafgi.data.BEDMACHINE_PISM, ifname,
            ['thickness', 'bed'],
            ofname, tdir)

    return make.Rule(
        action,
        [uafgi.data.BEDMACHINE_PISM, uafgi.data.measures_grid_file(ns481_grid)],
        [ofname])

# -------------------------------------------------------------
def gimpdem_local_rule(ns481_grid):
    """Creates a localized GIMP DEM file for a MEASURES grid"""

    ifname = uafgi.data.measures_grid_file(ns481_grid)
    ofname = uafgi.data.gimpdem_local(ns481_grid)
    gimpdem_tif = uafgi.data.join('gimpdem-nsidc0645', 'gimpdem_90m_v01.1.tif')

    def action(tdir):
        import uafgi.data
        from uafgi import gdalutil
        import subprocess

        os.makedirs(os.path.dirname(ofname), exist_ok=True)

        grid_file = uafgi.data.measures_grid_file(ns481_grid)
        fb = gdalutil.FileInfo(grid_file)

        cmd = ['gdal_translate',
            '-r', 'average',
            '-projwin', str(fb.x.low), str(fb.y.high), str(fb.x.high), str(fb.y.low),
            '-tr', str(fb.x.delta), str(fb.y.delta),
            gimpdem_tif,
            ofname]

        subprocess.run(cmd, check=True)

        cmd = ['ncrename', '-v', 'Band1,elevation', ofname]
        subprocess.run(cmd, check=True)


    return make.Rule(
        action,
        [gimpdem_tif, ifname],
        [ofname])

# -------------------------------------------------------------
MAKEDIR = './b01_compute_sigma.mk'
def render_bedmachine_makefile(select):
    """Given a Glacier selection, creates a Makefile to create all the
    localized BedMachine files required for it."""

    makefile = make.Makefile()

    # Make the global BedMachine file (compressed, for PISM)
    makefile.add(bedmachine_global_rule())

    targets = list()

    # Sigma on ITS-LIVE Files
    for grid in select['ns481_grid']:
        # Localize the ItsLive file
        rule = uafgi.data.itslive.merge_to_pism_rule(grid,
            uafgi.data.itslive.ItsliveMerger,
            datetime.datetime(1985,1,1), datetime.datetime(2019,1,1))

        # This was already done, we just constructed the Rule to get an output file
        #makefile.add(rule)
        #targets.append(rule.outputs[0])

        # Compute von Mises stress for it
        rule = flow_simulation.compute_sigma_rule(
            rule.outputs[0], uafgi.data.join_outputs('itslive', 'sigma'))
        makefile.add(rule)
        targets.append(rule.outputs[0])

    # Sigma on Wood 2021 Velocity Files
    for grid in select['ns481_grid']:
        # Localize the Wood 2021 velocity file
        rule = uafgi.data.itslive.merge_to_pism_rule(grid,
            uafgi.data.itslive.W21Merger,
            datetime.datetime(2011,1,1), datetime.datetime(2020,1,1))

        #makefile.add(rule)
        #targets.append(rule.outputs[0])

        # Compute von Mises stress for it
        rule = flow_simulation.compute_sigma_rule(
            rule.outputs[0], uafgi.data.join_outputs('wood2021', 'velocities'))
        makefile.add(rule)
        targets.append(rule.outputs[0])



    makefile.generate(targets, MAKEDIR, python_exe='python')

def main():
    #select = pd.read_pickle(uafgi.data.join_outputs('stability', '01_select.df'))
    select = pdutil.ExtDf.read_pickle(uafgi.data.join_outputs('stability', '01_select.dfx'))
    render_bedmachine_makefile(select.df)
    print(f'Finished rendering Makefile.\n    Run with {MAKEDIR}/make')

    cmd = [os.path.join(MAKEDIR, 'make')]
    subprocess.run(cmd, check=True)

main()
