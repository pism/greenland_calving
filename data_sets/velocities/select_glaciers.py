import numpy as np
import os
import re
import pandas as pd
import pyproj
from uafgi import gdalutil,ogrutil
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

    df = pd.read_pickle('data/GreenlandGlacierStats/GreenlandGlacierStats.pik')

    # Select glaciers with fjord width between 2 and 4 km
    df = df[(df['mean_fjord_width'] >=2) & (df['mean_fjord_width'] <= 4)]

    # Categorize by different regions / glacier types
    dfg = df.groupby(['coast', 'category'])

    # Select glacier with maximum mean discharge in each category
    # https://stackoverflow.com/questions/32459325/python-pandas-dataframe-select-row-by-max-value-in-group?noredirect=1&lq=1
    selections = dfg.apply(lambda group: group.nlargest(1, columns='mean_discharge')).reset_index(drop=True)


    # --------------------------------------------------------
    # Load name and location dataframes
    ddir = 'data/GreenlandGlacierNames/'


    # ---------- Left join by popular_name to get ID
    names1 = pd.read_csv(os.path.join(ddir, 'glacier_names_ext.csv')) \
        .rename(columns={'name': 'popular_name'})
    selections = pd.merge(
        selections, names1, how='left', on=['popular_name','coast'])

    # ---------- Left outer join to get location
    nameloc0 = pd.read_csv(os.path.join(ddir, 'tc-9-2215-2015-supplement.csv'))
    locs1 = pd.read_csv(os.path.join(ddir, 'glacier_locations_ext.csv'))

    # Concat both dataframes together to get a master ID->location table
    loc = pd.concat([
        nameloc0[['ID','LAT','LON']].rename(columns={'LAT':'lat', 'LON':'lon'}),
        locs1])
    selections = pd.merge(
        selections, loc, on=['ID'], how='left') \
        .drop(['popular_name_y'], axis=1) \
        .rename(columns={'popular_name_x' : 'popular_name'})

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

    # ----------------------------------------------------------
    # Project the glacier "location" points into map_wkt
    # Glacier points are in lat/lon
    proj = pyproj.Transformer.from_crs(wgs84,map_crs,always_xy=True)
    locations = pd.Series(
        index=selections.index,
        data=[shapely.geometry.Point(x,y) for x,y in zip(
            *proj.transform(selections.lon.tolist(), selections.lat.tolist()))]
        )


    # Load the fjord for each glacier (project into map transform)
    fjords = load_fjords(map_wkt)    # list

    selections = selections.join(polys_overlapping_points(locations, fjords, fjords, poly_label='fjord'))
    #print(selections.columns)


    # ----------------------------------------------------------
    # Determine the NSIDC grid for each glacier
    rows = list()
    for grid_poly,grid_name in zip(gdf.poly.to_list(), gdf.grid.to_list()):
        intersects = locations[locations.map(lambda p: grid_poly.intersects(p))]
        for ix in intersects.index.tolist():
            rows.append((ix, grid_name, grid_poly))
    grids = pd.DataFrame(rows, columns=['ix', 'grid', 'grid_poly']) \
        .set_index(keys='ix', drop=True) \
        .sort_index()

    # Join back with selections (sometimes >1 grid available per glacier)
    selections = selections.join(grids).reset_index()
    #print(selections.index)
    #print(selections.grid_poly)
    #print(selections.columns)

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
    sel = selections[['popular_name','grid','fjord_area','overlap','opct']]
#    sel = sel[sel['grid'].notna()]
    print(sel)

#    print(grids)

    return

    # ----------------------------------------------------------
    # Determine the NSIDC grid for each glacier

    # Load the grids 
    grids_s = list()
    for index, row in gdf.iterrows():

        # Transform glacier terminus locations to this grid's projection
        local = pyproj.CRS.from_string(row['wkt'])
        proj = pyproj.Transformer.from_crs(wgs84,local,always_xy=True)
        projected_points = pd.Series(
            index=selections.index,
            data=[shapely.geometry.Point(x,y) for x,y in zip(
                *proj.transform(selections.lon.tolist(), selections.lat.tolist()))]
            )

        # Find intersections between terminus locations and this grid
        # NOTE: intersects includes selections.index
        intersects = projected_points[projected_points.map(lambda p: row['poly'].intersects(p))]

        grids_s.append(pd.Series(index=intersects.index, data=[row['grid']] * len(intersects),name='grid'))

    grids = pd.concat(grids_s, axis=0)




    # ----------------------------------------------------------

    # Write out file for QGis
    selq = selections[['ID', 'popular_name', 'lat', 'lon']]
    selq['label'] = selq['ID'].str.cat(selq['popular_name'].fillna('X'),sep=':')
    selq = selq.set_index('ID')


    return selections, selq


def select_glaciers_main():
    selections,selq = select_glaciers()

    # Write out selections
    selections.to_pickle('selections.df')
    selq.to_csv('selections_qgis.csv')

# ====================================================================




select_glaciers_main()

#fjords = load_fjords('PROJCS["WGS 84 / NSIDC Sea Ice Polar Stereographic North",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",70],PARAMETER["central_meridian",-45],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",SOUTH],AXIS["Northing",SOUTH],AUTHORITY["EPSG","3413"]]')
print(fjords)
