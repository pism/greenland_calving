import numpy as np
import pandas as pd
from uafgi import gdalutil,bedmachine,glacier,make
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
def render_bedmachine_makefile(select):
    """Given a Glacier selection, creates a Makefile to create all the
    localized BedMachine files required for it."""

    makefile = make.Makefile()

    # Make the global BedMachine file (compressed, for PISM)
    makefile.add(bedmachine_global_rule())

    # Make the localized BedMachine extracts
    targets = list()
    for grid in select['ns481_grid']:
        rule = bedmachine_local_rule(grid)
        makefile.add(rule)
        targets.append(rule.outputs[0])

    # Convert the ItsLive files
    for grid in select['ns481_grid']:
        # Localize the ItsLive file
        rule = uafgi.data.itslive.merge_to_pism_rule(grid,
            uafgi.data.itslive.ItsliveMerger,
            datetime.datetime(2011,1,1), datetime.datetime(2019,1,1))

        makefile.add(rule)
        targets.append(rule.outputs[0])

        # Compute von Mises stress for it
        rule = flow_simulation.compute_sigma_rule(
            rule.outputs[0], uafgi.data.join_outputs('itslive'))
        makefile.add(rule)
        targets.append(rule.outputs[0])

    # Convert the Wood 2021 velocity files
    for grid in select['ns481_grid']:
        # Localize the Wood 2021 velocity file
        rule = uafgi.data.itslive.merge_to_pism_rule(grid,
            uafgi.data.itslive.W21Merger,
            datetime.datetime(2011,1,1), datetime.datetime(2020,1,1))

        makefile.add(rule)
        targets.append(rule.outputs[0])

        # Compute von Mises stress for it
        rule = flow_simulation.compute_sigma_rule(
            rule.outputs[0], uafgi.data.join_outputs('wood2021', 'velocities'))
        makefile.add(rule)
        targets.append(rule.outputs[0])



    makefile.generate(targets, '02_extract_bedmachine.mk')

def main():
    select = pd.read_pickle(uafgi.data.join_outputs('stability', '01_select.df'))
    render_bedmachine_makefile(select)
    print('Finished rendering Makefile.\n    Run with ./02_extract_bedmachine.mk/make')

main()
