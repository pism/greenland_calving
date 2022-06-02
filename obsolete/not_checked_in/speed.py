import netCDF4
from uafgi import ncutil
import numpy as np

with netCDF4.Dataset('fill.nc', 'r') as nc0:
    with netCDF4.Dataset('speed.nc', 'w') as ncout:
        cnc = ncutil.copy_nc(nc0, ncout)
        vars = list(nc0.variables.keys())
        cnc.define_vars(vars)
        for var in vars:
                cnc.copy_var(var)

        
        vvel = nc0.variables['vvel'][:]
        uvel = nc0.variables['uvel'][:]

        speed = vvel*vvel + uvel*uvel

        ncout.createVariable('speed', 'd', ('y', 'x'))[:] = speed
