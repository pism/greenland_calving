import scipy.sparse.linalg
import scipy.sparse
import numpy as np
import netCDF4
import sys
from pism.util import fill_missing_petsc

np.set_printoptions(threshold=sys.maxsize)

D_UNUSED = 0    # Not part of the FD Domain
D_MISSING = 1       # Data are missing here
D_DATA = 2      # There is data here



# -------------------------------------------------------
right_diff = ((0,1), (-1.,1.))
center_diff = ((-1,1), (-.5,.5))
left_diff = ((-1,0), (-1.,1.))
nan_stencil = ((0,), (np.nan,))

stencil_choice = [
    center_diff,    # left and right are OK
    left_diff,      # rightnan
    right_diff,     # leftnan
    nan_stencil]    # Both are nan

# -------------------------------------------------------
class SubMap(object):
    def __init__(self, shape, subj, subi):
        self.shape = shape
        self.sub2j = subj
        self.sub2i = subi
        self.ji2sub = {(subj[k],subi[k]) : k for k in range(0,len(subj))}
#        for x in self.ji2sub.keys():
#            print(x)


        # Location of variables in the mega-vector
        self.n1 = len(self)
        self.vubase = 0
        self.vbase = self.vubase
        self.ubase = self.n1
        self.dcbase = self.n1*2
        self.dbase = self.dcbase
        self.cbase = self.dbase + self.n1

    def __len__(self):
        return len(self.sub2j)
    def transpose(self):
        return SubMap((self.shape[1],self.shape[0]), self.sub2i, self.sub2j)

    def decode(self, val_s, fill_value=np.nan):
        """Goes from subspace to full vector"""
        val = np.zeros(self.shape) + fill_value
        print(len(self.sub2j))
        print(len(self.sub2i))
        val[self.sub2j, self.sub2i] = val_s
        return val
# -------------------------------------------------------
def d_dy_missing(data, dmap,dy, smap,  rows,cols,vals,bb, factor=1.0, rowoffset=0, coloffset=0):
    """Produces a matrix for the del operator
       rows,cols,vals:
            Matrix M
        bb:
            Offset: dF/dx = M*vu + bb
    """
    bydy = 1. / dy

    for k in range(0,len(smap)):
        jj = smap.sub2j[k]
        ii = smap.sub2i[k]

        # Decide on stencil, based position in the domain
        if dmap[jj-1,ii] == D_UNUSED:
            stencil = right_diff
        elif dmap[jj+1,ii] == D_UNUSED:
            stencil = left_diff
        else:
            stencil = center_diff
        stcoo,stval = stencil

        # Apply the stencil
        for l in range(0,len(stcoo)):
            jj2 = jj+stcoo[l]

            if dmap[jj2,ii] == D_MISSING:
                # This cell is also mising; include in the matrix to solve for
                rows.append(rowoffset + k)
                cols.append(coloffset + smap.ji2sub[jj2, ii])
                vals.append(factor * stval[l] * bydy)

            else:
                # This cell is not missing; add to the RHS
                bb[rowoffset + k] += factor * stval[l] * data[jj2,ii]


def d_dy_present(data, dmap,dy, smap,  rows,cols,vals,bb, factor=1.0, rowoffset=0, coloffset=0):
    """Produces a matrix for the del operator
       rows,cols,vals:
            Matrix M
        bb:
            Offset: dF/dx = M*vu + bb
    """
    bydy = 1. / dy

    for k in range(0,len(smap)):
        jj = smap.sub2j[k]
        ii = smap.sub2i[k]

#        print('({}, {}): {}'.format(jj, ii, dmap[jj-1:jj+2,ii]))

        # Decide on stencil, based position in the domain
        if dmap[jj-1,ii] != D_DATA:
            stencil = right_diff
        elif dmap[jj+1,ii] != D_DATA:
            stencil = left_diff
        else:
            stencil = center_diff
        stcoo,stval = stencil

        # Apply the stencil
        for l in range(0,len(stcoo)):
            jj2 = jj+stcoo[l]
#            print('({}, {}) <- ({}, {}) ({}: {} {} {})'.format(jj,ii,jj2,ii,dmap[jj-1:jj+2,ii], stencil==left_diff,stencil==center_diff,stencil==right_diff))

            rows.append(rowoffset + k)
            cols.append(coloffset + smap.ji2sub[jj2, ii])
            vals.append(factor * stval[l] * bydy)


# ----------------------------------------------------------------
def d_dx_present(data, dmap,dx, smap,  rows,cols,vals,bb,
    factor=1.0, rowoffset=0, coloffset=0):

    d_dy_present(np.transpose(data), np.transpose(dmap),dx, smap.transpose(),
        rows,cols,vals,bb,
        factor=factor, rowoffset=rowoffset, coloffset=coloffset)

