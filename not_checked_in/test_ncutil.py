from uafgi import ncutil
import netCDF4

with netCDF4.Dataset('x.nc') as ncin:
    ncs = ncutil.Schema(ncin)
    with netCDF4.Dataset('y.nc', 'w') as ncout:
        ncs.create(ncout, var_kwargs={'zlib': True})
        print('AA1')
        ncs.copy(ncin, ncout)
        print('AA2')



