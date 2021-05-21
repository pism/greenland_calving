import numpy as np
import pandas as pd
from uafgi import make,cfutil,glacier,gdalutil,ncutil
from uafgi.pism import pismutil
import uafgi.data
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
import os
import datetime
import netCDF4





# Put in pdutil...
# https://stackoverflow.com/questions/30112202/how-do-i-find-the-closest-values-in-a-pandas-series-to-an-input-number
def find_neighbours(value, df, colname):
    exactmatch = df[df[colname] == value]
    if not exactmatch.empty:
        return exactmatch.index
    else:
        lowerneighbour_ind = df[df[colname] < value][colname].idxmax()
        upperneighbour_ind = df[df[colname] > value][colname].idxmin()
        return [lowerneighbour_ind, upperneighbour_ind]

sigma_max = 4.e5

# Load data...
select = pd.read_pickle(uafgi.data.join_outputs('stability', '03_select.df'))
w21t = d_w21.read_termini(uafgi.data.wkt.nsidc_ps_north).df

# Choose a glacier to look at (will put in a loop later)
#row = select.iloc[0].to_dict()
print(select['w21_key'])
row = select.loc[13].to_dict()
print(list(row.keys()))
print('Glacier: {}'.format(row['w21_key']))
grid = row['ns481_grid']
fjc = row['fjord_classes']
fjord = np.isin(fjc, glacier.ALL_FJORD)
up_loc = row['up_loc']

# Get termini for that
w21tx = w21t[w21t['w21t_Glacier'] == row['w21t_Glacier']].sort_values(['w21t_date'])
#['w21t_Year', 'w21t_Day_of_Yea'])


# Sample program to calculate velocity and calving rate from ItsLive
# velocities, and compare to Wood et al 2021 data.

itslive_nc = 'outputs/itslive/GRE_G0240_{}_2011_2018.nc'.format(grid)
#sigma_nc = make.opath(itslive_nc, odir, '_sigma')
sigma_nc = os.path.splitext(itslive_nc)[0] + '_sigma.nc'

target_year = 2016
target_dt = datetime.datetime(target_year, 9, 1)

with netCDF4.Dataset(itslive_nc) as nc:
    time = cfutil.read_time(nc, 'time')
    nct = nc.variables['time']
    time_bnds = cfutil.read_time(nc, 'time_bnds',
        units=nct.units, calendar=nct.calendar)

    # Fix end of range in Its-Live
    time_bnds[:,1] += datetime.timedelta(days=1)

# --------------------------------------------------------
# Figure out time index in ItsLive files
for itime_itslive in range(time_bnds.shape[0]):
    if target_dt >= time_bnds[itime_itslive,0] and target_dt < time_bnds[itime_itslive,1]:
        break

# Figure out terminus trace closest to target date
df = w21tx.copy()
df['dtdiff'] = df['w21t_date'].apply(lambda dt: abs((dt - target_dt).total_seconds()))
terminus_row = df.loc[df['dtdiff'].idxmin()]
terminus = terminus_row.w21t_terminus

# --------------------------------------------------------

# Read velocity components
with netCDF4.Dataset(itslive_nc) as nc:
    uu = nc.variables['u_ssa_bc'][itime_itslive,:]
    vv = nc.variables['v_ssa_bc'][itime_itslive,:]


# Read sigma
with netCDF4.Dataset(sigma_nc) as nc:
    sigma = nc.variables['sigma'][itime_itslive,:]
    mask = nc.variables['mask'][itime_itslive,:]

# ----------------------------------------------
# Determine the fjord
grid_info = gdalutil.FileInfo(itslive_nc)

# Cut off the fjord at our terminus
fjc = glacier.classify_fjord(fjord, grid_info, up_loc, terminus)
fjc = np.flipud(fjc)    # fjord was originally read by gdal, it is flipped u/d
fjord = np.isin(fjc, glacier.ALL_FJORD)


# Update the PISM map to reflect cut-off fjord.
#ICE_TYPES = (pismutil.MASK_GROUNDED, pismutil.MASK_FLOATING)
kill_mask = np.logical_and(np.isin(mask, pismutil.MULTIMASK_ICE), fjc==glacier.LOWER_FJORD)
mask[kill_mask] = pismutil.MASK_ICE_FREE_OCEAN

kill_mask = (mask == pismutil.MASK_ICE_FREE_OCEAN)
uu[kill_mask] = 0
vv[kill_mask] = 0

# --------------------------------------------------
u_sigma = uu * sigma
v_sigma = vv * sigma

# Compute flux across the boundary (and length of the boundary)
flux = pismutil.flux_across_terminus(mask, fjord, u_sigma, v_sigma, grid_info.dx, grid_info.dy)

# ------------------------------------------------------------------------
with netCDF4.Dataset(itslive_nc) as ncin:
    schema = ncutil.Schema(ncin)
    schema.keep_only_vars('x', 'y')

    with netCDF4.Dataset('z.nc', 'w') as ncout:
        schema.create(ncout, var_kwargs={'zlib': True})
        for vname in ('fjc', 'fjord', 'mask', 'uu', 'vv', 'flux'):
            ncout.createVariable(vname, 'd', ('y','x'))
        schema.copy(ncin, ncout)
        ncout.variables['fjc'][:] = fjc[:]
        ncout.variables['fjord'][:] = fjord[:]
        ncout.variables['mask'][:] = mask[:]
        ncout.variables['uu'][:] = uu[:]
        ncout.variables['vv'][:] = vv[:]
        ncout.variables['flux'][:] = flux[:]

tflux = np.sum(flux)
print('Mean fjord width: {}'.format(row['w21_mean_fjord_width']))


print(flux)

