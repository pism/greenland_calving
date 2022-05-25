import scipy.sparse.linalg
import scipy.sparse
import numpy as np
import netCDF4
import sys
from pism.util import fill_missing_petsc
import uafgi.indexing
import scipy.ndimage
import math
from scipy import signal
from numpy.fft  import fft2, ifft2
import scipy.ndimage

#np.set_printoptions(threshold=sys.maxsize)

# Enumerated values describing each gridcell
D_UNUSED = 0        # Not part of the domain
D_MISSING = 1       # Data are missing here
D_DATA = 2          # There are data here

# Indices and weights for first-order ceter fine difference.
center_diff = ((-1,1), (-.5,.5))

# https://laurentperrinet.github.io/sciblog/posts/2017-09-20-the-fastest-2d-convolution-in-the-world.html
def np_fftconvolve(A,B):
    return np.real(ifft2(fft2(A)*fft2(B, s=A.shape)))

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
#    return subval
    return val

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
# ----------------------------------------------------------
def disc_stencil(radius, dyx):
    """Creates a disc-shaped convolution stencil"""

    shape = tuple(math.ceil(radius*2. / dyx[i]) for i in range(0,2))
    st = np.zeros(shape, dtype='float32')
    for j in range(0,shape[0]):
        y  = (j+.5)*dyx[0]
        for i in range(0,shape[1]):
            x = (i+.5)*dyx[1]
            st[j,i] = (np.sqrt((y-radius)*(y-radius) + (x-radius)*(x-radius)) <= radius)

    return st


def get_dmap(values, thk, threshold, dist_channel, dist_front, dyx):
    """Creates a domain of gridcells within distance of cells in amount2
    that are >= threshold."""

    # Sobel-filter the amount variable
    sx = scipy.ndimage.sobel(thk, axis=0)
    sy = scipy.ndimage.sobel(thk, axis=1)
    sob = np.hypot(sx,sy)

    # Get original domain, where thickness is changing rapidly
    domain0 = (sob > threshold).astype('float32')

    # Create a disc-shaped mask, used to convolve
    stencil = disc_stencil(dist_channel, dyx)
    print('stencil shape ',stencil.shape)

    # Create domain of points close to original data points
    domain = (signal.convolve2d(domain0, stencil, mode='same') != 0)

    # Points with data
    data = (np.logical_not(np.isnan(values)))

    # Points close to the calving front
    # Get maximum value of Sobel fill.  This will be an ice cliff,
    # somewhere on the calving front.
    sobmax = np.max(sob)
    front = (sob >= .95*sobmax).astype('float32')
    fc = scipy.ndimage.measurements.center_of_mass(front)
    front_center = (fc[0]*dyx[0], fc[1]*dyx[1])

    # Create the dmap
    dmap = np.zeros(thk.shape, dtype='i') + D_UNUSED
    dmap[domain] = D_MISSING
    dmap[data] = D_DATA
    dmap[np.logical_not(domain)] = D_UNUSED
#    dmap[:] = D_DATA

    # Focus on area near calving front
    dthresh = dist_front*dist_front
    for j in range(0,dmap.shape[0]):
        y  = (j+.5)*dyx[0]
        y2 = (y-front_center[0])*(y-front_center[0])
        for i in range(0,dmap.shape[1]):
            x = (i+.5)*dyx[1]
            x2 = (x-front_center[1])*(x-front_center[1])
            if y2+x2 > dthresh:
                dmap[j,i] = D_UNUSED


    return dmap

# ----------------------------------------------------------
def reduce_column_rank(cols):
    col_set = dict((c,None) for c in cols)    # Keep order
    print('len(col_set) = {} -> {}'.format(len(cols), len(col_set)))
    mvs_cols = list(col_set.keys())
    svm_cols = dict((c,i) for i,c in enumerate(mvs_cols))
    cols_d = [svm_cols[c_s] for c_s in cols]
    print(cols_d[:100])
    return cols_d,mvs_cols

def reduce_row_rank(rows, bb):
    row_set = dict((c,None) for c in rows)    # Keep order
    print('len(row_set) = {} -> {}'.format(len(rows), len(row_set)))
    mvs_rows = list(row_set.keys())
    svm_rows = dict((c,i) for i,c in enumerate(mvs_rows))
    rows_d = [svm_rows[c_s] for c_s in rows]
#    bb_d = [svm_rows[c_s] for c_s in bb]
    bb_d = [bb[mvs_rows[i]] for i in range(0,len(mvs_rows))]
    return rows_d,bb_d,mvs_rows

