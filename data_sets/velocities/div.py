import scipy.sparse.linalg
import scipy.sparse
import numpy as np
import netCDF4
import sys
from pism.util import fill_missing_petsc
import uafgi.indexing

np.set_printoptions(threshold=sys.maxsize)

D_UNUSED = 0    # Not part of the FD Domain
D_MISSING = 1       # Data are missing here
D_DATA = 2      # There is data here

center_diff = ((-1,1), (-.5,.5))

# -------------------------------------------------------
def get_indexing(ndarr):
    """Assumes ndarr is fully packed, row-major: j,i indexing"""
    base = (0,0)
    extent = ndarr.shape
    indices = (0,1)    # List highest-stride index first
    return uafgi.indexing.Indexing(base, extent, indices)

# -------------------------------------------------------
def d_dy_present(divable,dy,  indexing,  rows,cols,vals, factor=1.0, rowoffset=0, coloffset=0):
    """Produces a matrix for the del operator

       rows,cols,vals:
            Matrix M
    divable:
        Map of which cells are avaialble to calculate 2D divergence
        See get_divable()
    """
    #indexing = get_indexing(divable)
    bydy = 1. / dy

    stcoo,stval = center_diff
    for jj in range(0, divable.shape[0]):
        for ii in range(0, divable.shape[1]):
            if divable[jj,ii]:
                for l in range(0,len(stcoo)):
                    jj2 = jj+stcoo[l]

                    # Convert to 1D indexing
                    k = indexing.tuple_to_index((jj,ii))
                    k2 = indexing.tuple_to_index((jj2,ii))
                    rows.append(rowoffset + k)
                    cols.append(coloffset + k2)
                    vals.append(factor * stval[l] * bydy)

def d_dx_present(divable,dx, indexing,  rows,cols,vals,
    factor=1.0, rowoffset=0, coloffset=0):

    d_dy_present(np.transpose(divable),dx, indexing.transpose(),
        rows,cols,vals,
        factor=factor, rowoffset=rowoffset, coloffset=coloffset)
# ----------------------------------------------------------------
# d_dy_fns(present)
d_dyx_fns = {
    True : (d_dy_present, d_dx_present),
}

# ----------------------------------------------------------------
def div_matrix(d_dyx, divable, dyx, rows,cols,vals,
    factor=1.0, rowoffset=0):

    """Generates a matrix to compute divergence of a vector field.
    (v and u are stacked)

    d_dyx: [2]
        Function used to generate the derivative matrix for (d/dy, d/dx)

    vu1:
        1D matrix of U component of velocity, followed by V component
    shape:
        Shape of the original finite difference grid
    """
    indexing = get_indexing(divable)
    n1 = divable.shape[0] * divable.shape[1]
    d_dyx[0](divable,dyx[0], indexing, rows,cols,vals,
        factor=factor, rowoffset=rowoffset)
    d_dyx[1](divable, dyx[1], indexing, rows,cols,vals,
        factor=factor, rowoffset=rowoffset, coloffset=n1)


def curl_matrix(d_dyx, divable, dyx, rows,cols,vals,
    factor=1.0, rowoffset=0):
    """Generates a matrix to compute divergence of a vector field.
    (v and u are stacked)

    vu1:
        1D matrix of U component of velocity, followed by V component
    shape:
        Shape of the original finite difference grid
    """

    indexing = get_indexing(divable)

    n1 = divable.shape[0] * divable.shape[1]
    # curl = del x F = dF_y/dx - dF_x/dy
    d_dyx[1](divable, dyx[1], indexing, rows,cols,vals,
        factor=factor, rowoffset=rowoffset)
    d_dyx[0](divable, dyx[0], indexing, rows,cols,vals,
        factor=-factor, rowoffset=rowoffset, coloffset=n1)

# -------------------------------------------------------
def dc_matrix(d_dyx, divable2, dyx, rows,cols,vals,
    factor=1.0):

    n1 = divable2.shape[0] * divable2.shape[1]

    div_matrix(d_dyx_fns[True], divable2, dyx, rows,cols,vals)
    curl_matrix(d_dyx_fns[True], divable2, dyx, rows,cols,vals, rowoffset=n1)


# -------------------------------------------------------
def cut_subset(val):
#    subval = val[406:420, 406:420]
    subval = val[306:520, 306:520]
    return subval

# -------------------------------------------------------
def get_divable(idomain2):
    """Returns a domain (true/false array) for which the divergence can be
    computed, using ONLY center differences."""
    domain2 = np.zeros(idomain2.shape, dtype=bool)
    # Loop 1..n-1 to maintain a bezel around the edge
    for jj in range(1,idomain2.shape[0]-1):
        for ii in range(1,idomain2.shape[1]-1):
            domain2[jj,ii] = (idomain2[jj+1,ii] and idomain2[jj-1,ii] and idomain2[jj,ii+1] and idomain2[jj,ii-1])
    return domain2


