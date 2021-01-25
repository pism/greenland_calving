import os
import itertools
from uafgi import make,glaciers
import uafgi.nsidc.nsidc0481
import sys
sys.path.append('.')
import data
from uafgi import itslive

def main():
    odir = 'outputs'

    # Create a blank makefile
    makefile = make.Makefile()
    # Things we want to keep

    # Merge the velocities into a single file
    grid = 'W69.10N'
    grid_file = 'outputs/{}-grid.nc'.format(grid)
    rule = itslive.merge_to_pism_rule(grid, grid_file,
        'data/itslive/GRE_G0240_{}.nc', range(2011,2019), 'outputs')
    targets = makefile.add(rule)

    # Build the outputs of that rule
    make.build(makefile, targets)


main()
