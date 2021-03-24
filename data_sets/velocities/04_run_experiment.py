import numpy as np
import pandas as pd
from uafgi import make
import uafgi.data
from uafgi.pism import pismutil
from uafgi.pism import calving0



def run_pism_rule(row, year, sigma_max):

    # Determine the local grid
    grid = row['ns481_grid']

    ssigma_max = '{:03d}'.format(int(round(sigma_max / 1e4)))
    pname = row['w21_popular_name'].replace('.','').replace(' ','')

    ofname = uafgi.data.join_outputs(
        'stability',
        '{:03d}_{}'.format(row['ns642_GlacierID'], pname),
        'stab_{:03d}_{}_{}_{}.nc'.format(
            row['ns642_GlacierID'],
            str(year),
            ssigma_max,
            pname))

    def action(tdir, dry_run=False):
        import numpy as np
        import uafgi.data
        from uafgi.pism import flow_simulation

        grid = row['ns481_grid']
        velocity_file = uafgi.data.join_outputs('itslive', 'GRE_G0240_{}_2011_2018.nc'.format(grid))

        # Flip on Y to convert between GDAL vs. PISM conventions
        fjord_classes = np.flipud(row['fjord_classes'])

        # returns (inputs, outputs) on dry_run=True
        return flow_simulation.run_pism(
            grid, fjord_classes, velocity_file, year,
            ofname, tdir,
            row=row, dry_run=dry_run, sigma_max=sigma_max)

    inputs,outputs = action(None, dry_run=True)
    return make.Rule(action, inputs, outputs)


def main():

    makefile = make.Makefile()
    targets = list()

    sigma_maxs = list(np.arange(1e5,5.2e5,.2e5))

    select = pd.read_pickle('select_03.df')
    for year in range(2013, 2014):
        for sigma_max in (sigma_maxs[0],sigma_maxs[-1]):
            for ix,row in select.iterrows():
                rule = run_pism_rule(row, year, sigma_max)
                makefile.add(rule)
                targets.append(rule.outputs[0])

    makefile.generate(targets, '04_run_experiment.mk')

main()


