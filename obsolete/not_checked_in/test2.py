from uafgi import gdalutil

grid_file = 'data/measures/grids/W69.10N_grid.nc'
fb = gdalutil.FileInfo(grid_file)

for j in range(0,3):
    for i in range(0,3):
        x,y = fb.to_xy(i,j)
        x -= 51
        y -= 51
        i2,j2 = fb.to_ij(x,y)

        print('({}, {}) ({}, {}) ({}, {})'.format(i,j,x,y,i2,j2))
