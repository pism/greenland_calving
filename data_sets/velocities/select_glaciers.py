import sys
import numpy as np
import os
import re
import pandas as pd
import pyproj
from uafgi import gdalutil,ogrutil,shputil
from uafgi.nsidc import nsidc0481
from uafgi import greenland,pdutil
import shapely
import shapely.geometry
from osgeo import ogr,osr




def select_glaciers(includes, w21_blackouts=None):
    """w21_blackouts:
        DataFrame with index matching w21, cols do not matter; rows we do NOT want to select.
    """

    # Master set of glaciers from which we will select
    w21 = greenland.read_w21(greenland.map_wkt)
    glaciers = w21.df.copy()

    # TESTING
#    glaciers = glaciers[glaciers['w21_popular_name']=='Jakobshavn Isbrae']

    # Join in the "include" column
    glaciers = pd.merge(glaciers, includes[['w21_key', 'include']], how='left', on='w21_key')
    # Rows of w21 we MUST include
    include_rows = glaciers[glaciers['include'] == 1]

    if w21_blackouts is not None:
        # Get the original w21.df's index onto the blackouts list
        blackouts_index= pd.merge(w21.df.reset_index(), w21_blackouts, how='inner', on='w21_key').set_index('index').index

        # Remove items we previously decided we DID NOT want to select
        glaciers = glaciers.drop(blackouts_index, axis=0)

    # Select glaciers with fjord width between 2km and 4km
    glaciers = glaciers[(glaciers['w21_mean_fjord_width'] >=2) & (glaciers['w21_mean_fjord_width'] <= 4)]

    # Categorize by different regions / glacier types
    dfg = glaciers.groupby(['w21_coast', 'w21_category'])

    # Select glacier with maximum mean discharge in each category
    # https://stackoverflow.com/questions/32459325/python-pandas-dataframe-select-row-by-max-value-in-group?noredirect=1&lq=1
    select = dfg.apply(lambda group: group.nlargest(1, columns='w21_mean_discharge')).reset_index(drop=True)

    # Add in the includes
    select = pd.concat([select, include_rows]) \
        .drop_duplicates(subset=['w21_key']) \
        .reset_index()

    return w21.replace(df=select)


def select_glaciers_main():

    pd.set_option('display.max_columns', None)

    # Read user overrides of joins and columns
    over = greenland.read_overrides('overrides.ods', 'troughs/shp/terminus_locations.shp', ['w21_key', 'bkm15_key'], 'w21_key', greenland.map_wkt)

    # Set up glacers we DON'T want to select
    blackouts = pd.DataFrame({
        'w21_key' : [
    #        ('Bowdoin Gl.', 'BOWDOIN'),
    #        ('F. Graae Gl.', 'F_GRAAE'),
    #        ('Vestfjord Gl.', 'VESTFJORD'),
        ]
    })

    # Get initial list of glaciers
    select = select_glaciers(over, blackouts)

    # Join with bkm15
    bkm15 = greenland.read_bkm15(greenland.map_wkt)
    match = greenland.match_allnames(select, bkm15)
    select = match.left_join(overrides=over)
#    print(select.df.columns)



    select.df = greenland.override_cols(select.df, over, 'w21_key',
        [('bkm15_lat', 'lat', 'lat'),
         ('bkm15_lon', 'lon', 'lon'),
         ('bkm15_loc', 'loc', 'loc')])
#    print(select.df[['w21_key','bkm15_key']])
#    print(select.df.loc([32]))

#    print(select.df[['w21_key','bkm15_key']])

    # Identify the hand-drawn fjord for each item
    fj = greenland.read_fj(greenland.map_wkt)
    match = greenland.match_point_poly(select, 'loc', fj, 'fj_poly')
    select = match.left_join(right_cols=['fj_poly'])

#    print(select.df[['w21_key', 'fj_poly', 'grid']])

    ns481 = greenland.read_ns481(greenland.map_wkt)

    match = greenland.match_point_poly(select, 'loc', ns481, 'ns481_poly',
        left_cols=['fj_poly'], right_cols=['ns481_poly'])
    match.df['fjord_grid_overlap'] = match.df.apply(
            lambda x: 0 if (type(x['ns481_poly'])==float or type(x['fj_poly']) == float)
            else x['ns481_poly'].intersection(x['fj_poly']).area / x['fj_poly'].area,
            axis=1)

    #match.df = pd.merge(match.df, select.df, on='w21_key', how='left')
    #match.df.sort_values(['w21_ix'])
    match.df.sort_values(['w21_ix'])

    select = match.left_join(overrides=over[['w21_key', 'ns481_key']])

    select.df = select.df[~select.df['ns481_key'].isna()]
    #print(sel.df.columns)
    #print(select.df[['w21_popular_name', 'lat', 'lon', 'w21_coast', 'ns481_grid', 'fj_poly']])


    # Join with CALFIN dataset high-frequency termini
    cf20= greenland.read_cf20(greenland.map_wkt)
#    cf20.df.to_csv('cf20.csv')
    print('===================================')
    match = greenland.match_point_poly(cf20, 'cf20_locs', select, 'fj_poly').swap()
    select = match.left_join(overrides=over)

    select.df.to_csv('select.csv')

    # ----- Join with NSIDC-0642 (MEASURES) annual termini
    ns642 = greenland.read_ns642(greenland.map_wkt)
    # Combine all points for each GlacierID
    ns642x = greenland.ns642_by_glacier_id(ns642)

    match = greenland.match_point_poly(
        ns642x, 'ns642_points', select, 'fj_poly',
        right_cols=['lat','lon','w21_key']).swap()
#    print('xyz1', match.df.columns)
    select = match.left_join(overrides=over)

    
#    print(select.df[['w21_popular_name', 'w21_coast', 'ns481_grid', 'cf20_key', 'ns642_key']])
#    print(select.df[['w21_popular_name', 'lat', 'lon', 'w21_coast', 'ns481_grid', 'fj_poly', 'cf20_key']])


    print(select.df[['w21_popular_name']])
    selT,selF = pdutil.split_na(select.df, 'cf20_key')
    print(selT.columns)
    cols = ['w21_popular_name', 'w21_coast', 'ns481_grid', 'cf20_key', 'ns642_key']
    print('xxxxxxxxxxxxxxxxxxxxxxx')
    print(selT[cols])
    print('xxxxxxxxxxxxxxxxxxxxxxx')
    print(selF[cols])

    seldf = select.df.drop(['cf20_locs', 'ns642_points', 'ns481_poly'])
    
    select.df.to_pickle('select.df')
    select.df.to_csv('select.csv')


    return select

# ====================================================================




select_glaciers_main()