# -------------------------------------------------------
# --------------------------------------------------------
def get_div_curl(vvel2, uvel2, divable_data2):

    n1 = divable_data2.shape[0] * divable_data2.shape[1]

    # ------------ Create div matrix on DATA points
    rows = list()
    cols = list()
    vals = list()
#    dyx = (5000, 5000)
    dyx = (1.,1.)
    dc_matrix(d_dyx_fns[True],
        divable_data2,
        dyx, rows,cols,vals)
    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(n1*2, n1*2))

    # ------------ Compute div/curl

    vu = np.zeros(n1*2)
    vu[:n1] = np.reshape(vvel2,-1)
    vu[n1:] = np.reshape(uvel2,-1)

    # ... in subspace
    divcurl = M * vu
    div2 = np.reshape(divcurl[:n1], divable_data2.shape)
    curl2 = np.reshape(divcurl[n1:], divable_data2.shape)

    div2[np.logical_not(divable_data2)] = np.nan
    curl2[np.logical_not(divable_data2)] = np.nan

    return div2,curl2

# --------------------------------------------------------
def remove_unused_rows(rows,cols,vals,bb,  n1):
    # Renumber the rows
    rows1 = dict((r,0) for r in rows)
    row_renumber = dict((r,i) for i,r in enumerate(rows1.keys()))
    rows2 = [row_renumber[r] for r in rows]
    bb2 = [bb[i] for i,r in enumerate(rows1.keys())]


    if True:
        cols1 = dict((r,0) for r in cols)
        col_renumber = dict((r,i) for i,r in enumerate(cols1.keys()))
        cols2 = [col_renumber[r] for r in cols]
        cols_oldvnew = np.array(list(cols1.keys()), dtype='i') - 1
        ncols_new = len(cols1)
    else:
        cols_oldvnew = None
        cols2 = cols
        ncols_new = n1*2

    nrows_new = len(rows1)
    
    M = scipy.sparse.coo_matrix((vals, (rows2,cols2)),
        shape=(nrows_new, ncols_new)).tocsc()
    rhs = np.array(bb2)

    return M,rhs,cols_oldvnew

# --------------------------------------------------------
def main():
    # --------- Read uvel and vvel
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


    vvel2 = cut_subset(vvel2)
    uvel2 = cut_subset(uvel2)

#    vvel2[:] = 1
#    uvel2[:] = 1

    # ------------ Read amount of ice (thickness)
    rhoice = 918.    # [kg m-3]: Convert thickness from [m] to [kg m-2]
    with netCDF4.Dataset('outputs/bedmachine/W69.10N-thickness.nc') as nc:
        amount2 = nc.variables['thickness'][:] * rhoice

    amount2 = cut_subset(amount2)


    # ------------ Set up the domain map (classify gridcells)
    dmap2 = np.zeros(vvel2.shape, dtype='i') + D_UNUSED
    dmap2[amount2 > 0] = D_DATA
    dmap2[np.where(np.logical_and(
        amount2 > 0,
        np.isnan(vvel2)
        ))] = D_MISSING

    # ------------ Select subspace of gridcells on which to operate

    # Select cells with data
    # *** TODO: This is wonky
    divable_data2 = get_divable(dmap2==D_DATA)
    indexing_data = get_indexing(divable_data2)
    n1 = dmap2.shape[0] * dmap2.shape[1]

    # ----------- Store it
    with netCDF4.Dataset('dmap.nc', 'w') as nc:
        nc.createDimension('y', vvel2.shape[0])
        nc.createDimension('x', vvel2.shape[1])
        ncv = nc.createVariable('dmap', 'i', ('y','x'))
        ncv[:] = dmap2[:]
        ncv = nc.createVariable('amount', 'd', ('y','x'))
        ncv[:] = amount2[:]
        ncv = nc.createVariable('divable_data', 'i', ('y','x'))
        ncv[:] = divable_data2[:]

    div2,curl2 = get_div_curl(vvel2, uvel2, divable_data2)

    # ---------- Apply Poisson Fill to curl
    curl2_m = np.ma.array(curl2, mask=(np.isnan(curl2)))
    curl2_fv,_ = fill_missing_petsc.fill_missing(curl2_m)
    curl2_f = curl2_fv[:].reshape(curl2.shape)

    # ---------- Apply Poisson Fill to div
    div2_m = np.ma.array(div2, mask=(np.isnan(div2)))
    div2_fv,_ = fill_missing_petsc.fill_missing(div2_m)
    div2_f = div2_fv[:].reshape(div2.shape)


#    div2_f[:] = 0
#    curl2_f[:] = 0

    # --------- Redo the domain (smap_used)
    domain_used2 = get_divable(dmap2 != D_UNUSED)

    # ------------ Create div matrix on all domain points
    rows = list()
    cols = list()
    vals = list()
