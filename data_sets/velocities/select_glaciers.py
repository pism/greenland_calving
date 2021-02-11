import sys
import numpy as np
import os
import re
import pandas as pd
import pyproj
from uafgi import gdalutil,ogrutil,shputil
from uafgi.nsidc import nsidc0481
import shapely
import shapely.geometry
from osgeo import ogr,osr

def load_fjords(dest_crs_wkt):
    """
    dest_crs_wkt:
        WKT of the desination coordinate system.
    """

    driver = ogr.GetDriverByName('ESRI Shapefile')
    src_ds = driver.Open('troughs/shp/fjord_outlines.shp')
    src_lyr = src_ds.GetLayer()   # Put layer number or name in her
    src_srs = src_lyr.GetSpatialRef()
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromWkt(dest_crs_wkt)
    transform = osr.CoordinateTransformation(src_srs, dst_srs)

    fjords_s = list()
    if True:
        while True:
            feat = src_lyr.GetNextFeature()
            if feat is None:
                break
            poly = ogrutil.to_shapely_polygon(feat,transform)

            fjords_s.append(poly)

    return fjords_s
#    fjords = pd.Series(name='fjords',data=fjords_s)
#    return fjords


def polys_overlapping_points(points_s, polys, poly_outs, poly_label='poly'):

    """Given a list of points and polygons... finds which polygons overlap
    each point.

    points_s: pd.Series(shapely.geometry.Point)
        Pandas Series containing the Points (with index)
    polys: [poly, ...]
        List of shapely.geometry.Polygon
    poly_outs: [x, ...]
        Item to place in resulting DataFrame in place of the Polygon.
        Could be the same as the polygon.

    """

    # Load the grids 
    out_s = list()
    for poly,poly_out in zip(polys,poly_outs):

        # Find intersections between terminus locations and this grid
        # NOTE: intersects includes selections.index
        intersects = points_s[points_s.map(lambda p: poly.intersects(p))]

        out_s.append(pd.Series(index=intersects.index, data=[poly_out] * len(intersects),name=poly_label))

    grids = pd.concat(out_s, axis=0)
    return grids


def select_glaciers():
    """Selects a set of glaciers for stability analysis.
    Initial set: just one from each region / category.

    Returns: Two dataframes: selections_full, selq
        selections_full:
            All columns
        selq:
            Dataframe to be stored as CSV file and loaded in QGIS when
            outlining glacier fjords.

            Same rows as selections_full, but only the columns:
            ID:
                Glacier ID ([Bjork et al 2015], extended)
            lat, lon:
                Approximate location of glacier.
            label:
                String used as label in QGis
    """

    stats0 = pd.read_pickle('data/GreenlandGlacierStats/GreenlandGlacierStats.pik')

    # Select glaciers with fjord width between 2 and 4 km
    stats = stats0[(stats0['mean_fjord_width'] >=2) & (stats0['mean_fjord_width'] <= 4)]

    # Categorize by different regions / glacier types
    dfg = stats.groupby(['coast', 'category'])

    # Select glacier with maximum mean discharge in each category
    # https://stackoverflow.com/questions/32459325/python-pandas-dataframe-select-row-by-max-value-in-group?noredirect=1&lq=1
    selections = dfg.apply(lambda group: group.nlargest(1, columns='mean_discharge')).reset_index(drop=True)

    # ------------------ Manual changes to the list
    # Add additional glaciers
    adds = {
        'Skinfaxe Gl.',    # Replaces Rimfaxe

        # Andy Aschwanden  6:00 PM Feb 9, 2021
        #
        # I wonder if there is some benefit to stick with glaciers
        # that are covered by MEASUReS? E.g. if we later want to
        # revisit our approach, or we decide to average MEASUReS
        # velocities.  Also, we should include the usual suspects:
        # Helheim, Kangerdlugssuaq, Rink, Store, Upernavik Isstrom
        # N,C,S, Jakobshavn (even if only used as an example for
        # things that don't work)
        'Helheim Gl.', 'Kangerlussuaq Gl.', 'Rink Isbrae', 'Store Gl.',
        'Upernavik Isstrom N',
        'Upernavik Isstrom C',
        'Upernavik Isstrom S',
        'Jakobshavn Isbrae',
        'Kong Oscar Gl.',
    }
    selections = pd.concat([
        selections,
        stats0.loc[stats0.popular_name.isin(adds)]
        ]).drop_duplicates()

    # Remove some glaciers, one-off
    removes = {
        'Rimfaxe Gl.',   # No NSIDC-0481 grid coverage; nearby similar glaciers
        'Upernavik Isstrom SS',    # We already have 3 other Upernavik Isstrom; duplicate of Upernavik Isstrom S?
        'Sermeq Avannarleq',    # Doesn't seeem to really be marine terminating
    }
    selections = selections[~selections.popular_name.isin(removes)].reset_index()

