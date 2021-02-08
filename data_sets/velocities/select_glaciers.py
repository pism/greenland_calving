import os
import pandas as pd
#%matplotlib inline
import matplotlib.pyplot as plt


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
    selections_full = pd.merge(
        selections, loc, on=['ID'], how='left') \
        .drop(['popular_name_y'], axis=1) \
        .rename(columns={'popular_name_x' : 'popular_name'})
    selections_abbrev = selections_full[['popular_name','ID','lat','lon']]

    # ----------------------------------------------------------

    # Write out file for QGis
    selq = selections_full[['ID', 'popular_name', 'lat', 'lon']]
    selq['label'] = selq['ID'].str.cat(selq['popular_name'].fillna('X'),sep=':')
    selq = selq.set_index('ID')


    return selections_full, selq


def select_glaciers_main():
    selections_full,selq = select_glaciers()

    # Write out selections
    selections_full.to_pickle('selections_full.df')
    selq.to_csv('selections_qgis.csv')



select_glaciers_main()


#selections.to_csv('selections.csv')
#selections.to_pickle('selections.pik')
#
#names = pd.read_csv('data/GreenlandGlacierNames/tc-9-2215-2015-supplement.csv')
#
## Read our selections that we wish to geolocate
## NOTE: We don't know whether NORD001, NORD002 or NORD003 is the correct glacier
#selj = pd.read_csv('selections_joined.csv')
#selj = selj[selj['ID'].notna()]
#
## Read manually-obtained locations
#loc1 = pd.read_csv('locations.csv')
## Read existing locations
#loc2 = pd.read_csv('data/GreenlandGlacierNames/tc-9-2215-2015-supplement.csv')
#loc2 = loc2[['ID','LAT','LON']]
#loc2 = loc2.rename(columns={'LAT':'lat', 'LON':'lon'})
## Concat all locations together
#loc = pd.concat([loc1,loc2])
#
## Left join locations with our selections
#selj = pd.merge(selj,loc,on='ID', how='left')
#
## Write out CSV file for QGISq
#selq = selj[['ID', 'popular_name', 'lat', 'lon']]
#selq['label'] = selq['ID'].str.cat(selq['popular_name'].fillna('X'),sep=':')
#selq = selq.set_index('ID')
#selq.to_csv('selection_locations.csv')
#selq
#
