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

def d_dy_present(data, domain,dy, smap,  rows,cols,vals, factor=1.0, rowoffset=0, coloffset=0):
    """Produces a matrix for the del operator
       rows,cols,vals:
            Matrix M
    """
    bydy = 1. / dy

    for k in range(0,len(smap)):
        jj = smap.sub2j[k]
        ii = smap.sub2i[k]

#        print('({}, {}): {}'.format(jj, ii, domain[jj-1:jj+2,ii]))

        # Decide on stencil, based position in the domain
        if not domain[jj-1,ii]:
            stencil = right_diff
        elif not domain[jj+1,ii]:
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
def d_dx_present(data, domain,dx, smap,  rows,cols,vals,
    factor=1.0, rowoffset=0, coloffset=0):

    d_dy_present(np.transpose(data), np.transpose(domain),dx, smap.transpose(),
        rows,cols,vals,
        factor=factor, rowoffset=rowoffset, coloffset=coloffset)
# ----------------------------------------------------------------
# d_dy_fns(present)
d_dyx_fns = {
    True : (d_dy_present, d_dx_present),
}

# ----------------------------------------------------------------
def div_matrix(d_dyx, vvel2,uvel2, domain, dyx, smap, rows,cols,vals,
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
    d_dyx[0](vvel2, domain, dyx[0], smap, rows,cols,vals,
        factor=factor, rowoffset=rowoffset)
    d_dyx[1](uvel2, domain, dyx[1], smap, rows,cols,vals,
        factor=factor, rowoffset=rowoffset, coloffset=len(smap))


def curl_matrix(d_dyx, vvel2,uvel2, domain, dyx, smap, rows,cols,vals,
    factor=1.0, rowoffset=0):
    """Generates a matrix to compute divergence of a vector field.
    (v and u are stacked)

    vu1:
        1D matrix of U component of velocity, followed by V component
    shape:
        Shape of the original finite difference grid
    """
    # curl = del x F = dF_y/dx - dF_x/dy
    d_dyx[1](vvel2, domain, dyx[1], smap, rows,cols,vals,
        factor=factor, rowoffset=rowoffset)
    d_dyx[0](uvel2, domain, dyx[0], smap, rows,cols,vals,
        factor=-factor, rowoffset=rowoffset, coloffset=len(smap))

# -------------------------------------------------------
def dc_matrix(d_dyx, vvel2,uvel2, domain2, dyx, smap, rows,cols,vals,
    factor=1.0):

    n1 = len(smap)

    div_matrix(d_dyx_fns[True], vvel2,uvel2, domain2, dyx, smap, rows,cols,vals)
    curl_matrix(d_dyx_fns[True], vvel2,uvel2, domain2, dyx, smap, rows,cols,vals, rowoffset=n1)


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
def get_div_curl(vvel2, uvel2, domain_data2, smap_data):

    n1 = len(smap_data)

    # ------------ Create div matrix on DATA points
    rows = list()
    cols = list()
    vals = list()
#    dyx = (5000, 5000)
    dyx = (1.,1.)
    dc_matrix(d_dyx_fns[True], vvel2,uvel2,
        domain_data2,
        dyx,smap_data, rows,cols,vals)
    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(n1*2, n1*2))

    # ------------ Construct vu vector based on smap_data
    vu_s = np.zeros(n1*2)
    vu_s[:n1] = vvel2[smap_data.sub2j, smap_data.sub2i]
    vu_s[n1:] = uvel2[smap_data.sub2j, smap_data.sub2i]

    # ------------ Compute div/curl

    # ... in subspace
    divcurl_s = M * vu_s
    div_s = divcurl_s[:n1]
    curl_s = divcurl_s[n1:]

    # ... convert back to main space
    div2 = np.zeros(vvel2.shape) + np.nan
    div2[smap_data.sub2j, smap_data.sub2i] = div_s
    curl2 = np.zeros(vvel2.shape) + np.nan
    curl2[smap_data.sub2j, smap_data.sub2i] = curl_s

    return div2,curl2

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

    # Make an "unused" border
    dmap2[0,:] = D_UNUSED
    dmap2[-1,:] = D_UNUSED
    dmap2[:,0] = D_UNUSED
    dmap2[:,-1] = D_UNUSED

    # ------------ Select subspace of gridcells on which to operate

    # Select cells with data
    # *** TODO: This is wonky
    domain_data2 = (dmap2 == D_DATA)
    remove_singletons(domain_data2, dmap2)
    subj,subi = np.where(domain_data2)
    smap_data = SubMap(uvel2.shape, subj,subi)
    n1 = len(smap_data)

    # ----------- Store it
    with netCDF4.Dataset('dmap.nc', 'w') as nc:
        nc.createDimension('y', vvel2.shape[0])
        nc.createDimension('x', vvel2.shape[1])
        ncv = nc.createVariable('dmap', 'i', ('y','x'))
        ncv[:] = dmap2[:]
        ncv = nc.createVariable('amount', 'd', ('y','x'))
        ncv[:] = amount2[:]
        ncv = nc.createVariable('domain_data', 'i', ('y','x'))
        ncv[:] = domain_data2[:]

    div2,curl2 = get_div_curl(vvel2, uvel2, domain_data2, smap_data)

    # ---------- Apply Poisson Fill to curl
    curl2_m = np.ma.array(curl2, mask=(np.isnan(curl2)))
    curl2_fv,_ = fill_missing_petsc.fill_missing(curl2_m)
    curl2_f = curl2_fv[:].reshape(curl2.shape)

    # ---------- Apply Poisson Fill to div
    div2_m = np.ma.array(div2, mask=(np.isnan(div2)))
    div2_fv,_ = fill_missing_petsc.fill_missing(div2_m)
    div2_f = div2_fv[:].reshape(div2.shape)


    div2_f[:] = 0
    curl2_f[:] = 0

    # --------- Redo the domain (smap_used)
    domain_used2 = (dmap2 != D_UNUSED)
    remove_singletons(domain_used2, dmap2)
    subj,subi = np.where(domain_used2)
    smap_used = SubMap(uvel2.shape, subj,subi)
    n1 = len(smap_used)

    # ------------ Create div matrix on all domain points
    rows = list()
    cols = list()
    vals = list()
