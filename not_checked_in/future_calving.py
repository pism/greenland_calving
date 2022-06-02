import numpy as np
import pandas as pd
from uafgi import make,cfutil,glacier,gdalutil,ncutil,pdutil
from uafgi.pism import pismutil,flow_simulation
import uafgi.data
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
import uafgi.data.itslive as d_itslive
import os
import datetime
import netCDF4

pd.set_option('display.max_columns', None)


# Load data...
select = pd.read_pickle(uafgi.data.join_outputs('stability', '03_select.df'))
w21x = pd.read_pickle('w21x.df')

# Choose a glacier to look at (will put in a loop later)
dfs = list()
for ix,row in select.iterrows():
    data_fname = row['w21_data_fname']

    # Get base Wood et al data
    df = d_w21.glacier_rate_df(data_fname)
    df = df.reset_index()

    # Add our own sigma / flux calculations to it
    for vsource,Merger,y0,y1 in (
        ('w21', d_itslive.W21Merger,2011,2020),
        ('its', d_itslive.ItsliveMerger,2011,2019)):

        aflux_vs = 'aflux_'+vsource
        sflux_vs = 'sflux_'+vsource
        sigma_max_vs = 'sigma_max_'+vsource

        adv = flow_simulation.flow_rate2(row, w21x, Merger, y0, y1)
        if len(adv) == 0:
            continue

        # Convert [km y-1] to [m y-1]
        adv['aflux'] = adv['aflux'] * .001
        adv['sflux'] = adv['sflux'] * .001


        adv = adv.rename(columns={'aflux':'aflux_'+vsource, 'sflux':sflux_vs})
        df = pdutil.merge_nodups(df, adv, left_on='time', right_on='year', how='left').drop('year',axis=1)

        # Scale by difference in our velocity flux vs. Wood et al, 1km upstream
        df['sflux1_'+vsource] = df[sflux_vs] * df['ice_advection'] / df[aflux_vs]
        # Solve for sigma_max
        df[sigma_max_vs] = (df[sflux_vs] * df['ice_advection']) / (df[aflux_vs] * -df['calving'])

        # Remove extraneous column
        df = df.drop('velocity_source', axis=1)

    dfs.append(df)

df = pd.concat(dfs)
df = df.dropna()    # Only keep rows with our computed sigma_max
df.to_csv('w21x.csv')
df.to_pickle('w21x.df')
