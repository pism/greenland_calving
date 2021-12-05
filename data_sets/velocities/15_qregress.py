from IPython.core.display import display, HTML
import pandas as pd
import importlib
import csv,os
import numpy as np
import pandas as pd
import itertools
import pyproj
import shapely
import copy
from uafgi import gicollections,cfutil,glacier,gdalutil,shputil,pdutil
import uafgi.data.ns642
import netCDF4
import matplotlib.pyplot as plt
import uafgi.data.wkt
import uafgi.data.w21 as d_w21

from uafgi.data import d_velterm
import uafgi.data.stability as d_stability
import scipy

import statsmodels.api
import statsmodels.formula.api
# -------------------------------------------------------------------
def _selcols(select, y0, y1):
    y_end = y1-1
    Qsg_name = f'w21_subglacial_discharge_{y0:04d}_{y_end:04d}'
    TF_name = f'w21_mean_TF_{y0:04d}-{y_end:04d}'
        
    df0 = select.df[[
        'w21t_Glacier', 'w21t_glacier_number', 'w21_coast', 'w21_mean_fjord_width',
        Qsg_name, TF_name]]
    df0 = df0.rename(columns={Qsg_name:'Qsg', TF_name:'TF'})
    df0['q4tf'] = df0['Qsg']**0.4 * df0['TF']
    df0['year0'] = float(y0)
    df0['year1'] = float(y1)
    return df0

def wood_q4tf(select):

    """Given our `select` dataset (d_stability), creates a dataframe with
    Qsd and TF by year range.  (This should really go in d_stability.py)

    Returns wdfs[] 2 dataframes:
        wdfs[0] = dataframe for glaciers in regions SE,SW,CE,CW,NE
        wdfs[1] = dataframe for glaciers in regions N,NW

    Retunred columns: 
        w21t_Glacier
        w21t_glacier_number
        w21_coast
        w21_mean_fjord_width
        Qsg:
            Subglacial discharge
        TF: [degC]
            Thermal Forcing in fjord
        q4tf:
            Qsg^.04 * TF
        year0:
            First year for which q4tf is valid
        year1:
            Last year (+1) for which q4tf is valid
    """

    dfs = list()
    for y0,y1 in ((1992,1998), (1998,2008), (2008,2018)):
        df = _selcols(select, y0,y1)
        dfs.append(df)
    df = pd.concat(dfs)

    #df0 = _selcols(select, 1992, 1998)#'w21_subglacial_discharge_1998_2007', 'w21_mean_TF_1998-2007')
    #df1 = _selcols(select, 'w21_subglacial_discharge_2008_2017', 'w21_mean_TF_2008-2017')

    #df = pd.concat((df0,df1)).sort_values('w21t_Glacier')
    # See Estimating Greenland tidewater glacier retreat driven by submarine melting (Slater et al 2019) p. 2497
    wdfs = [df[df.w21_coast.isin(['SE','SW','CE','CW','NE'])],  df[df.w21_coast.isin(['N','NW'])]]
    return wdfs

# -------------------------------------------------------------------
def read_retreats(select):
    """Reads the per-glacier Wood data files to retrieve linear retreat.
    Returns dataframe:
        year:
            Time of measurement (can be franctional year)
        up_len:
            Number gets smaller as glacier retreats; can be negative.
            This column is de-meaned
        w21t_glacier_number:
    """

    # Read year,up_len from Wood et al data
    rdfs = list()

    year_bounds = [1992,]

    for _,selrow in select.df.iterrows():
        with netCDF4.Dataset(os.path.join('data', 'wood2021', 'data', selrow['w21_data_fname'])) as nc:
            grp = nc.groups['ice_front_retreat']['discrete']
            retreat_time = grp.variables['retreat_time'][:].astype(np.float64)
            retreat = grp.variables['retreat'][:]
            retreat -= np.mean(retreat)   # Retreat is compared to average; zero point doesn't really matter
            rdf = pd.DataFrame({'year':retreat_time, 'up_len':-retreat})
            rdf['w21t_glacier_number'] = selrow.w21t_glacier_number
        rdfs.append(rdf)

    rdf = pd.concat(rdfs)
    return rdf

# -------------------------------------------------------------------

def join_retreats_q4tf(rdf,wdfs,decade_mean=True):
    """
    rdf:
        Result of read_retreats()
    wdfs:
        Result of wood_q4tf()
    mean:
        True: Average over points to give just one per decade in Wood data
        False: Give individual points

    Returns mdfs[] (rdf joined with each in wdfs):
        w21t_Glacier
        w21t_glacier_number
        year0
        year1
        year
        up_len
        w21_mean_fjord_width
        Qsg
        TF
        q4tf
    """

    mdfs = list()

    # Join rdf (year,up_len) to appropriate row of q4tf
    # https://pandas.pydata.org/pandas-docs/version/0.20/generated/pandas.merge_asof.html#pandas.merge_asof
    for wdf in wdfs:
        wdf = wdf.sort_values('year0')
        rdf = rdf.sort_values('year')
        mdf = pd.merge_asof(rdf,wdf,left_on='year',right_on='year0', by=['w21t_glacier_number'])
        mdf = mdf.dropna()
        
        # Get just 1 point per decade
        if decade_mean:
            dfg = mdf.groupby(['w21t_Glacier', 'w21t_glacier_number','year0','year1'])
            mdf = dfg.mean()
        mdf = mdf.reset_index()

        mdfs.append(mdf)

    return mdfs

# ---------------------------------------------------------------
def regress_kappas(mdfs):
    """Determins kappa for up_len ~ q4tf (for the two regional glacier subsets"""

    kappas_list = list()
    for mdf in mdfs:

        dfg = mdf.groupby(['w21t_Glacier','w21t_glacier_number'])
        kappas = list()
        for _,df in dfg:
            results = statsmodels.formula.api.ols('up_len ~ q4tf', data=df).fit()
            #print(results.summary())
            kappa = results.params.q4tf   # Kappa named after regression in paper
            kappas.append(kappa)
        ##    #lr = sklearn.liear_model.LinearRegression()
         #   lr.fit()
        #    print(df)
        #    df.plot.scatter('q4tf','up_len')
        kappas = np.array(kappas)
        df = pd.DataFrame({'kappa':kappas})
        df = df[df.kappa.abs()<1]
        df.plot()
        print(df.kappa.mean())
        kappa = df.kappa.mean()   # delta_L = kappa * delta_q4tf
        kappas_list.append(kappa)

    return kappas_list

# ---------------------------------------------------------------
def main():
    # Read our set of glaciers
    map_wkt = uafgi.data.wkt.nsidc_ps_north
    select = d_stability.read_select(map_wkt)

    # Read data from my experiment
    velterm_df = d_velterm.read()

    wdfs = wood_q4tf(select)
    rdf = read_retreats(select)
    mdfs = join_retreats_q4tf(rdf,wdfs,decade_mean=True)

    kappas = regress_kappas(mdfs)

    print(kappas)

main()

