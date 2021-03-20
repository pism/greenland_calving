import sys
import numpy as np
import os
import re
import pandas as pd
import pyproj
from uafgi import gdalutil,ogrutil,shputil
from uafgi import pdutil
import shapely
import shapely.geometry
from osgeo import ogr,osr
import uafgi.data
import uafgi.data.bkm15
import uafgi.data.cf20
import uafgi.data.fj
import uafgi.data.m17
import uafgi.data.mwp
import uafgi.data.ns481
import uafgi.data.ns642
import uafgi.data.w21
import uafgi.data.wkt
from uafgi.data import greenland
import pandas_ods_reader

"""Determine a set of glaciers for our experiment."""


def _csv_to_tuple(val):
    """Converts key column value from comma-separated format to standard
    format."""

    if (type(val) == float) or (val is None):
        return val

    parts = val.split(',')
    if len(parts) == 1:
        return parts[0]
    return tuple(parts)

def read_overrides(overrides_ods, locations_shp, keycols, join_col, map_wkt):

    """Reads an per-project overrides table, ready to use as overrides in
    joins.  The table is read as a combination of an ODS file and a
    shapefile containing the locations of termini; with an attribute
    in the shapefile matching a column in the overrides_ods file.

    The location of the terminus points is returned in the columns:
        lat, lon: degrees
        loc: shapely.geometry.Point

    Args:
        overrides_ods: filename
            Name of the overrides file (ODS format)
            Must contain at least column: <join_col>

        locations_shp: filename
            Name of the shapefile identifying a location point for each glacier.
            Must contain at least one attribute: <join_col>

        keycols: [str, ...]
            Names of columns that are keys (in both datasources).
            Comma-separate them and turn into tuples.

        join_col: str
            Name of column used to join overrides and locations

    """

    # Manual overrides spreadsheet
    over = pandas_ods_reader.read_ods(overrides_ods,1)
    over = over.drop('comment', axis=1)
    over = over.dropna(how='all')    # Remove blank lines

    # Manual glacier point locations
    tl = pd.DataFrame(shputil.read(locations_shp, map_wkt))

    # Convert keycols to tuples
    for df in (over,tl):
        for col in keycols:
            df[col] = df[col].map(_csv_to_tuple)

    # Mark to remove any "extra" columns that we didn't actually join with
    df = pd.merge(over,tl,how='left',on='w21_key', suffixes=(None,'_DELETEME'))


    # Move data from the shapefile to override the lon/lat columns
    df = df.rename(columns={'_shape' : 'loc'})
    lon = df['_shape0'].map(lambda xy: xy if type(xy)==float else xy.x)
    lat = df['_shape0'].map(lambda xy: xy if type(xy)==float else xy.x)

    # Merge the shapefile and spreadsheet lat/lon, if available.
    if 'lon' in df:
        df['lon'] = df['_shape0'].map(lambda xy: xy if type(xy)==float else xy.x).fillna(df['lon'])
    if 'lat' in df:
        df['lat'] = df['_shape0'].map(lambda xy: xy if type(xy)==float else xy.y).fillna(df['lat'])

    # Remove extraneous columns
    drops = ['_shape0'] + [x for x in df.columns if x.endswith('_DELETEME')]
    df = df.drop(drops, axis=1)
    return df

