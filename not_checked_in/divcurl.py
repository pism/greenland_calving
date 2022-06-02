from uafgi import flowfill,ncutil
import netCDF4
import numpy as np
import scipy.ndimage

def get_amount(geometry_file):
    with netCDF4.Dataset(geometry_file) as nc:
        thk2 = nc.variables['thickness'][:].astype(np.float64)
        bed2 = nc.variables['bed'][:].astype(np.float64)

    # Filter thickness, it's from a lower resolution
    thk2 = scipy.ndimage.gaussian_filter(thk2, sigma=2.0)

    # Amount is in units [kg m-2]
    rhoice = 918.    # [kg m-3]: Convert thickness from [m] to [kg m-2]
    amount2 = thk2 * rhoice
    return amount2

def main():
    """Compute div and curl for every velocity field in the MEASURES data"""
    velocity_file = 'outputs/TSX_W71.65N_2008_2020_pism.nc'
    geometry_file = 'outputs/BedMachineGreenland-2017-09-20_pism_W71.65N.nc'
    output_file = 'outputs/TSX_W71.65N_2008_2020_div.nc'

    amount2 = get_amount(geometry_file)

    with netCDF4.Dataset(velocity_file) as nc:
      with netCDF4.Dataset(output_file, 'w') as ncout:

        # Set up the new file
        cnc = ncutil.copy_nc(nc, ncout)
        cnc.createDimension('time', size=0)    # Unlimited
        all_vars = ('x', 'y', 'time', 'time_bnds')#, 'u_ssa_bc', 'v_ssa_bc')
        for vname in all_vars:
            cnc.define_vars(((vname,vname),), zlib=True)
        ncdiv = ncout.createVariable('div', 'd', ('time','y','x'), zlib=True)
        nccurl = ncout.createVariable('curl', 'd', ('time','y','x'), zlib=True)
        for vname in all_vars:
            cnc.copy_var(vname, vname)

        for t in range(0,len(nc.dimensions['time'])):
#        for t in range(0,3):
            print('t = {} of {}'.format(t, len(nc.dimensions['time'])))
            # Read surface velocities
            nc_vvel = nc.variables['v_ssa_bc']
            nc_vvel.set_auto_mask(False)
            vsvel2 = nc_vvel[t,:].astype(np.float64)
            vsvel2[vsvel2 == nc_vvel._FillValue] = np.nan

            nc_uvel = nc.variables['u_ssa_bc']
            nc_uvel.set_auto_mask(False)    # Don't use masked arrays
            usvel2 = nc_uvel[t,:].astype(np.float64)
            usvel2[usvel2 == nc_uvel._FillValue] = np.nan

            # Convert to flux velocity
            vvel2 = vsvel2 * amount2
            uvel2 = usvel2 * amount2

            # -------------- Compute divergence and curl
            print('Computing divergence and curl')
            divable_data2 = flowfill.get_divable(~np.isnan(vvel2))
            div2,curl2 = flowfill.get_div_curl(vvel2, uvel2, divable_data2)

            ncdiv[t,:] = div2
            nccurl[t,:] = curl2

main()

