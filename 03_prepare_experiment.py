import numpy as np
import pandas as pd
from uafgi import gdalutil,bedmachine,glacier,make
import uafgi.wkt
import uafgi.data
import uafgi.data.ns642
from osgeo import gdal

# =================================================================
# ---------------- Consistent filename processing



def prepare_experiment(select):

    """Adds columns to the Glacier Selection dataframe, to prepare for
    experiment.

    terminus: LineString
        The terminus from which the simulation will start
    fjord: np.array(bool)
        The entire fjord
    up_fjord: np.array(bool)
        Portions of the fjord upstream of the terminus

    Returns:
        New select dataframe

    NOTE: Localized BedMachine files must already exist by now!
        See 02_extract_bedmachine.py
    """

    # Shallow  copy
    select = select.copy()

    # Use standard Polar Stereographic projection for Greenland
    wkt = uafgi.wkt.nsidc_ps_north

    # Read annual termini
    ns642 = uafgi.data.ns642.read(wkt)
    ns642_dict = dict(list(ns642.df.groupby(by='ns642_GlacierID')))

    def _add_termini(row):
        print('glacierid ', row['ns481_grid'], row['ns642_GlacierID'])
        # Determine the local grid
        grid = row['ns481_grid']
        grid_file = uafgi.data.measures_grid_file(grid)
        grid_info = gdalutil.FileInfo(grid_file)
        bedmachine_file = uafgi.data.bedmachine_local(grid)

        # Load the fjord
        fjord = bedmachine.get_fjord(bedmachine_file, row['fj_poly'])

        # Obtain past terminus traces
        ns642_this = ns642_dict[row['ns642_GlacierID']]
        termini = ns642_this['ns642_terminus'].to_list()

        # Determine the most-retreated terminus
        def _up_termini():
            for terminus in termini:
                fjc = glacier.classify_fjord(fjord, grid_info, row.up_loc, terminus)
                up_fjord = np.isin(fjc, glacier.GE_TERMINUS)
                yield np.sum(np.sum(up_fjord)), terminus, fjc

        _, terminus, fjc = min(
            _up_termini(),
            key=lambda x: x[0])

        # Return value to put in a series
        return (grid_info, fjc, terminus)

    # Compute three new cols; first as one column, then break apart
    combo = select.apply(_add_termini, axis=1)
    for ix,vname in enumerate(['grid_info', 'fjord_classes', 'terminus']):
        select[vname] = combo.map(lambda x: x[ix])

    return select


# ==================================================================
# apply linear regresion using numpy
def linReg(x, y):
    '''linear regression using numpy starting from two one dimensional numpy arrays
    x: np.array
        Values of independent variable
    y: np.arry
        Values of dependent variable'''
    A = np.vstack([x, np.ones(len(x))]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    return pd.Series({'slope':slope, 'intercept': intercept})


def add_termini(select):
    """Adds two columns to selected glaciers, from ns642 dataset:
        years:
            List of years
        termini:
            LineString of terminus for each year

    select:
        The dataset to add to
    """

    # Use standard Polar Stereographic projection for Greenland
    map_wkt = uafgi.wkt.nsidc_ps_north
    ns642 = uafgi.data.ns642.read(map_wkt)

    # Before grouping, filter by Glacier IDs we care about
    # So we don't waste time reading termini of useless glacierss
    glacier_ids = set(select['ns642_GlacierID'].to_list())
    ns642x = ns642.df[ns642.df['ns642_GlacierID'].isin(glacier_ids)]

    # Group by GlacierID
    ns642g = ns642x[['ns642_GlacierID', 'ns642_year0', 'ns642_terminus']].groupby(['ns642_GlacierID'])

    # Create DataFrame with years and termini as lists
    def _year_terminus_to_list(df):
#        grid_file = uafgi.data.measures_grid_file(grid)
#        grid_info = gdalutil.FileInfo(grid_file)
        years = df['ns642_year0'].to_list()
        termini = df['ns642_terminus'].to_list()
        return pd.DataFrame(data={'ns642_years': [years], 'ns642_termini': [termini]})

    ytdf = ns642g.apply(_year_terminus_to_list).reset_index().drop(['level_1'], axis=1)


    df = pd.merge(select, ytdf, how='left', on='ns642_GlacierID', suffixes=(None,'_DELETEME'))
    drops = [x for x in df.columns if x.endswith('_DELETEME')]
    df = df.drop(drops, axis=1)
    return df


def _retreat_rate(row):
    fjord = np.isin(row['fjord_classes'], glacier.ALL_FJORD)
    ice_area = [glacier.ice_area(row.grid_info, fjord, row.up_loc, t) for t in row.ns642_termini]
    ice_len = [x / (row.w21_mean_fjord_width * 1000.) for x in ice_area]
    slope,_ = linReg(row.ns642_years, ice_len)
    return slope

def add_retreat_rate(select):
    '''Adds a column to the dataframe, based on ns642 terminus positions
    retreat_rate: [m/a]
        Calculated linear rate of retreat of the glacier.
        Obtained as m^2/a and dividing by the mean fjord width.
    '''
    select = add_termini(select)
    select['retreat_rate'] = select.apply(_retreat_rate, axis=1)
#    select = select.drop([['ns642_years', 'ns642_termini']], axis=1)
    return select


# ==================================================================



# ===============================================================
def main():
    select = pd.read_pickle(uafgi.data.join_outputs('stability', '01_select.df'))

    # Just one row for testing
#    select = select[select['w21_key']==('Rink Isbrae', 'RINK_ISBRAE')]

    select = prepare_experiment(select)
    select = add_retreat_rate(select)

    print('select:......')
    print(select.columns)
    select.to_pickle(uafgi.data.join_outputs('stability', '03_select.df'))
    select.to_csv(uafgi.data.join_outputs('stability', '03_select.csv'))

    for ix,row in select.iterrows():
        grid = row['ns481_grid']
        grid_file = uafgi.data.measures_grid_file(grid)
        grid_info = gdalutil.FileInfo(grid_file)
        fjord_classes = row['fjord_classes']

        # Write sample file so we can check results
        fname = 'fjord_classes-{:02d}.nc'.format(ix)
        ds = gdalutil.clone_geometry('NetCDF', fname, grid_info, 1, gdal.GDT_Byte)
        band = ds.GetRasterBand(1)
        band.SetMetadataItem('NETCDF_VARNAME', row['w21_popular_name'])
        band.WriteArray(fjord_classes)
        ds.FlushCache()

main()

