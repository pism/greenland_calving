import os
import itertools
from uafgi import make,glaciers
import uafgi.nsidc.nsidc0481
import sys
sys.path.append('.')
import data


def main():
    odir = 'outputs'

    # Create a blank makefile
    makefile = make.Makefile()
    # Things we want to keep
    outputs = []

    # Merge the velocities into a single file
#    filter_attrs=dict(source='TSX', grid='W69.10N')
#    rule = glaciers.merge(makefile, 'data', odir,
    filter_attrs=dict(source='TSX', grid='E61.10N')
    rule = glaciers.merge(makefile, 'E61.10N', uafgi.nsidc.nsidc0481.parse, odir,
        os.path.join(odir, '{source}_{grid}_2008_2020.nc'),
        ('vx','vy'),
        #max_files=3,
        filter_attrs=filter_attrs,
        blacklist=data.blacklist).rule

    # Convert to PISM format
    rule = glaciers.fixup_velocities_for_pism(makefile, rule.inputs[0], odir).rule
    velocity_file = rule.outputs[0]
    outputs.append(velocity_file)


    # Build the outputs of that rule
    make.build(makefile, outputs)

    # Remove intermediate files
    make.cleanup(makefile, rule.outputs)


main()
