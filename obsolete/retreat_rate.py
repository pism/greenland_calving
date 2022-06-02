import numpy as np
import netCDF4
from uafgi import glacier,ncutil,gdalutil
from osgeo import gdal,ogr,osr
import uafgi.data.wkt

sigma_max = 400000

wkt = uafgi.data.wkt.nsidc_ps_north
srs = osr.SpatialReference(wkt=wkt)

ifname = 'sample_retreat.nc'
#grid_info = gdalutil.FileInfo(ifname)
with netCDF4.Dataset(ifname) as ncin:
    schema = ncutil.Schema(ncin)
    grid = ncin.ns481_grid
    grid_file = uafgi.data.measures_grid_file(grid)
    grid_info = gdalutil.FileInfo(grid_file)

    L1 = ncin.variables['strain_rates[0]'][0,:]
    L2 = ncin.variables['strain_rates[1]'][0,:]
    fjord = np.isin(ncin.variables['fjord_classes'][:], glacier.ALL_FJORD)
    iasv = ncin.variables['ice_area_specific_volume'][1,:]

    sigma = glacier.von_mises_stress_eig(L1, L2)


    # Put our terminus raster into a GDAL datasource
#    terminus_ds = gdal.GetDriverByName('MEM').Create('', grid_info.nx, grid_info.ny, 1, gdal.GDT_Byte)
    terminus_ds = gdalutil.clone_geometry('MEM', '', grid_info, 1, gdal.GDT_Byte)
    terminus_ds.SetSpatialRef(srs)
    terminus_band = terminus_ds.GetRasterBand(1)
    terminus_r = (np.logical_and(iasv > 0, fjord)) * 1000.0


    # Terminus 1
    terminus_r = ncin.variables['thk'][0,:]
    terminus_r[np.logical_not(fjord)] = 0
    terminus_r = (terminus_r > 0) * 200.0

    # Terminus 2
#    terminus_r = ncin.variables['thk'][0,:]
#    terminus_r = (np.logical_or(terminus_r > 0, fjord)) * 200.0




    # Maybe need to do flipud???
    terminus_band.WriteArray(np.flipud(terminus_r))

    # Contour the terminus (and fjord)
    shp_ds = ogr.GetDriverByName("Memory").CreateDataSource('')
#    shp_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource('x.shp')
    layer0 = shp_ds.CreateLayer('contour', srs)
    layer0.CreateField(ogr.FieldDefn('ID', ogr.OFTInteger))
    layer0.CreateField(ogr.FieldDefn('elev', ogr.OFTReal))
    gdal.ContourGenerate(
        terminus_band, 50, 0, [1.e-4], 1, -32768., layer0, 0, 1)
    defn = layer0.GetLayerDefn()

#    shp_ds = None
#    shp_ds = ogr.GetDriverByName("ESRI Shapefile").Open('x.shp')
#    layer0 = shp_ds.GetLayer(0)


    # Simplify and copy to an output shapefile
    shp_ds1 = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource('terminus.shp')
    layer1 = shp_ds1.CreateLayer('contour', srs)
    layer1.CreateField(ogr.FieldDefn('ID', ogr.OFTInteger))
    layer1.CreateField(ogr.FieldDefn('elev', ogr.OFTReal))
    featureDefn1 = layer1.GetLayerDefn()

    while True:
        feature0 = layer0.GetNextFeature()
        if feature0 is None:
            break
        geom0 = feature0.GetGeometryRef()
        geom1 = geom0.Simplify(50.0)
        print('points: {} {}'.format(geom0.GetPointCount(),geom1.GetPointCount()))
        feature1 = ogr.Feature(featureDefn1)
        feature1.SetGeometry(geom1)
        feature1.SetField('ID', feature0.GetField('ID'))
        feature1.SetField('elev', feature0.GetField('elev'))
        layer1.CreateFeature(feature1)



#
#
##    shp_ds.Destroy()
#
#    while True:
#        feature = layer.GetNextFeature()
#        if feature is None:
#            break
#        geom = feature.GetGeometryRef()
#        simple = geom.Simplify(20.0)
#
#
#        ring = geom
#        print('points: {}'.format(simple.GetPointCount()))
#
#    # Simplify...    
##    layer.Simplify(20.0)    # tolerance = 20m
#
#
#
##    with netCDF4.Dataset('y.nc', 'w') as ncout:
##        schema.create(ncout, var_kwargs={'zlib': True})
##        ncv = ncout.createVariable('sigma', 'd', ('time','y','x'))
##        schema.copy(ncin, ncout)
##        ncv[:] = sigma[:]
#
