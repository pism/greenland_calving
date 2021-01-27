import re,os
import numpy as np
import pandas as pd
import cf_units
from uafgi import ncutil,gdalutil

def read_retreat(fname):
    row = dict()
    with ncutil.open(fname) as nc:
        fb = gdalutil.FileInfo(fname)
        dyx_area = fb.dx*fb.dy

        nctime = nc.variables['time']
        times = cf_units.Unit(nctime.units, calendar=nctime.calendar).num2date(nctime[:])
        fjord = nc.variables['fjord'][:]
        thk0 = nc.variables['thk'][0,:,:]

        rows = list()
        for itime in range(0,len(times)):
            row = {'year': nc.year, 'sigma_max': nc.sigma_max, 'time': times[itime]}
            thk1 = nc.variables['thk'][itime,:,:]

            # Advance: Place starting with no ice, but now have ice
            where_advance = np.logical_and(thk0 == 0, thk1 != 0)
            where_advance[np.logical_not(fjord)] = False
            row['adv_area'] = np.sum(where_advance) * dyx_area

            # Retreat: Place starting with ice, now has no ice
            where_retreat = np.logical_and(thk0 != 0, thk1 == 0)
            where_retreat[np.logical_not(fjord)] = False
            row['ret_area'] = np.sum(where_retreat) * dyx_area

            print(row)
            rows.append(row)
    return rows
        

def main_analyze(dir, prefix, nsidc):
    str = r'{}_{}_(.*)_(.*)_retreat\.nc'.format(prefix,nsidc)
    print('Re: {}'.format(str))
    fileRE = re.compile(str)
    years = list()
    leaves = list()
    for leaf in os.listdir(dir):
        match = fileRE.match(leaf)
        if match is None:
            continue
        year = int(match.group(1))
        years.append(year)
        leaves.append(leaf)

    dfi = pd.DataFrame({'year': years, 'leaf': leaves}).sort_values(['year','leaf'])
    dfig = dfi.groupby(['year'])

    for year,dfg in dfig:
        if year <= 2014:
            continue
        print('processing ', year)
        rows = list()
        for leaf in dfg['leaf'].values:
            print('  --> ', year,leaf)
            fname = os.path.join(dir, leaf)
            rows += read_retreat(fname)

        df = pd.DataFrame(rows)
        df.to_pickle('{}_retreats_{}.pik'.format(prefix, year))
        print(df)


#main_analyze('outputs', 'GRE_G0240', r'W71\.65N')
main_analyze('outputs', 'GRE_G0240', r'W69\.10N')
