from osgeo import gdal


# Classification values
OCEAN = 3
CLOUD = 2
ICE = 1
SNOW = 0



def read_geotiff(fname, iband):

    # open dataset
    ds = gdal.Open(fname)
    srcband = ds.GetRasterBand(iband)
    return srcband.ReadAsArray()



    print('count ', ds.RasterCount)
    for band in range(1,ds.RasterCount+1):
        print("[ GETTING BAND ]: ", band)
        srcband = ds.GetRasterBand(band)
        arr = srcband.ReadAsArray()
        print(arr.shape)

#        if srcband is None:
#            continue



#        stats = srcband.GetStatistics( True, True )
#        if stats is None:
#            continue

#        print("[ STATS ] =  Minimum=%.3f, Maximum=%.3f, Mean=%.3f, StdDev=%.3f" % ( \
#                    stats[0], stats[1], stats[2], stats[3] ))





read_geotiff('data/snowline/20120715_classification.tif')