def d_dx_missing(data, dmap,dx, smap,  rows,cols,vals,bb,
    factor=1.0, rowoffset=0, coloffset=0):

    d_dy_missing(np.transpose(data), np.transpose(dmap),dx, smap.transpose(),
        rows,cols,vals,bb,
        factor=factor, rowoffset=rowoffset, coloffset=coloffset)

# ----------------------------------------------------------------
# d_dy_fns(present)
d_dyx_fns = {
    True : (d_dy_present, d_dx_present),
    False : (d_dy_missing, d_dx_missing),
}

# ----------------------------------------------------------------
def div_matrix(d_dyx, vvel2,uvel2, dmap, dyx, smap, rows,cols,vals,bb,
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
    d_dyx[0](vvel2, dmap, dyx[0], smap, rows,cols,vals,bb,
        factor=factor, rowoffset=rowoffset)
    d_dyx[1](uvel2, dmap, dyx[1], smap, rows,cols,vals,bb,
        factor=factor, rowoffset=rowoffset, coloffset=len(smap))


def curl_matrix(d_dyx, vvel2,uvel2, dmap, dyx, smap, rows,cols,vals,bb,
    factor=1.0, rowoffset=0):
    """Generates a matrix to compute divergence of a vector field.
    (v and u are stacked)

    vu1:
        1D matrix of U component of velocity, followed by V component
    shape:
        Shape of the original finite difference grid
    """
    # curl = del x F = dF_y/dx - dF_x/dy
    d_dyx[1](vvel2, dmap, dyx[0], smap, rows,cols,vals,bb,
        factor=factor, rowoffset=rowoffset)
    d_dyx[0](uvel2, dmap, dyx[1], smap, rows,cols,vals,bb,
        factor=-factor, rowoffset=rowoffset, coloffset=len(smap))

# -------------------------------------------------------
def cut_subset(val):
#    subval = val[406:420, 406:420]
    subval = val[306:520, 306:520]
    return subval

# -------------------------------------------------------
#def remove_singletons(domain2):
#
#    print('XX BEFORE: {}'.format(domain2[233:236,387]))
#
#    # If a cell is in our domain but surrounded by out-of-domain cells.. remove it
#    for jj in range(1, domain2.shape[0]-1):
#        for ii in range(1, domain2.shape[1]-1):
#            if domain2[jj,ii]:
#                if ((not domain2[jj-1,ii]) and (not domain2[jj+1,ii])) \
#                    or ((not domain2[jj,ii-1]) and (not domain2[jj,ii+1])):
#
#                    domain2[jj,ii] = False
#
#    print('XX AFTER: {}'.format(domain2[233:236,387]))
#
#    return domain2

def remove_singletons(domain2, dmap2):
    """domain2:
        Remove singletons of True in this variable
    dmap2:
        Change to D_UNUSED in this  variable"""

    nremoved = 1
    while nremoved > 0:
        nremoved = 0

        # If a cell is in our domain but surrounded by out-of-domain cells.. remove it
        for jj in range(1, domain2.shape[0]-1):
            for ii in range(1, domain2.shape[1]-1):
                if domain2[jj,ii]:
                    if ((not domain2[jj-1,ii]) and (not domain2[jj+1,ii])) \
                        or ((not domain2[jj,ii-1]) and (not domain2[jj,ii+1])):
                        dmap2[jj,ii] = D_UNUSED
                        domain2[jj,ii] = False
                        nremoved += 1

        print('nremoved = {}'.format(nremoved))

    return domain2


# -------------------------------------------------------
def vudc_equations(vv, uu, dmap,dyx, smap, div_f, curl_f):
    """Produces a matrix for the del operator
       rows,cols,vals:
            Matrix M
        bb:
            Offset: dF/dx = M*vu + bb


        Point with data
        ---------------
        u = ...
        v = ...
        d - l.c. of u/v of self and surrounding points = 0
        c - l.c. of u/v of self and surrounding points = 0

        Point missing data
        ------------------
        d = 0
        c = (fill value for curl)
        d - l.c. of u/v of self and surrounding points = 0
        c - l.c. of u/v of self and surrounding points = 0
    """

    rows = list()
    cols = list()
    vals = list()
    rhs = list()

    bydy = 1. / dyx[0]
    bydx = 1. / dyx[1]


    for k in range(0,len(smap)):
        jj = smap.sub2j[k]
        ii = smap.sub2i[k]

#        print('({}, {}): {}'.format(jj, ii, dmap[jj-1:jj+2,ii]))

        # Decide on stencil, based position in the domain
        if dmap[jj-1,ii] == D_UNUSED:
            stencil = right_diff
        elif dmap[jj+1,ii] == D_UNUSED:
            stencil = left_diff
        else:
            stencil = center_diff
        stcoo_j,stval_j = stencil

        # Decide on stencil, based position in the domain
        if dmap[jj,ii-1] == D_UNUSED:
            stencil = right_diff
        elif dmap[jj,ii+1] == D_UNUSED:
            stencil = left_diff
        else:
            stencil = center_diff
        stcoo_i,stval_i = stencil


        # Equations differ depending on whether we have data here
        if dmap[jj,ii] == D_DATA:
            # <v-variable> = v
            rows.append(len(rhs))
            cols.append(smap.vbase + k)
            vals.append(1.0)
            rhs.append(vv[jj,ii])

            # <u-variable> = u
            rows.append(len(rhs))
            cols.append(smap.ubase + k)
            vals.append(1.0)
            rhs.append(uu[jj,ii])

        else:    # No uv here
            # <div-variable> = 0
            rows.append(len(rhs))
            cols.append(smap.dbase + k)
            vals.append(1.0)
#            rhs.append(0)
            rhs.append(div_f[jj,ii])

            # <curl-variable> = curl-val
            rows.append(len(rhs))
            cols.append(smap.cbase + k)
            vals.append(1.0)
            rhs.append(curl_f[jj,ii])
#            rhs.append(0)


        # <div-var> - <div formula> = 0
        cols.append(smap.dbase + k)
        rows.append(len(rhs))
        vals.append(1.0)
        for l in range(0,len(stcoo_j)):
            jj2 = jj+stcoo_j[l]
            k2 = smap.ji2sub[jj2,ii]
            rows.append(len(rhs))
            cols.append(smap.vbase + k2)
            vals.append(-stval_j[l] * bydy)
        for l in range(0,len(stcoo_i)):
            ii2 = ii+stcoo_i[l]
            k2 = smap.ji2sub[jj,ii2]
            rows.append(len(rhs))
            cols.append(smap.ubase + k2)
            vals.append(-stval_i[l] * bydx)
        rhs.append(0.)

        # curl - <curl formula> = 0
        cols.append(smap.cbase + k)
        rows.append(len(rhs))
        vals.append(1.0)
        for l in range(0,len(stcoo_i)):    # dv/dx
            ii2 = ii+stcoo_i[l]
            k2 = smap.ji2sub[jj,ii2]
            rows.append(len(rhs))
            cols.append(smap.vbase + k2)
            vals.append(-stval_i[l] * bydx)
        for l in range(0,len(stcoo_j)):
            jj2 = jj+stcoo_j[l]
            k2 = smap.ji2sub[jj2,ii]        # -du/dy
            rows.append(len(rhs))
            cols.append(smap.ubase + k2)
            vals.append(stval_j[l] * bydy)
        rhs.append(0)

    # Convert to matrix form and return
    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(smap.n1*4, smap.n1*4)).tocsc()
    bb = np.array(rhs)
    return M,bb

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

    # Make an "unused" border
    dmap2[0,:] = D_UNUSED
    dmap2[-1,:] = D_UNUSED
    dmap2[:,0] = D_UNUSED
    dmap2[:,-1] = D_UNUSED

    # ------------ Select subspace of gridcells on which to operate
    process_present = True
    if process_present:
        # Select cells with data
        domain2 = (dmap2 == D_DATA)
        remove_singletons(domain2, dmap2)
    else:
        # Select NaN cells
        domain2 = remove_singletons(dmap2 != D_UNUSED, dmap2)
        domain2 = (dmap2 == D_MISSING)

    subj,subi = np.where(domain2)
    smap = SubMap(uvel2.shape, subj,subi)
    n1 = len(smap)


    # ---------- Put in a test value
