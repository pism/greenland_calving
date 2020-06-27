import scipy.sparse.linalg
import scipy.sparse
import numpy as np
import netCDF4
import sys
from pism.util import fill_missing_petsc
import uafgi.indexing
import scipy.ndimage

#np.set_printoptions(threshold=sys.maxsize)

# Enumerated values describing each gridcell
D_UNUSED = 0        # Not part of the domain
D_MISSING = 1       # Data are missing here
D_DATA = 2          # There are data here

# Indices and weights for first-order ceter fine difference.
center_diff = ((-1,1), (-.5,.5))

# -------------------------------------------------------
def get_indexing(ndarr):
    """Produces a uafgi.indexing.Indexing object describing
    how a standard row-major 2D array Numpy ndarray is indexed.

    ndarr:
        Numpy array for which to produce an Indexing object.
    Returns:
        The Indexing object for ndarr
    """
    base = (0,0)
    extent = ndarr.shape
    indices = (0,1)    # List highest-stride index first
    return uafgi.indexing.Indexing(base, extent, indices)

# -------------------------------------------------------
def d_dy_present(divable,dy,  indexing,  rows,cols,vals, factor=1.0, rowoffset=0, coloffset=0):

    """Adds the discretized finite difference d/dy operator,
    (derivative in the y direction, or 0th index), to a sparse matrix.
    Each (j,i) index in the 2D array for which a derivative is being
    computed is converted to a k index in the 1D vector on which the
    matrix operates.

    The (row,col) of each item is based on the positions of the
    gridcells involved in each part of the d/dy operator.

    divable: ndarray(bool)
        Map of which cells are avaialble to calculate 2D derivatives;
        i.e. gridcells that are fully surrounded by gridcells with
        data (D_DATA), even if the gridcell itself is undefined.
        See get_divable()

    indexing: uafgi.indexing.Indexing
        Indexing object for 2D arrays 
    rows,cols,vals:
        Lists to which to append (row,col,val) for each item in
        the sparse matrix being created.
    factor:
        Multiple values by this
    rowoffset:
        Add this to every row index.
        Used to put a sub-matrix computing divergence, and one
        computing curl, into the same matrix.
    coloffset:
        Add this to every column index.
        Used to create a matrix that can take a concatenated vecotr of
        [v,u] as its input.
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
    """Adds the discretized finite difference d/dy operator,
    (derivative in the y direction, or 0th index), to a sparse matrix.
    See d_dy_present for arguments.

    d/dx is computed by computing d/dy on the transpose of all the
    (2D) array inputs.  The Indexing object must also be
    "tranposed"...
    """

    d_dy_present(np.transpose(divable),dx, indexing.transpose(),
        rows,cols,vals,
        factor=factor, rowoffset=rowoffset, coloffset=coloffset)
# ----------------------------------------------------------------
def div_matrix(d_dyx, divable, dyx, rows,cols,vals,
    factor=1.0, rowoffset=0):

    """Adds the discretized finite difference divergence operator to a
    sparse matrix.  Based on d/dy and d/dx functions.

    Matrix assumes concated vector of (v,u) where v is the velocity in
    the y direciton, and u in the x direction.

    Each (j,i) index in the 2D array for which a derivative is being
    computed is converted to a k index in the 1D vector on which the
    matrix operates.

    The (row,col) of each item is based on the positions of the
    gridcells involved in each part of the d/dy operator.

    d_dyx:
        Must be (d_dy_present, d_dx_present)
    divable: ndarray(bool)
        Map of which cells are avaialble to calculate 2D derivatives;
        i.e. gridcells that are fully surrounded by gridcells with
        data (D_DATA), even if the gridcell itself is undefined.
        See get_divable()
    dyx: (dy, dx)
        Grid spacing in each direction
    rows,cols,vals:
        Lists to which to append (row,col,val) for each item in
        the sparse matrix being created.
    factor:
        Multiple values by this
    rowoffset:
        Add this to every row index.
        Used to put a sub-matrix computing divergence, and one
        computing curl, into the same matrix.

    """

    indexing = get_indexing(divable)
    n1 = divable.shape[0] * divable.shape[1]
    d_dyx[0](divable,dyx[0], indexing, rows,cols,vals,
        factor=factor, rowoffset=rowoffset)
    d_dyx[1](divable, dyx[1], indexing, rows,cols,vals,
        factor=factor, rowoffset=rowoffset, coloffset=n1)


def curl_matrix(d_dyx, divable, dyx, rows,cols,vals,
    factor=1.0, rowoffset=0):
    """Adds the discretized finite difference divergence operator to a
    sparse matrix.  Based on d/dy and d/dx functions.

    Arguments:
        Same as div_matrix()"""

    indexing = get_indexing(divable)

    n1 = divable.shape[0] * divable.shape[1]
    # curl = del x F = dF_y/dx - dF_x/dy
    d_dyx[1](divable, dyx[1], indexing, rows,cols,vals,
        factor=factor, rowoffset=rowoffset)
    d_dyx[0](divable, dyx[0], indexing, rows,cols,vals,
        factor=-factor, rowoffset=rowoffset, coloffset=n1)

# -------------------------------------------------------
def dc_matrix(d_dyx, divable, dyx, rows,cols,vals,
    factor=1.0):

    """Accumulates a matrix that converts the concatenated vector:
        [v, u]
    to the concatenated vector:
        [div, curl]

    d_dyx:
        Must be (d_dy_present, d_dx_present)
    divable: ndarray(bool)
        Map of which cells are avaialble to calculate 2D derivatives;
        i.e. gridcells that are fully surrounded by gridcells with
        data (D_DATA), even if the gridcell itself is undefined.
        See get_divable()
    dyx: (dy, dx)
        Grid spacing in each direction
    rows,cols,vals:
        Lists to which to append (row,col,val) for each item in
        the sparse matrix being created.
    factor:
        Multiple values by this

    """

    n1 = divable.shape[0] * divable.shape[1]

    div_matrix((d_dy_present, d_dx_present), divable, dyx, rows,cols,vals)
    curl_matrix((d_dy_present, d_dx_present), divable, dyx, rows,cols,vals, rowoffset=n1)


# -------------------------------------------------------
def cut_subset(val):
    """Temporary function to cut down the size of our sample problem."""

#    subval = val[406:420, 406:420]
    subval = val[306:520, 306:520]
    return subval

# -------------------------------------------------------
def get_divable(idomain2):
    """Returns a domain (true/false array) for which the divergence can be
    computed, using ONLY center differences.

    idomain2: ndarray(bool)
        Map of which points in the domain have data.
    """
    domain2 = np.zeros(idomain2.shape, dtype=bool)
    # Loop 1..n-1 to maintain a bezel around the edge
    for jj in range(1,idomain2.shape[0]-1):
        for ii in range(1,idomain2.shape[1]-1):
            domain2[jj,ii] = (idomain2[jj+1,ii] and idomain2[jj-1,ii] and idomain2[jj,ii+1] and idomain2[jj,ii-1])
    return domain2
# --------------------------------------------------------
def get_div_curl(vvel2, uvel2, divable_data2, dyx=(1.,1.)):
    """Computes divergence and curl of a (v,u) velocity field.

    vvel2: ndarray(j,i)
        y component of velocity field
    uvel2: ndarray(j,i)
        x component of velocity field
    divable_data2: ndarray(j,i, dtype=bool)
        Map of points in domain where to compute divergence and curl
        See get_divable()
    dyx:
        Size of gridcells in y and x dimensions.
        By default set to 1, because having div and cur scaled similarly to the
        original values works best to make a balanced LSQR matrix.

    Returns: (div, curl) ndarray(j,i)
        Returns divergence and curl, computed on the domain divable_data2
    """

    n1 = divable_data2.shape[0] * divable_data2.shape[1]

    # ------------ Create div matrix on DATA points
    rows = list()
    cols = list()
    vals = list()
    dc_matrix((d_dy_present, d_dx_present),
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
def main():
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


    vsvel2 = cut_subset(vsvel2)
    usvel2 = cut_subset(usvel2)

    # ------------ Read amount of ice (thickness)
    rhoice = 918.    # [kg m-3]: Convert thickness from [m] to [kg m-2]
    with netCDF4.Dataset('outputs/bedmachine/W69.10N-thickness.nc') as nc:
        amount2 = nc.variables['thickness'][:].astype(np.float64) * rhoice

    amount2 = cut_subset(amount2)
    # Filter amount, it's from a lower resolution
    amount2 = scipy.ndimage.gaussian_filter(amount2, sigma=2.0)

    # ------------ Convert surface velocities to volumetric velocities
    vvel2 = vsvel2 * amount2
    uvel2 = usvel2 * amount2

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
        nc.createVariable('vvel', 'd', ('y','x'))[:] = vvel2
        nc.createVariable('uvel', 'd', ('y','x'))[:] = uvel2

    div2,curl2 = get_div_curl(vvel2, uvel2, divable_data2)

    # ---------- Apply Poisson Fill to curl
    curl2_m = np.ma.array(curl2, mask=(np.isnan(curl2)))
    curl2_fv,_ = fill_missing_petsc.fill_missing(curl2_m)
    curl2_f = curl2_fv[:].reshape(curl2.shape)

    # ---------- Apply Poisson Fill to div
    div2_m = np.ma.array(div2, mask=(np.isnan(div2)))
    div2_fv,_ = fill_missing_petsc.fill_missing(div2_m)
    div2_f = div2_fv[:].reshape(div2.shape)


    div2_f[:] = 0
#    curl2_f[:] = 0

    # --------- Redo the domain (smap_used)
    domain_used2 = get_divable(dmap2 != D_UNUSED)
    domain_used2 = np.ones(dmap2.shape, dtype=bool)
    domain_used2[0,:] = False
    domain_used2[-1,:] = False
    domain_used2[:,0] = False
    domain_used2[:,-1] = False

    # ------------ Create div matrix on all domain points
    rows = list()
    cols = list()
    vals = list()
#    dyx = (5000, 5000)
    dyx = (1.,1.)
    dc_matrix((d_dy_present, d_dx_present), domain_used2,
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
        # How much to fit original U/V data
        # Larger --> Avoids changing original data, but more stippling
        prior_weight = 0.8
        for jj in range(0, divable_data2.shape[0]):
            for ii in range(0, divable_data2.shape[1]):

                if dmap2[jj,ii] == D_DATA:

                    ku = indexing_data.tuple_to_index((jj,ii))
                    try:
                        rows.append(len(bb))
                        cols.append(ku)
                        vals.append(prior_weight*1.0)
                        bb.append(prior_weight*vvel2[jj,ii])

                        rows.append(len(bb))
                        cols.append(n1 + ku)
                        vals.append(prior_weight*1.0)
                        bb.append(prior_weight*uvel2[jj,ii])

                    except KeyError:    # It's not in sub_used
                        pass

    print('rows ', sum(1 if np.isnan(x) else 0 for x in rows))
    print('cols ', sum(1 if np.isnan(x) else 0 for x in cols))
    print('vals ', sum(1 if np.isnan(x) else 0 for x in vals))
    print('bb ', sum(1 if np.isnan(x) else 0 for x in bb))

    # ----------- Remove unused rows

    print(' *********** bb nan2 ', np.sum(np.isnan(bb)))
    print('M0 shape ',(len(bb), n1*2))
    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(len(bb),n1*2)).tocsc()
    rhs = np.array(bb)
    print('M len ', M.shape, len(rhs))
    print(' *********** rhs nan2 ', np.sum(np.isnan(rhs)))

    # ----------- Solve for vu_s
#    print('***** Matrix condition number: {}'.format(np.linalg.cond(M)))
    vu_s,istop,itn,r1norm,r2norm,anorm,acond,arnorm,xnorm,var = scipy.sparse.linalg.lsqr(M,rhs, damp=.0005)#, iter_lim=3000)

    # ----------- Convert back to full space
#    vu = np.zeros(n1*2) + np.nan
#    vu[cols_oldvnew] = vu_s
    vu = vu_s

    vv3 = np.reshape(vu[:n1], dmap2.shape)
    uu3 = np.reshape(vu[n1:], dmap2.shape)

    div3,curl3 = get_div_curl(vv3, uu3, domain_used2)

    # Convert back to surface velocity
    vvs3 = vv3 / amount2
    vvs3[amount2==0] = np.nan
    uus3 = uu3 / amount2
    uus3[amount2==0] = np.nan



    # Smooth: because our localized low-order FD approximation introduces
    # stippling, especially at boundaries
    vvs3 = scipy.ndimage.gaussian_filter(vvs3, sigma=1.0)
    uus3 = scipy.ndimage.gaussian_filter(uus3, sigma=1.0)

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
        nc.createVariable('vsvel', 'd', ('y','x'))[:] = vsvel2
        nc.createVariable('usvel', 'd', ('y','x'))[:] = usvel2
        nc.createVariable('vvel', 'd', ('y','x'))[:] = vvel2
        nc.createVariable('uvel', 'd', ('y','x'))[:] = uvel2
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

        nc.createVariable('vvs3', 'd', ('y','x'))[:] = vvs3
        nc.createVariable('uus3', 'd', ('y','x'))[:] = uus3

        nc.createVariable('div3', 'd', ('y','x'))[:] = div3
        nc.createVariable('curl3', 'd', ('y','x'))[:] = curl3

        nc.createVariable('vv3_diff', 'd', ('y','x'))[:] = vvs3-vsvel2
        nc.createVariable('uu3_diff', 'd', ('y','x'))[:] = uus3-usvel2





main()
