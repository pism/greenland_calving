import os
import itertools
from uafgi import make,glacier
import sys
sys.path.append('.')
import data
from uafgi.data import itslive
import datetime

def main():
    odir = 'outputs'

    # Create a blank makefile
    makefile = make.Makefile()
    # Things we want to keep

    # Merge the velocities into a single file
    grid = 'W69.10N'
    grid_file = 'velocities_data/measures/grids/{}_grid.nc'.format(grid)
    rule = itslive.merge_to_pism_rule(grid, itslive.W21Merger,
        datetime.datetime(2011,1,1), datetime.datetime(2020,1,1))
    targets = makefile.add(rule)


    print('Inputs ',rule.inputs)
    print('Outputs ',rule.outputs)

    # Build the outputs of that rule
    make.build(makefile, targets)


main()