#    for j in range(0,vvel2.shape[0]):
#        for i in range(0,vvel2.shape[1]):
#            vvel2[j,i] = i
#            uvel2[j,i] = i

    # ----------- Store it
    with netCDF4.Dataset('dmap.nc', 'w') as nc:
        nc.createDimension('y', vvel2.shape[0])
        nc.createDimension('x', vvel2.shape[1])
        ncv = nc.createVariable('dmap', 'i', ('y','x'))
        ncv[:] = dmap2[:]
        ncv = nc.createVariable('amount', 'd', ('y','x'))
        ncv[:] = amount2[:]
        ncv = nc.createVariable('domain', 'i', ('y','x'))
        ncv[:] = domain2[:]

    # ------------ Set up for div/curl matrix
    rows = list()
    cols = list()
    vals = list()
    bb = np.zeros(len(smap)*2)    # First missing vvels, then missing uvels

    # ------------ Create div matrix and RHS
    dyx = (5000, 5000)
    div_matrix(d_dyx_fns[process_present], vvel2,uvel2, dmap2, dyx, smap, rows,cols,vals,bb)
    curl_matrix(d_dyx_fns[process_present], vvel2,uvel2, dmap2, dyx, smap, rows,cols,vals,bb, rowoffset=n1)

    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(n1*2, n1*2))


    # ------------ Construct vu vector based on smap
    vu_s = np.zeros(n1*2)
    vu_s[:n1] = vvel2[smap.sub2j, smap.sub2i]
    vu_s[n1:] = uvel2[smap.sub2j, smap.sub2i]

    # ------------ Get result in subspace
    if process_present:
        divcurl_s = M * vu_s
        div_s = divcurl_s[:n1]
        curl_s = divcurl_s[n1:]

        #    print('div_s ',div_s)

        # ------------ Convert back to main space
        div2 = np.zeros(vvel2.shape) + np.nan
        div2[smap.sub2j, smap.sub2i] = div_s
        curl2 = np.zeros(vvel2.shape) + np.nan
        curl2[smap.sub2j, smap.sub2i] = curl_s

    else:
        pass


    # ---------- Apply Poisson Fill to curl
    curl2_m = np.ma.array(curl2, mask=(np.isnan(curl2)))
    curl2_fv,_ = fill_missing_petsc.fill_missing(curl2_m)
    curl2_f = curl2_fv[:].reshape(curl2.shape)