#    dyx = (5000, 5000)
    dyx = (1.,1.)
    dc_matrix(d_dyx_fns[True], domain_used2,
        dyx, rows,cols,vals)

    # ----------- Create dc vector in subspace as right hand side
    dc_s = np.zeros(n1*2)
    dc_s[:n1] = np.reshape(div2_f, -1)
    dc_s[n1:] = np.reshape(curl2_f, -1)
    bb = dc_s.tolist()
    print(' *********** bb nan ', np.sum(np.isnan(bb)))


    # ------------ Add additional constraints for original data
#    rows = list()
#    cols = list()
#    vals = list()
#    bb = list()
    if True:
        for jj in range(0, divable_data2.shape[0]):
            for ii in range(0, divable_data2.shape[1]):

                if dmap2[jj,ii] == D_DATA:

                    ku = indexing_data.tuple_to_index((jj,ii))
                    try:
                        rows.append(len(bb))
                        cols.append(ku)
                        vals.append(.01*1.0)
                        bb.append(.01*vvel2[jj,ii])

                        rows.append(len(bb))
                        cols.append(n1 + ku)
                        vals.append(.01*1.0)
                        bb.append(.01*uvel2[jj,ii])

                    except KeyError:    # It's not in sub_used
                        pass

    print('rows ', sum(1 if np.isnan(x) else 0 for x in rows))
    print('cols ', sum(1 if np.isnan(x) else 0 for x in cols))
    print('vals ', sum(1 if np.isnan(x) else 0 for x in vals))
    print('bb ', sum(1 if np.isnan(x) else 0 for x in bb))

    # ----------- Remove unused rows
#    print('len bb = ', len(bb))
##    rows,cols,vals,bb,cols_oldvnew = remove_unused_rows(rows,cols,vals,bb)
#    print('len bb = ', len(bb))
#
#    # ----------- Convert to a (rectangular) matrix
#    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
#        shape=(nrlen(bb), n1*2)).tocsc()
#    print('nrows= ', len(bb))
#    rhs = np.array(bb)



    print(' *********** bb nan2 ', np.sum(np.isnan(bb)))
    print('M0 shape ',(len(bb), n1*2))
    if False:
        M,rhs,cols_oldvnew = remove_unused_rows(rows,cols,vals,bb, n1)
    else:
        M = scipy.sparse.coo_matrix((vals, (rows,cols)),
            shape=(len(bb),n1*2)).tocsc()
        rhs = np.array(bb)
    print('M len ', M.shape, len(rhs))
    print(' *********** rhs nan2 ', np.sum(np.isnan(rhs)))

    # ----------- Solve for vu_s
#    print('***** Matrix condition number: {}'.format(np.linalg.cond(M)))
    vu_s,istop,itn,r1norm,r2norm,anorm,acond,arnorm,xnorm,var = scipy.sparse.linalg.lsqr(M,rhs, damp=.0005, iter_lim=3000)

    # ----------- Convert back to full space
#    vu = np.zeros(n1*2) + np.nan
#    vu[cols_oldvnew] = vu_s
    vu = vu_s

    vv3 = np.reshape(vu[:n1], dmap2.shape)
    uu3 = np.reshape(vu[n1:], dmap2.shape)

    div3,curl3 = get_div_curl(vv3, uu3, domain_used2)


    # ----------- Store it
    with netCDF4.Dataset('x.nc', 'w') as nc:
        nc.createDimension('y', vvel2.shape[0])
        nc.createDimension('x', vvel2.shape[1])
        ncv = nc.createVariable('dmap', 'i', ('y','x'))
        ncv[:] = dmap2[:]
        ncv = nc.createVariable('amount', 'd', ('y','x'))
        ncv[:] = amount2[:]
#        ncv = nc.createVariable('domain', 'i', ('y','x'))
#        ncv[:] = domain2[:]
        ncv = nc.createVariable('vvel', 'i', ('y','x'))
        ncv[:] = vvel2[:]
        ncv = nc.createVariable('uvel', 'i', ('y','x'))
        ncv[:] = uvel2[:]
        if True:
            ncv = nc.createVariable('div', 'd', ('y','x'))
            ncv[:] = div2
            ncv = nc.createVariable('curl', 'd', ('y','x'))
            ncv[:] = curl2
            ncv = nc.createVariable('div_f', 'd', ('y','x'))
            ncv[:] = div2_f
            ncv = nc.createVariable('curl_f', 'd', ('y','x'))
            ncv[:] = curl2_f

        nc.createVariable('vv3', 'd', ('y','x'))[:] = vv3
        nc.createVariable('uu3', 'd', ('y','x'))[:] = uu3

        nc.createVariable('div3', 'd', ('y','x'))[:] = div3
        nc.createVariable('curl3', 'd', ('y','x'))[:] = curl3


main()
