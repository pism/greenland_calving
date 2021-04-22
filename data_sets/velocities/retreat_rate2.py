import numpy as np
import netCDF4
from uafgi import glacier,ncutil,gdalutil,cfutil
from osgeo import gdal,ogr,osr
import uafgi.data.wkt


# ===============================================
sigma_max = 4e5

wkt = uafgi.data.wkt.nsidc_ps_north
srs = osr.SpatialReference(wkt=wkt)

ifname = 'sample_retreat.nc'
velocity_file = 'outputs/itslive/GRE_G0240_E71.75N_2011_2018.nc'


# Retrieve velocity
si_vel = 'm s-1'
itime = 3
with netCDF4.Dataset(velocity_file) as nc:
    in_vel = nc.variables['u_ssa_bc'].units
    print('Velocity units: {}'.format(in_vel))
    uvel = cfutil.convert(nc.variables['u_ssa_bc'][itime,:], in_vel, si_vel)
    vvel = cfutil.convert(nc.variables['v_ssa_bc'][itime,:], in_vel, si_vel)

# Retrieve fjord, etc.
itime = 0
with netCDF4.Dataset(ifname) as ncin:
    grid = ncin.ns481_grid
    grid_file = uafgi.data.measures_grid_file(grid)
    grid_info = gdalutil.FileInfo(grid_file)


    si_strain = 's-1'
    in_strain = 's-1'
    L1 = cfutil.convert(ncin.variables['strain_rates[0]'][itime,:], in_strain, si_strain)
    L2 = cfutil.convert(ncin.variables['strain_rates[1]'][itime,:], in_strain, si_strain)
    sigma = glacier.von_mises_stress_eig(L1, L2)    # [Pa]
    factor = 1. - sigma / sigma_max
    uvel_adj = uvel * factor
    vvel_adj = vvel * factor
    vel = np.sqrt(uvel*uvel + vvel*vvel)
    vel_adj = np.sqrt(uvel_adj*uvel_adj + vvel_adj*vvel_adj)
    mask = ncin.variables['mask'][itime,:]
    fjord = np.isin(ncin.variables['fjord_classes'][:], glacier.ALL_FJORD)


dx = cfutil.convert(grid_info.dx, grid_info.xunits, 'm')
dy = cfutil.convert(grid_info.dy, grid_info.xunits, 'm')

# Determine cells with flux to the east

# In the fjord
# Mask in (2,3)  (grounded / floating ice)
# Gridcell just east has mask=4 (open water)



# ---------------- Border cells dumping ice East / West
# https://stackoverflow.com/questions/20528328/numpy-logical-or-for-more-than-two-arguments

#fjord[:] = True

# Flux to the East: [m^2 s-1] ("horizontal sheet extruding through terminus")
maskX = mask.copy()
maskX[:,:-1] = mask[:,1:]    # Shift west by 1 pixel
fjordX = fjord.copy()
fjordX[:,:-1] = fjord[:,1:]    # Shift west by 1 pixel
cells = np.logical_and.reduce((fjord, fjordX, np.isin(mask,(2,3)), maskX==4))
fluxE = np.maximum(uvel_adj * cells.astype(float) * dy, 0.0)

# Flux to the West
maskX = mask.copy()
maskX[:,1:] = mask[:,:-1]    # Shift east by 1 pixel
fjordX = fjord.copy()
fjordX[:,1:] = fjord[:,:-1]    # Shift east by 1 pixel
cells = np.logical_and.reduce((fjord, fjordX, np.isin(mask,(2,3)), maskX==4))
fluxW = np.maximum(-uvel_adj * cells.astype(float), 0.)

# Flux to the North
maskX = mask.copy()
maskX[:-1,:] = mask[1:,:]    # Shift south by 1 pixel
fjordX = fjord.copy()
fjordX[:-1,:] = fjord[1:,:]    # Shift south by 1 pixel
cells = np.logical_and.reduce((fjord, fjordX, np.isin(mask,(2,3)), maskX==4))
fluxN = np.maximum(vvel_adj * cells.astype(float) * dx, 0.0)

# Flux to the South
maskX = mask.copy()
maskX[1:,:] = mask[:-1,:]    # Shift north by 1 pixel
fjordX = fjord.copy()
fjordX[1:,:] = fjord[:-1,:]    # Shift north by 1 pixel
cells = np.logical_and.reduce((fjord, fjordX, np.isin(mask,(2,3)), maskX==4))
fluxS = np.maximum(-vvel_adj * cells.astype(float) * dx, 0.0)


# =============================================================


with netCDF4.Dataset(ifname) as ncin:
    schema = ncutil.Schema(ncin)
    with netCDF4.Dataset('y.nc', 'w') as ncout:
        schema.create(ncout, var_kwargs={'zlib': True})
        for vname in ('fluxE', 'fluxW', 'fluxN', 'fluxS', 'sigma', 'uvel', 'vvel', 'vel', 'uvel_adj', 'vvel_adj', 'vel_adj', 'factor'):
            ncout.createVariable(vname, 'd', ('y','x'))
        schema.copy(ncin, ncout)
        ncout.variables['fluxE'][:] = cfutil.convert(fluxE[:], si_vel, in_vel)
        ncout.variables['fluxW'][:] = cfutil.convert(fluxW[:], si_vel, in_vel)
        ncout.variables['fluxN'][:] = cfutil.convert(fluxN[:], si_vel, in_vel)
        ncout.variables['fluxS'][:] = cfutil.convert(fluxS[:], si_vel, in_vel)
        ncout.variables['sigma'][:] = sigma[:]
        ncout.variables['uvel'][:] = cfutil.convert(uvel[:], si_vel, in_vel)
        ncout.variables['vvel'][:] = cfutil.convert(vvel[:], si_vel, in_vel)
        ncout.variables['vel'][:] = cfutil.convert(vel[:], si_vel, in_vel)
        ncout.variables['uvel_adj'][:] = cfutil.convert(uvel_adj[:], si_vel, in_vel)
        ncout.variables['vvel_adj'][:] = cfutil.convert(vvel_adj[:], si_vel, in_vel)
        ncout.variables['vel_adj'][:] = cfutil.convert(vel_adj[:], si_vel, in_vel)
        ncout.variables['factor'][:] = factor[:]