#    print(selections[['popular_name','greenlandic_name','coast', 'category']])
#    return

    # ----------------------------------------------------------
    # Load dataset of grids.  Use first grid globally
    gdf = nsidc0481.load_grids()

    # ----------------------------------------------------------
    # Set up coordinate reference systems.
    # wgs84: lon/lat from selections DataFrame (above)
    #        (ultimately from glacier location database files)
    wgs84 = pyproj.CRS.from_epsg("4326")

    # Assume all grids use the same projection (NSIDC Polar Stereographic)
    # Project everything to it
    map_wkt = gdf.loc[0].wkt
    map_crs = pyproj.CRS.from_string(map_wkt)

    proj_wgs84 = pyproj.Transformer.from_crs(wgs84,map_crs,always_xy=True)

    # --------------------------------------------------------
    # Load name and location dataframes
    ddir = 'data/GreenlandGlacierNames/'


    # ---------- Left join by popular_name to get ID
    names1 = pd.read_csv(os.path.join(ddir, 'glacier_names_ext.csv')) \
        .rename(columns={'name': 'popular_name'})
    selections = pd.merge(
        selections, names1, how='left', on=['popular_name','coast'])

    # ---------- Read external database of glacier locations and names
    nameloc0 = pd.read_csv(os.path.join(ddir, 'tc-9-2215-2015-supplement.csv'))

    # Project the terminus location points into map_wkt
    locations = pd.Series(
        index=nameloc0.index,
        data=[shapely.geometry.Point(x,y) for x,y in zip(
            *proj_wgs84.transform(nameloc0.LON.tolist(), nameloc0.LAT.tolist()))]
        )
    nameloc0['terminus_location'] = locations

    # --------------------------------------------------------
    # Supplemental name and location database
    locs1 = \
        pd.DataFrame(
            shputil.read('troughs/shp/terminus_locations.shp', map_wkt)) \
        .rename(columns={'_shape0' : 'terminus_location_lonlat', '_shape' : 'terminus_location', 'popname' : 'popular_name'})
