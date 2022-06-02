from osgeo import ogr
import shapefile
from uafgi import shputil

# Read a shapefile of polygons, compute area of each.  This can be
# used to find the most-retreated terminus polygon, which should have
# the largest area.

fname_closed = 'data/calfin/domain-termini-closed/termini_1972-2019_Jakobshavn-Isbrae_closed_v1.0.shp'
fname_term = 'data/calfin/domain-termini/termini_1972-2019_Jakobshavn-Isbrae_v1.0.shp'

# with shapefile.Reader(fname) as sf:
#     for i in range(0, len(sf)):
#         shape = sf.polygon(i)
#         print(type(shape))
#         if shape.shapeType != shapefile.POLYGON:
#             raise ValueError('shapefile.POLYGON shapeType expected in file {}'.format(self.fname))
#         print(shape.__dict__)
#         print('{},{}'.format(i,shape.area))



dataSource = ogr.GetDriverByName("ESRI Shapefile").Open(fname_closed)
layer = dataSource.GetLayer()


schema = []
ldefn = layer.GetLayerDefn()
for n in range(ldefn.GetFieldCount()):
    fdefn = ldefn.GetFieldDefn(n)
    schema.append(fdefn.name)
print(schema)

polygons = list()
for id,feature in enumerate(layer):
    geom = feature.GetGeometryRef()
    area = geom.GetArea()
    attrs = [-area, id+1]
    attrs += [feature.GetFieldAsString(fd) for fd in ('Date', 'ImageID')]
    polygons.append(attrs)

polygons.sort()
id = polygons[0][1]
image_id0 = polygons[0][3]
print(polygons[0])

print(id)
shputil.select_feature(fname_closed, id, 'poly.shp')

#print(polygons[:5])
# ---------------------------------------------------


dataSource = ogr.GetDriverByName("ESRI Shapefile").Open(fname_term)
layer = dataSource.GetLayer()
for id,feature in enumerate(layer):
    image_id = feature.GetFieldAsString('ImageID')
    if image_id == image_id0:
        print(id, image_id)
        break