# ----------------------------------------------------------
def fill_flow(vvel2, uvel2, dmap, clear_divergence=False, prior_weight=0.8):
    """
    vvel, uvel: ndarray(j,i)
        Volumetric flow fields (should have divergence=0)
    data_map: ndarray(j,i, dtype=bool)
        True where there is data, False elsewhere
    ice_map:
        True where there is ice, False elsewhere
    clear_divergence:
        if True, zero out the divergence when filling.
        Otherwise, just Poisson-fill existing (non-zero) divergence.
    prior_weight: 0-1
        The amount to weight rows that pin values to the origianl data.

    Returns: vvel_filled, uvel_filled, diagnostics
        Filled versions of vvel2, uvel2
    """

    diagnostics = dict()

    # ------------ Select subspace of gridcells on which to operate
    # Select cells with data
    divable_data2 = get_divable(dmap==D_DATA)
    indexing_data = get_indexing(divable_data2)

    # n1 = number of gridcells, even unused cells.
    # LSQR works OK with unused cells in its midst.
    n1 = dmap.shape[0] * dmap.shape[1]

    # -------------- Compute divergence and curl
    print('Computing divergence and curl')
    div2,curl2 = get_div_curl(vvel2, uvel2, divable_data2)
    diagnostics['div'] = div2
    diagnostics['curl'] = curl2

    # ---------- Apply Poisson Fill to div
    print('Applying Poisson fill')
    if clear_divergence:
        div2_f = np.zeros(dmap.shape)
    else:
        div2_m = np.ma.array(div2, mask=(np.isnan(div2)))
        div2_fv,_ = fill_missing_petsc.fill_missing(div2_m)
        div2_f = div2_fv[:].reshape(div2.shape)
        div2_f[:] = 0
    diagnostics['div_filled'] = div2_f

    # ---------- Apply Poisson Fill to curl
    curl2_m = np.ma.array(curl2, mask=(np.isnan(curl2)))
    curl2_fv,_ = fill_missing_petsc.fill_missing(curl2_m)
    curl2_f = curl2_fv[:].reshape(curl2.shape)
    diagnostics['curl_filled'] = curl2_f

    # ================================== Set up LSQR Problem
    rows = list()
    cols = list()
    vals = list()

    # --------- Setup domain to compute filled-in data EVERYWHERE
    # This keeps the edges of the domain as far as possible from places where
    # "the action" happens.  Edge effects can cause stippling problems.
#    divable_used2 = np.ones(data_map.shape, dtype=bool)
    divable_used2 = (dmap != D_UNUSED)
    # Make a bezel around the edge
    divable_used2[0,:] = False
    divable_used2[-1,:] = False
    divable_used2[:,0] = False
    divable_used2[:,-1] = False

    # ------------ Create div+cov matrix on all domain points.
    # This ensures our solution has the correct divergence and curl
    # This will include some empty rows and columns in the LSQR
    # matrix.  That is not a problem for LSQR.
    print('Computing div-curl matrix to invert')
    dyx = (1.,1.)
    dc_matrix((d_dy_present, d_dx_present), divable_used2,
        dyx, rows,cols,vals)

    # ----------- Create dc vector in subspace as right hand side
    # ...based on our filled divergence and curl from above
    dc_s = np.zeros(n1*2)
    dc_s[:n1] = np.reshape(div2_f, -1)
    dc_s[n1:] = np.reshape(curl2_f, -1)
    bb = dc_s.tolist()    # bb = right-hand-side of LSQR problem

    # ------------ Add additional constraints for original data
    # This ensures our answer (almost) equals the original, where we
    # had data.
    # Larger --> Avoids changing original data, but more stippling
    print('Adding additonal constraints')
    for jj in range(0, divable_data2.shape[0]):
        for ii in range(0, divable_data2.shape[1]):

            if dmap[jj,ii] == D_DATA:

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

    # ================= Solve the LSQR Problem
    ncols_s = n1*2
    cols_d,mvs_cols = reduce_column_rank(cols)    # len(cols)==n1*2
    nrows_s = len(bb)
    rows_d,bb_d,mvs_rows = reduce_row_rank(rows, bb)
