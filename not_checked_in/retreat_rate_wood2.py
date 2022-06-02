import numpy as np
import pandas as pd
from uafgi import make,cfutil,glacier,gdalutil,ncutil
from uafgi.pism import pismutil,flow_simulation
import uafgi.data
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
import uafgi.data.itslive as d_itslive
import os
import datetime
import netCDF4


# Load data...
select = pd.read_pickle(uafgi.data.join_outputs('stability', '03_select.df'))
w21t = d_w21.read_termini(uafgi.data.wkt.nsidc_ps_north).df

# Select data
#select = select[select.w21t_key == 'Store']   ## DEBUG


# Choose a glacier to look at (will put in a loop later)
dfs = list()
for ix,row in select.iterrows():
    #row = select.iloc[0].to_dict()
    print(select['w21_key'])
    #row = select.iloc[13].to_dict()  ### DEBUG
    print(list(row.keys()))
    print('Glacier: {}'.format(row['w21_key']))

    dfs.append(flow_simulation.flow_rate2(row, w21t, d_itslive.ItsliveMerger, 2011, 2019))
    dfs.append(flow_simulation.flow_rate2(row, w21t, d_itslive.W21Merger, 2011, 2020))


df = pd.concat(dfs).sort_values(by=['w21t_key', 'year', 'velocity_source'])
df.to_csv('advance.csv')
df.to_pickle('advance.df')

