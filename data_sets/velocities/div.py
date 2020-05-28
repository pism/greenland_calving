import scipy.sparse
import numpy as np
import netCDF4


right_diff = ((0,1), (-1.,1.))
center_diff = ((-1,1), (-.5,.5))
left_diff = ((-1,0), (-1.,1.))
nan_stencil = ((0,), (np.nan,))

stencil_choice = [
    center_diff,    # left and right are OK
    left_diff,      # rightnan
    right_diff,     # leftnan
    nan_stencil]    # Both are nan

def get_stencil(data, iyx):
    """
    data:
        The original data for which we're getting a stencil.
        Assume we're always getting stencil for dimension=0
    iyx:
        Index into data where we are looking
    """
    # Test for location at edges
    if iyx[0]-1 < 0:
        return right_diff
    if iyx[0]+1 >= data.shape[0]:
        return left_diff

    return center_diff

#    # Test for missing data on one side or the other
#    leftnan = 2 if np.isnan(data[iyx[0]-1, iyx[1]]) else 0
#    rightnan = 1 if np.isnan(data[iyx[0]+1, iyx[1]]) else 0
#    return stencil_choice[leftnan + rightnan]

def d_dx(data, idim,dyx, rows,cols,vals, factor=1.0, rowoffset=0, coloffset=0):
    """Produces a matrix for the del operator"""
    bydx = 1. / dyx[idim]
    data1 = np.reshape(data,-1)

    # Data array, transposed so idim is now dim=0
    if idim == 0:
        dataT = data
    else:
        dataT = data.transpose()

    stride = data.strides[idim] // data.strides[1]
    iyx = [0,0]
    for iy in range(0,data.shape[0]):
        iyx[idim]=iy
        for ix in range(0,data.shape[1]):
            iyx[1-idim]=ix
            ii = iy*data.shape[1] + ix
            stcoo,stval = get_stencil(dataT, iyx)
            for k in range(0,len(stcoo)):
                jj = ii + stcoo[k]*stride
                rows.append(ii+rowoffset)
                cols.append(jj+coloffset)
                vals.append(factor*stval[k]*bydx)

def div(vu1, shape, dyx, factor, rows, cols, vals):
    """Generates a matrix to compute divergence of a vector field.
    (v and u are stacked)

    vu1:
        1D matrix of U component of velocity, followed by V component
    shape:
        Shape of the original finite difference grid
    """
    n1 = vu1.shape[0] // 2
    d_dx(np.reshape(vu1[:n1],shape), 0,dyx, rows,cols,vals)
    d_dx(np.reshape(vu1[n1:],shape), 1,dyx, rows,cols,vals, coloffset=n1)



def main():
    t = 0    # Time
    with netCDF4.Dataset('outputs/velocity/TSX_W69.10N_2008_2020_pism.nc') as nc:
        nc_vvel = nc.variables['v_ssa_bc']
        nc_vvel.set_auto_mask(False)
        vvel2 = nc_vvel[t,:]
        vvel2[vvel2 == nc_vvel._FillValue] = np.nan

        nc_uvel = nc.variables['u_ssa_bc']
        nc_uvel.set_auto_mask(False)    # Don't use masked arrays
        uvel2 = nc_uvel[t,:]
        uvel2[uvel2 == nc_uvel._FillValue] = np.nan

        print('Fill Value {}'.format(nc_uvel._FillValue))


    with netCDF4.Dataset('outputs/bedmachine/W69.10N-thickness.nc') as nc:
        thickness2 = nc.variables['thickness'][:]

    # Convert thickness from m to kg/m^2
    rhoice = 920    # kg m-3

    vvel1 = np.reshape(vvel2,-1)
    uvel1 = np.reshape(uvel2,-1)
    thickness1 = np.reshape(thickness2,-1)
    n1 = vvel1.shape[0]
    vu1 = np.zeros(vvel1.shape[0]*2)
    vu1[:n1] = vvel1[:]*thickness1*rhoice
    vu1[n1:] = uvel1[:]*thickness1*rhoice

    rows = list()
    cols = list()
    vals = list()

    div(vu1, vvel2.shape, (5000,5000), 1.0, rows,cols,vals)
    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(n1, n1*2))

    divvel1 = M * vu1
    divvel2 = np.reshape(divvel1, vvel2.shape)

    nan0 = np.isnan(uvel2)
    nan1 = np.isnan(divvel2)
    bn2 = np.logical_and(np.logical_not(nan0), nan1)

#    divvel2[np.abs(divvel2)>10000] = 0

    with netCDF4.Dataset('x.nc', 'w') as nc:
        nc.createDimension('y', vvel2.shape[0])
        nc.createDimension('x', vvel2.shape[1])
        ncv = nc.createVariable('div', 'd', ('y','x'))
        ncv[:] = divvel2
        ncv = nc.createVariable('became_nan', 'd', ('y','x'))
        ncv[:] = bn2

main()
