import numpy as np
import pandas as pd
from uafgi import make,cfutil,glacier,gdalutil,ncutil,pdutil
from uafgi.pism import pismutil,flow_simulation
import uafgi.data
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
import uafgi.data.itslive as d_itslive
import os
import datetime
import netCDF4

pd.set_option('display.max_columns', None)

# Caluclate the retreat rates for the Wood et al 2021 glaciers, based on historical terminus positions
w21 = d_w21.
