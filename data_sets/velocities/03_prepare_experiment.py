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
        return (fjc, terminus)

    # Compute three new cols; first as one column, then break apart
    combo = select.apply(_add_termini, axis=1)
    for ix,vname in enumerate(['fjord_classes', 'terminus']):
        select[vname] = combo.map(lambda x: x[ix])

    return select


# ==================================================================



# ==================================================================



# ===============================================================
def main():
    select = pd.read_pickle('select_01.df')

    # Just one row for testing
#    select = select[select['w21_key']==('Rink Isbrae', 'RINK_ISBRAE')]

    select = prepare_experiment(select)
    print('select:......')
    print(select.columns)
    select.to_pickle('select_03.df')
    select.to_csv('select_03.csv')

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

