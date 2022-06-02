from osgeo import ogr
import shapefile

# Read a shapefile of polygons, compute area of each.  This can be
# used to find the most-retreated terminus polygon, which should have
# the largest area.

fclosed = 'data/calfin/domain-termini-closed/termini_1972-2019_Jakobshavn-Isbrae_closed_v1.0.shp'
fterm = 'data/calfin/domain-termini/termini_1972-2019_Jakobshavn-Isbrae_v1.0.shp'

for fname in (fterm,fclosed):
    with shapefile.Reader(fname) as sf:
        print(len(sf))


    driver = ogr.GetDriverByName("ESRI Shapefile")
    dataSource = driver.Open(fname)
    layer = dataSource.GetLayer()


    schema = []
    ldefn = layer.GetLayerDefn()
    for n in range(ldefn.GetFieldCount()):
        fdefn = ldefn.GetFieldDefn(n)
        schema.append(fdefn.name)
    print(schema)
