from uafgi.data import itslive    # Fork from itslive.py for now...
from uafgi import ioutil
import datetime

ifname = 'velocities_data/wood2021/velocities/vel_2016-07-01_2017-06-31.nc'
time_bounds = (datetime.datetime(2016,7,1), datetime.datetime(2017,7,1))
grid_file = 'velocities_data/measures/grids/W61.70N_grid.nc'
ofname = 'z.nc'


with ioutil.TmpDir(tdir='tdir') as tdir:
    itslive.process_year(
        ifname,
        (datetime.datetime(2015,7,1), datetime.datetime(2016,7,1)),
        grid_file, 'fy2016.nc', tdir)

    itslive.process_year(
        ifname,
        (datetime.datetime(2016,7,1), datetime.datetime(2017,7,1)),
        grid_file, 'fy2017.nc', tdir)

    itslive.process_years(