#    rows_d = rows
#    bb_d = bb
#    mvs_rows = list(range(0,len(bb)))

    # ---------- Convert to SciPy Sparse Matrix Format
    M = scipy.sparse.coo_matrix((vals, (rows_d,cols_d)),
        shape=(len(mvs_rows),len(mvs_cols))).tocsc()
    print('LSQR Matrix complete: shape={}, nnz={}'.format(M.shape, len(vals)))
    rhs = np.array(bb_d)

    # ----------- Solve for vu
    print('Solving LSQR')
    vu_d,istop,itn,r1norm,r2norm,anorm,acond,arnorm,xnorm,var = scipy.sparse.linalg.lsqr(M,rhs, damp=.0005)#, iter_lim=100)

    vu = np.zeros(ncols_s) + np.nan
    vu[mvs_cols] = vu_d

    # ----------- Convert back to 2D
    vv3 = np.reshape(vu[:n1], dmap.shape)
    uu3 = np.reshape(vu[n1:], dmap.shape)


    return vv3, uu3, diagnostics

def fill_surface_flow(vsvel2, usvel2, amount2, dmap, clear_divergence=False, prior_weight=0.8):
    """
    vsvel2, usvel2: np.array(j,i)
        Surface velocities
    amount2: np.array(j,i)
        Ice depth; multiply surface velocity by this to get volumetric velocity
    amount2:
        Multiply surface velocity by this to get volumetric velocity
        Generally, could be depth of ice.
        (whose divergence should be 0)
    data_map: ndarray(j,i, dtype=bool)
        True where there is data, False elsewhere
    clear_divergence:
        if True, zero out the divergence when filling.
        Otherwise, just Poisson-fill existing (non-zero) divergence.
    prior_weight: 0-1
        The amount to weight rows that pin values to the origianl data.

    Returns: vvs3, uus3, (vvel2, uvel2, vvel_filled, uvel_filled)
        vvs3, uus3:
            Final filled and smothed surface velocities

        Intermediate values...
        vvel2,uvel2:
            Original non-filled volumetric velocities
        vvel_filled, uvel_filled:
            Filled volumetric velocities.
            Should have divergence=0
    """

    diagnostics = dict()


    # Get volumetric velocity from surface velocity
    vvel2 = vsvel2 * amount2
    uvel2 = usvel2 * amount2
    diagnostics['vvel'] = vvel2
    diagnostics['uvel'] = uvel2

    vvel_filled,uvel_filled,d2 = fill_flow(vvel2, uvel2, dmap, clear_divergence=clear_divergence, prior_weight=prior_weight)
    diagnostics.update(d2.items())
    diagnostics['vvel_filled'] = vvel_filled
    diagnostics['uvel_filled'] = uvel_filled

    # Convert back to surface velocity
    vvs3 = vvel_filled / amount2
    vvs3[amount2==0] = np.nan
    uus3 = uvel_filled / amount2
    uus3[amount2==0] = np.nan

    # Smooth: because our localized low-order FD approximation introduces
    # stippling, especially at boundaries
    # We need to smooth just over a single gridcell
    vvs3 = scipy.ndimage.gaussian_filter(vvs3, sigma=1.0)
    uus3 = scipy.ndimage.gaussian_filter(uus3, sigma=1.0)

    # Create pastiche of original + new
    missing2 = np.isnan(vsvel2)
    vvs4 = np.copy(vsvel2)
    vvs4[missing2] = vvs3[missing2]
    uus4 = np.copy(usvel2)
    uus4[missing2] = uus3[missing2]


    return vvs4, uus4, diagnostics



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


    vsvel2 = cut_subset(vsvel2)
    usvel2 = cut_subset(usvel2)

    # ------------ Read amount of ice (thickness)
    with netCDF4.Dataset('outputs/bedmachine/W69.10N-thickness.nc') as nc:
        thk2 = nc.variables['thickness'][:].astype(np.float64)

    thk2 = cut_subset(thk2)
    # Filter amount, it's from a lower resolution
    thk2 = scipy.ndimage.gaussian_filter(thk2, sigma=2.0)

    rhoice = 918.    # [kg m-3]: Convert thickness from [m] to [kg m-2]
    amount2 = thk2 * rhoice

    # ------------ Set up the domain map (classify gridcells)
    dmap = get_dmap(vsvel2, thk2, 300., 3000., 20000., (100.,100.))

    with netCDF4.Dataset('dmap.nc', 'w') as nc:
        nc.createDimension('y', vsvel2.shape[0])
        nc.createDimension('x', vsvel2.shape[1])
        nc.createVariable('amount', 'd', ('y','x'))[:] = amount2
        nc.createVariable('dmap', 'd', ('y','x'))[:] = dmap

    # ----------- Store it
    vv3,uu3,diagnostics = fill_surface_flow(vsvel2, usvel2, amount2, dmap,
        clear_divergence=True, prior_weight=0.8)
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