# ------------------------------------------------------------------
def select_glaciers(includes, w21_blackouts=None):
    """w21_blackouts:
        DataFrame with index matching w21, cols do not matter; rows we do NOT want to select.
    """

    # Master set of glaciers from which we will select
    w21 = uafgi.data.w21.read(uafgi.data.wkt.nsidc_ps_north)
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
    over = read_overrides(
        'overrides/overrides.ods', 'overrides/terminus_locations.shp',
        ['w21_key', 'bkm15_key'], 'w21_key', uafgi.data.wkt.nsidc_ps_north)

    # Set up glacers we DON'T want to select
    blackouts = pd.DataFrame({
        'w21_key' : [
            ('Upernavik Isstrom SS', 'UPERNAVIK_ISSTROM_SS'),    # Glacier is too much bother
            ('Midgard Gl.', 'MIDGARDGLETSCHER'),    # Not really any fjord left
    #        ('Bowdoin Gl.', 'BOWDOIN'),
    #        ('F. Graae Gl.', 'F_GRAAE'),
    #        ('Vestfjord Gl.', 'VESTFJORD'),
        ]
    })

    # Get initial list of glaciers
    select = select_glaciers(over, blackouts)

    # Join with bkm15
    bkm15 = uafgi.data.bkm15.read(uafgi.data.wkt.nsidc_ps_north)
    match = greenland.match_allnames(select, bkm15)
    select = match.left_join(overrides=over)
#    print(select.df.columns)



    select.df = pdutil.override_cols(select.df, over, 'w21_key',
        [('bkm15_lat', 'lat', 'lat'),
         ('bkm15_lon', 'lon', 'lon'),
         ('bkm15_loc', 'loc', 'loc')])
#    print(select.df[['w21_key','bkm15_key']])
#    print(select.df.loc([32]))

#    print(select.df[['w21_key','bkm15_key']])

    # Identify the hand-drawn fjord for each item
    fj = uafgi.data.fj.read(uafgi.data.wkt.nsidc_ps_north)
    match = pdutil.match_point_poly(select, 'loc', fj, 'fj_poly')
    select = match.left_join(right_cols=['fj_poly', 'fj_fid'])

    ns481 = uafgi.data.ns481.read(uafgi.data.wkt.nsidc_ps_north)

    match = pdutil.match_point_poly(select, 'loc', ns481, 'ns481_poly',
        left_cols=['fj_poly'], right_cols=['ns481_poly'])
    match.df['fjord_grid_overlap'] = match.df.apply(
            lambda x: 0 if (type(x['ns481_poly'])==float or type(x['fj_poly']) == float)
            else x['ns481_poly'].intersection(x['fj_poly']).area / x['fj_poly'].area,
            axis=1)

    match.df.sort_values(['w21_ix'])

    select = match.left_join(overrides=over[['w21_key', 'ns481_key']])
    select.df = select.df[~select.df['ns481_key'].isna()]


    # Join with CALFIN dataset high-frequency termini
    cf20= uafgi.data.cf20.read(uafgi.data.wkt.nsidc_ps_north)
#    cf20.df.to_csv('cf20.csv')
    print('===================================')
    match = pdutil.match_point_poly(cf20, 'cf20_locs', select, 'fj_poly').swap()
    select = match.left_join(overrides=over)

#    select.df.to_csv('select.csv')

    # ----- Join with NSIDC-0642 (MEASURES) annual termini
    ns642 = uafgi.data.ns642.read(uafgi.data.wkt.nsidc_ps_north)
    # Combine all points for each GlacierID
    ns642x = uafgi.data.ns642.by_glacier_id(ns642)

    match = pdutil.match_point_poly(
        ns642x, 'ns642_points', select, 'fj_poly',
        right_cols=['lat','lon','w21_key']).swap()
#    print('xyz1', match.df.columns)
    select = match.left_join(overrides=over)


    # ----- Add a single upstream point for each glacier
    up = shputil.read_df(
        uafgi.data.join('upstream/upstream_points.shp'),
        uafgi.data.wkt.nsidc_ps_north, shape='loc', add_prefix='up_')

    match = pdutil.match_point_poly(up, 'up_loc', select, 'fj_poly').swap()
    select = match.left_join()

        

    
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

    select.df.to_pickle('select_01.df')
    seldf = select.df.drop(['cf20_locs', 'ns642_points', 'ns481_poly'], axis=1)
    seldf.to_csv('select_01.csv')


    return select

# ====================================================================




select_glaciers_main()
