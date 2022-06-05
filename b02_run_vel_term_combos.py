import os
import datetime
import pandas as pd
import scipy.interpolate
from uafgi import dtutil, pdutil
from uafgi.pism import flow_simulation
import uafgi.data.fj
import uafgi.data.future_termini
import uafgi.data.wkt
import netCDF4
import cf_units
import numpy as np

"""Run this after 02_xxxxx.py"""

def _isnull(x):
    return isinstance(x, float) and np.isnan(x)

map_wkt = uafgi.data.wkt.nsidc_ps_north


# Read future termini; and convert one row per fjord
uafgi.data.fj.read(map_wkt).df
ft = uafgi.data.future_termini.read(map_wkt)
ftt = pdutil.group_and_tuplelist(ft.df, ['fj_fid'],
    [ ('ft_termini', ['ft_terminus']) ])

# Read our glacier list; add in list of future termini (ft_termini)
select = pdutil.ExtDf.read_pickle(uafgi.data.join_outputs('stability/01_select.dfx'))
select.df = pdutil.merge_nodups(select.df, ftt, on='fj_fid', how='left')

# For each glacier...
for ix,selrow in select.df.iterrows():

#    # DEBUGGING
#    if selrow.w21t_Glacier != 'Hayes SS':
#        continue
    print('=== Termini for glacier: {} {}'.format(selrow.ns481_grid, selrow.w21t_Glacier))

    # Determine velocity file (and sigma and BedMachine) for this glacier
    tpl = uafgi.data.join_outputs('itslive', 'sigma', 'GRE_G0240_{}_1985_2018').format(selrow.ns481_grid)
    velocity_file = tpl+'.nc'
    sigma_file = tpl+'_sigma.nc'
    bedmachine_file = uafgi.data.join_outputs('bedmachine', 'BedMachineGreenland-2017-09-20_{}.nc'.format(selrow.ns481_grid))
    

    data = list()
    
    # Integrate sigma for past termini
    date_termini = sorted(selrow.w21t_date_termini)


    # Integrate it over ALL velocity field timesteps
    print('Velocity file: {}'.format(velocity_file))
    with netCDF4.Dataset(velocity_file) as nc:

        # See if we've already done this
        ofname = uafgi.data.join_outputs('velterm', 'velterm_{:03d}.df'.format(selrow.w21t_glacier_number))
        if os.path.exists(ofname):
            print('Already exists: {}'.format(ofname))
            continue

        # Skip if no termini for this glacier
        if _isnull(selrow['ft_termini']):
            continue

        # Read the times
        nctime = nc.variables['time']
        vel_times = cf_units.Unit(nctime.units, calendar=nctime.calendar).num2date(nctime[:])

        for vel_itime,vel_time in enumerate(vel_times):
            vel_year = dtutil.year_fraction(vel_time)
            print('   vel_year = {}'.format(vel_year))

            termini = [terminus for _,terminus in date_termini]
            frs = flow_simulation.flow_rate3(selrow['ns481_grid'],
                bedmachine_file, selrow['fj_poly'],
                velocity_file,sigma_file,vel_itime, termini,
                selrow['up_loc'])

            for (date,terminus),fr in zip(date_termini,frs):
        #        data.append((None, dtutil.year_fraction(date),terminus,fr.aflux,fr.sflux,fr.up_area))
                data.append((selrow.w21t_glacier_number, vel_year, None, dtutil.year_fraction(date),None,fr.aflux,fr.sflux,fr.ncells,fr.up_area))

            # Compute for future termini
#            for k,v in selrow.items():
#                print('{}: {}'.format(k,v))

            termini = [x[0] for x in selrow.ft_termini]
            #print('xxxxxxx ', termini[0])
            frs = flow_simulation.flow_rate3(selrow['ns481_grid'],
                bedmachine_file, selrow['fj_poly'],
                velocity_file,sigma_file,vel_itime, termini,
                selrow['up_loc'])
            frs.sort(key=lambda x: -x.up_area)

            for ix,(terminus,fr) in enumerate(zip(termini,frs)):
        #        data.append((ix,2020+ix,terminus,fr.aflux,fr.sflux,fr.ncells, fr.up_area))
                data.append((selrow.w21t_glacier_number, vel_year, ix,2020+ix,None,fr.aflux,fr.sflux,fr.ncells, fr.up_area))

#            break
#            if vel_itime > 2:
#                break



        #    print(date, fr.sflux/fr.aflux, fr)
        fluxdf = pd.DataFrame(data, columns=('glacier_number', 'vel_year', 'future_index', 'term_year','terminus','aflux','sflux','ncells','up_area'))
        fluxdf['fluxratio'] = fluxdf.sflux/fluxdf.aflux


        os.makedirs(os.path.split(ofname)[0], exist_ok=True)
        fluxdf.to_pickle(ofname)

#    break
