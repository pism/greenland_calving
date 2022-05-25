import netCDF4
import numpy as np
import scipy.ndimage
from uafgi import flowfill

# --------------------------------------------------------
def main2():

    # ========================= Read Data from Input Files
    # --------- Read uvel and vvel
    t = 0    # Time
    with netCDF4.Dataset('outputs/velocity/TSX_W69.10N_2008_2020_pism.nc') as nc:
        nc_vvel = nc.variables['v_ssa_bc']
        nc_vvel.set_auto_mask(False)
        vsvel2 = nc_vvel[t,:].astype(np.float64)
        vsvel2[vsvel2 == nc_vvel._FillValue] = np.nan

        nc_uvel = nc.variables['u_ssa_bc']
        nc_uvel.set_auto_mask(False)    # Don't use masked arrays
        usvel2 = nc_uvel[t,:].astype(np.float64)
        usvel2[usvel2 == nc_uvel._FillValue] = np.nan

        print('Fill Value {}'.format(nc_uvel._FillValue))


    # ------------ Read amount of ice (thickness)
    with netCDF4.Dataset('outputs/bedmachine/W69.10N-thickness.nc') as nc:
        thk2 = nc.variables['thickness'][:].astype(np.float64)

    # Filter thickness, it's from a lower resolution
    thk2 = scipy.ndimage.gaussian_filter(thk2, sigma=2.0)

    # Amount is in units [kg m-2]
    rhoice = 918.    # [kg m-3]: Convert thickness from [m] to [kg m-2]
    amount2 = thk2 * rhoice

    # ------------ Set up the domain map (classify gridcells)
    has_data = np.logical_not(np.isnan(vsvel2))
    dmap = flowfill.get_dmap(has_data, thk=thk2, threshold=300.,
        dist_channel=3000., dist_front=20000., dyx=(100.,100.))

#    with netCDF4.Dataset('dmap.nc', 'w') as nc:
#        nc.createDimension('y', vsvel2.shape[0])
#        nc.createDimension('x', vsvel2.shape[1])
#        nc.createVariable('amount', 'd', ('y','x'))[:] = amount2
#        nc.createVariable('dmap', 'd', ('y','x'))[:] = dmap

    # ----------- Store it
    vv3,uu3,diagnostics = flowfill.fill_surface_flow(vsvel2, usvel2, amount2, dmap,
        clear_divergence=True, prior_weight=0.8)
    diagnostics['thk'] = thk2
    diagnostics['dmap'] = dmap

    with netCDF4.Dataset('x.nc', 'w') as nc:

        # ----------- Store it
        nc.createDimension('y', vsvel2.shape[0])
        nc.createDimension('x', vsvel2.shape[1])
        nc.createVariable('vsvel', 'd', ('y','x'))[:] = vsvel2
        nc.createVariable('usvel', 'd', ('y','x'))[:] = usvel2
        nc.createVariable('amount', 'd', ('y','x'))[:] = amount2

        nc.createVariable('vsvel_filled', 'd', ('y','x'))[:] = vv3
        nc.createVariable('usvel_filled', 'd', ('y','x'))[:] = uu3

        nc.createVariable('vsvel_diff', 'd', ('y','x'))[:] = vv3-vsvel2
        nc.createVariable('usvel_diff', 'd', ('y','x'))[:] = uu3-usvel2

        for vname,val in diagnostics.items():
            nc.createVariable(vname, 'd', ('y','x'))[:] = val

def main():
    st = disc_stencil(10, (1.,1.))
    print(st)

main2()
