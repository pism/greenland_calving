from osgeo import ogr

shapefile = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Gletsjer_closed_v1.0.shp'
shapefile = 'oneshape.shp'

src_ds = ogr.Open(shapefile)
src_lyr=src_ds.GetLayer('oneshape')

print(src_lyr)