#    curl2_f = curl2
#    curl2_f[np.isnan(curl2)] = 0

    # ---------- Apply Poisson Fill to div
    div2_m = np.ma.array(div2, mask=(np.isnan(div2)))
    div2_fv,_ = fill_missing_petsc.fill_missing(div2_m)
    div2_f = div2_fv[:].reshape(div2.shape)


    # ---------- Redo smap
    domain2 = remove_singletons(dmap2 != D_UNUSED, dmap2)
    subj,subi = np.where(domain2)
    smap = SubMap(uvel2.shape, subj,subi)
    n1 = len(smap)

    # ---------- Solve for v,u,div,curl simultaneously
    M,bb = vudc_equations(vvel2, uvel2, dmap2, dyx, smap, div2_f, curl2_f)
    vudc,istop,itn,r1norm,r2norm,anorm,acond,arnorm,xnorm,var = scipy.sparse.linalg.lsqr(M,bb)
#        btol=1e-14)
    print('LSQR ',istop,itn,r1norm,r2norm)
#    vudc = scipy.sparse.linalg.spsolve(M,bb)
#    ew,ev = scipy.sparse.linalg.eigs(M)
#    print(ew)
#    print('eigs ', list(np.abs(x) for x in ew))
    n1 = smap.n1
    print('n1 ',n1)
    vv3 = smap.decode(vudc[smap.vbase:smap.vbase+n1])
    uu3 = smap.decode(vudc[smap.ubase:smap.ubase+n1])
    div3 = smap.decode(vudc[smap.dbase:smap.dbase+n1])
    curl3 = smap.decode(vudc[smap.cbase:smap.cbase+n1])


    # ----------- Store it
    with netCDF4.Dataset('x.nc', 'w') as nc:
        nc.createDimension('y', vvel2.shape[0])
        nc.createDimension('x', vvel2.shape[1])
        ncv = nc.createVariable('dmap', 'i', ('y','x'))
        ncv[:] = dmap2[:]
        ncv = nc.createVariable('amount', 'd', ('y','x'))
        ncv[:] = amount2[:]
        ncv = nc.createVariable('domain', 'i', ('y','x'))
        ncv[:] = domain2[:]
        ncv = nc.createVariable('vvel', 'i', ('y','x'))
        ncv[:] = vvel2[:]
        ncv = nc.createVariable('uvel', 'i', ('y','x'))
        ncv[:] = uvel2[:]
        if process_present:
            ncv = nc.createVariable('div', 'd', ('y','x'))
            ncv[:] = div2
            ncv = nc.createVariable('curl', 'd', ('y','x'))
            ncv[:] = curl2
            ncv = nc.createVariable('curl_f', 'd', ('y','x'))
            ncv[:] = curl2_f

        nc.createVariable('vv3', 'd', ('y','x'))[:] = vv3
        nc.createVariable('uu3', 'd', ('y','x'))[:] = uu3
        nc.createVariable('div3', 'd', ('y','x'))[:] = div3
        nc.createVariable('curl3', 'd', ('y','x'))[:] = curl3


main()
