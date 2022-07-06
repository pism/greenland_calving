import os,subprocess
import numpy as np
import pandas as pd
from uafgi.util import pdutil#,gdalutil
from uafgi.util import make
#from uafgi import bedmachine,glacier    # from greenland_calving repo
import uafgi.data
import uafgi.data.ns642
import uafgi.data.itslive
import datetime

"""Set up bedmachine files --- both global and local --- as required
for our experiment."""


# -------------------------------------------------------------
MAKEDIR = './a04_localize_itslive.mk'
def render_bedmachine_makefile(select):
    """Given a Glacier selection, creates a Makefile to create all the
    localized BedMachine files required for it."""

    makefile = make.Makefile()

    targets = list()
    # Localize the ItsLive files
    for grid in select['ns481_grid']:
        # Localize the ItsLive file
        rule = uafgi.data.itslive.merge_to_pism_rule(grid,
            uafgi.data.itslive.ItsliveMerger,
            datetime.datetime(1985,1,1), datetime.datetime(2019,1,1))

        makefile.add(rule)
        targets.append(rule.outputs[0])

#    # Make the localized GimpDEM extracts
#    for grid in select['ns481_grid']:
#        rule = gimpdem_local_rule(grid)
#        makefile.add(rule)
#        targets.append(rule.outputs[0])



    makefile.generate(targets, MAKEDIR, python_exe='python')

def main():
    #select = pd.read_pickle(uafgi.data.join_outputs('stability', '01_select.df'))
    select = pdutil.ExtDf.read_pickle(uafgi.data.join_outputs('stability', '01_select.dfx'))
    render_bedmachine_makefile(select.df)
    print(f'Finished rendering Makefile.\n    Run with {MAKEDIR}/make')

    cmd = [os.path.join(MAKEDIR, 'make')]
    subprocess.run(cmd, check=True)

main()