#    print(locs1.columns)
    locs1['lat'] = locs1['terminus_location_lonlat'].map(lambda p: p.y)
    locs1['lon'] = locs1['terminus_location_lonlat'].map(lambda p: p.x)
    locs1 = locs1.drop('terminus_location_lonlat', axis=1)

    # -------------------------------------------------------------
    # Concat both dataframes together to get a master ID->location table
    loc = pd.concat([
        nameloc0[['ID', 'LAT', 'LON', 'terminus_location']].rename(columns={'LAT':'lat', 'LON':'lon'}),
        locs1])

    selections = pd.merge(
        selections, loc, on=['ID'], how='left') \
        .drop(['popular_name_y'], axis=1) \
        .rename(columns={'popular_name_x' : 'popular_name'}) \
        .drop('index', axis=1)

    # Stop if there are any selections missing an ID
    missing = selections[selections['ID'].isna()]
    if len(missing) > 0:
        print('=========== Missing IDs:')
        print(missing[['popular_name','greenlandic_name','coast', 'category']])
        print('Remedy by fixing the file troughs/shp/terminus_locations.shp and/or data/GreenlandGlacierNames/glacier_names_ext.csv')
        sys.exit(-1)

    # ----------------------------------------------------------
    # Load the fjord for each glacier (and project into map transform)
    fjords = load_fjords(map_wkt)    # list

    pop = polys_overlapping_points(selections.terminus_location, fjords, fjords, poly_label='fjord')

    selections = selections.join(pop)

    # Write out to file for QGIS; so user can add fjords if needed.
    selq = selections[['ID', 'popular_name', 'lat', 'lon']]
    
    print('--------- BEGIN selq; ignore the warning for now?')
    selq['label'] = selq['ID'].str.cat(selq['popular_name'].fillna('X'),sep=':')
    selq = selq.set_index('ID')
    selq.to_csv('selections_qgis.csv')
    print('--------- END selq')

    # Stop if there are any selections missing a fjord
    missing = selections[selections['fjord'].isna()]
    if len(missing) > 0:
        print('=========== Missing fjord outlines:')
        print(missing[['popular_name','greenlandic_name','coast', 'category']])
        print('Remedy by fixing troughs/shp/terminus_locations.shp (in QGIS), based on selections_qgis.csv')
        sys.exit(-1)


    # ----------------------------------------------------------
    # Determine the NSIDC grid for each glacier
    rows = list()
    locations = selections['terminus_location']
    for grid_poly,grid_name in zip(gdf.poly.to_list(), gdf.grid.to_list()):
        intersects = locations[locations.map(lambda p: grid_poly.intersects(p))]
        for ix in intersects.index.tolist():
            rows.append((ix, grid_name, grid_poly))

    glacier_grids = pd.DataFrame(rows, columns=['ix', 'grid', 'grid_poly']) \
        .set_index(keys='ix', drop=True) \
        .sort_index()

    # Join back with selections (sometimes >1 grid available per glacier)
    selections = selections.join(glacier_grids).reset_index()

    # ----------------------------------------------------------
    # Determine area of overlap of fjord with grid domain
    fjord_area = selections.apply(
        lambda x: 0 if type(x['fjord']) == float else x['fjord'].area,
        axis=1).rename('fjord_area')

    overlaps = selections.apply(
        lambda x: 0 if (type(x['grid_poly'])==float or type(x['fjord']) == float) else x['grid_poly'].intersection(x['fjord']).area,
        axis=1).rename('overlap')

    df = pd.concat([fjord_area, overlaps, (overlaps / fjord_area).rename('opct')], axis=1)

    selections = selections.join(df)

    # -------------------------------------------------------
    # Remove glaciers that can't be located on an NSIDC-0481 grid
    selections = selections[selections['opct'] != 0.0]

    # -------------------------------------------------------
    # Choose a grid for glaciers with multiple grids
    # Use that to eliminate duplicates
    grid_override = pd.DataFrame(
        data=[
            ('GGN0295','Kangilleq','W70.90N'),
            ('NORD001','Nordenskiold Gl. N','W75.85N')],
        columns=['ID','popular_name','grid_override'])

    selections = pd.merge(
        selections, grid_override, on=['ID'], how='left') \
        .rename(columns={'popular_name_x' : 'popular_name'}) \
        .drop(['popular_name_y', 'index'], axis=1)

    # Eliminate duplicate grids; drop the non-preferred grid
    selections = selections[
        (selections.grid_override == selections.grid) | selections.grid_override.isna()]

    # Check if any duplicated rows remain
    dup = selections.duplicated(subset='ID', keep=False)
    # Keep only "True" rows
    dup = dup[dup]

    # Check that no glaciers have duplicated grid
    if len(dup) > 0:
        print('=========== Glaciers with duplicate grids:')
        # Index out of selections based on dup
        print(selections.loc[dup.index][['ID', 'popular_name', 'coast', 'grid', 'opct']])
        print('Remedy by updating the grid_override variable in select_glaciers.py')
        sys.exit(-1)


    # Print for good measure
    print('============= Resulting Selections')
    print(selections[['ID', 'popular_name', 'coast', 'grid', 'opct']].sort_values('grid'))


    return selections

def select_glaciers_main():
    selections = select_glaciers()

    # Write out selections
    fname = 'selections.df'
    print('...saving to {}'.format(fname))
    selections.to_pickle(fname)

# ====================================================================




select_glaciers_main()
