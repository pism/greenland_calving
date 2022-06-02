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