#    dyx = (5000, 5000)
    dyx = (1.,1.)
    dc_matrix(d_dyx_fns[True], vvel2,uvel2, domain_used2,
        dyx,smap_used, rows,cols,vals)

    # ----------- Create dc vector in subspace as right hand side
    dc_s = np.zeros(n1*2)
    dc_s[:n1] = div2_f[smap_used.sub2j, smap_used.sub2i]
    dc_s[n1:] = curl2_f[smap_used.sub2j, smap_used.sub2i]
    bb = dc_s.tolist()
    print(' *********** bb nan ', np.sum(np.isnan(bb)))
#PROBLEM: This has NaNs!!!!!


    # ------------ Add additional constraints for original data
#    rows = list()
#    cols = list()
#    vals = list()
#    bb = list()

    for kd in range(0,len(smap_data)):
        jj = smap_data.sub2j[kd]
        ii = smap_data.sub2i[kd]

#        print(jj,ii)
#        if domain_data2[jj+1,ii] and domain_data2[jj-1,ii] and domain_data2[jj,ii+1] and domain_data2[jj,ii-1]:
#            continue


#        print('All data: ',jj,ii,domain_data2[jj+1,ii], domain_data2[jj-1,ii], domain_data2[jj,ii+1], domain_data2[jj,ii-1])

#            continue

        try:
            ku = smap_used.ji2sub[jj,ii]
            rows.append(len(bb))
            cols.append(ku)
            vals.append(.01*1.0)
            bb.append(.01*vvel2[jj,ii])

            rows.append(len(bb))
            cols.append(len(smap_used) + ku)
            vals.append(.01*1.0)
            bb.append(.01*uvel2[jj,ii])

        except KeyError:    # It's not in sub_used
            pass

    print('rows ', sum(1 if np.isnan(x) else 0 for x in rows))
    print('cols ', sum(1 if np.isnan(x) else 0 for x in cols))
    print('vals ', sum(1 if np.isnan(x) else 0 for x in vals))
    print('bb ', sum(1 if np.isnan(x) else 0 for x in bb))

    # ----------- Convert to a (rectangular) matrix
    M = scipy.sparse.coo_matrix((vals, (rows,cols)),
        shape=(len(bb), n1*2)).tocsc()
    print('nrows= ', len(bb))
    rhs = np.array(bb)

    # ----------- Solve for vu_s
#    print('***** Matrix condition number: {}'.format(np.linalg.cond(M)))
    vu_s,istop,itn,r1norm,r2norm,anorm,acond,arnorm,xnorm,var = scipy.sparse.linalg.lsqr(M,rhs, damp=.0005)
#    vu_s,istop,itn,normr,normar,norma,conda,normx = scipy.sparse.linalg.lsmr(M,rhs, damp=0.0005, maxiter=1000)
#    print(vu_s)
#    vu_s = scipy.sparse.linalg.spsolve(M, dc_s)
#    lu = scipy.sparse.linalg.splu(M)

#    print('shape: ', M.shape, dc_s.shape)
#    vu_s = lu.solve(dc_s)
#    print('dc_s ', dc_s[:100])
#    print('vu_s ', vu_s[:100])

    # ----------- Convert back to full space
    vv3 = smap_used.decode(vu_s[:n1])
    uu3 = smap_used.decode(vu_s[n1:])

    div3,curl3 = get_div_curl(vv3, uu3, domain_used2, smap_used)


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
