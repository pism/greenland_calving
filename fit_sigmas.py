from uafgi.data import d_velterm
import uafgi.data.stability as d_stability
import uafgi.data.wkt
from uafgi.pism import qregress
from uafgi.data import w21 as d_w21
from uafgi import pdutil
import pandas as pd

# Used for AGU Poster 2021


def fit_sigmas(select, velterm_df):

    dfs = list()
    for _,selrow in select.df.iterrows():
        adv = velterm_df[velterm_df.glacier_id == selrow.w21t_glacier_number]
        adv['aflux'] *= .001
        adv['sflux'] *= .001
        
        df = d_w21.glacier_rate_df(selrow.w21_data_fname)
        df = df.reset_index()

        df = pdutil.merge_nodups(df, adv, left_on='time', right_on='term_year', how='left').drop('term_year',axis=1)
#        df = pdutil.merge_nodups(df, adv, left_on='time', right_on='term_year', how='left').drop('year',axis=1)

        df['sflux1'] = df['sflux'] * df['ice_advection'] / df['aflux']

        df['sigma_max'] = (df['sflux'] * df['ice_advection']) / (df['aflux'] * -df['calving'])
        df = df.set_index('time')
        df = df.dropna()
        
        dfs.append(df)
        break

    return pd.concat(dfs)


def main():
    # Read our set of glaciers
    map_wkt = uafgi.data.wkt.nsidc_ps_north
    select = d_stability.read_select(map_wkt)
    # Read data from my experiment
    velterm_df = d_velterm.read()

#    print(velterm_df.columns)
#    print(select.df.columns)
    sigmasdf = fit_sigmas(select, velterm_df)

    print(sigmasdf)

main()



