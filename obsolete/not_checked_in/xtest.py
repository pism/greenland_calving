import subprocess
from uafgi import cdoutil,gdalutil,ioutil
from uafgi.pism import flow_simulation
import uafgi.data

ns481_grid = 'W69.10N'


if True:
    velocity_file = uafgi.data.join_outputs('itslive', 'GRE_G0240_{}_1985_2018.nc'.format(ns481_grid))

    output_file = './x.nc'
    with ioutil.TmpDir('.') as tdir:
        flow_simulation.get_von_Mises_stress_gimpdem(17, ns481_grid, velocity_file, output_file, tdir)

#    output_file = './xall.nc'
#    with ioutil.TmpDir('.') as tdir:
#        flow_simulation.compute_sigma(velocity_file, 'x.nc', tdir)


if False:
    gimpdem_tif = uafgi.data.join('gimpdem-nsidc0645', 'gimpdem_90m_v01.1.tif')
    grid_file = uafgi.data.measures_grid_file(ns481_grid)
    fb = gdalutil.FileInfo(grid_file)
    ofname = 'x.nc'

    cmd = ['gdal_translate',
        '-r', 'average',
        '-projwin', str(fb.x.low), str(fb.y.high), str(fb.x.high), str(fb.y.low),
        '-tr', str(fb.x.delta), str(fb.y.delta),
        gimpdem_tif,
        ofname]

    subprocess.run(cmd, check=True)

    cmd = ['ncrename', '-v', 'Band1,elevation', ofname]
    subprocess.run(cmd, check=True)


