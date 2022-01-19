# Manual code that was used (in Jupyter Notebook) to join in the bkm15
# dataset.  Join was done sem-manually by computing the distance from
# each bkm15 point to each fj fjord polygon.

select = pdutil.ExtDf.read_pickle('outputs/stability/01_select.dfx')
import uafgi.data.bkm15
bkm15 = uafgi.data.bkm15.read(uafgi.data.wkt.nsidc_ps_north)

from uafgi.data import stability
over = stability.read_overrides()

# -----------------------------------------------
distances = list()
for sel_ix,poly in select.df.fj_poly.items():
    for bkm15_ix,loc in bkm15.df.bkm15_loc.items():
        d = loc.distance(poly)
        distances.append((d, sel_ix, bkm15_ix))
print(sorted(distances))

# -----------------------------------
from osgeo import ogr
import shapely.geometry
importlib.reload(shputil)

overx_w21 = over.set_index('w21_key')
overx_bkm15 = over.set_index('bkm15_key')
sel_remain = set(select.df.index.tolist())
matches = list()
for dist,sel_ix,bkm15_ix in sorted(distances):

    # Avoid previoulsy matched fjord outlines; unless we have multiple inside the polygon
    if (dist != 0) and (sel_ix not in sel_remain):
        continue

    # It's just not a match..
    if dist > 50000:
        break

    w21_key = select.df.loc[sel_ix].w21_key
    bkm15_key = bkm15.df.loc[bkm15_ix].bkm15_id


    # Already matched this one!
#    print(overx.index)
    if w21_key in overx.index:
        try:
            sel_remain.remove(sel_ix)
        except KeyError:
            pass
        continue
    if bkm15_key in overx_bkm15.index:
        continue

    
    matches.append((dist,sel_ix,bkm15_ix))
    try:
        sel_remain.remove(sel_ix)
    except KeyError:
        pass

# -----------------------------------
from uafgi import shputil
with shputil.ShapefileWriter('match.shp' ,'Point', [('bkm15_id',ogr.OFTString)]) as shpout:
    # This file match.csv must be hand-edited, leaving on the lines that make sense
    with open('match.csv', 'w') as out:
        matches.sort(key=lambda x: (x[1], x[0]) )
        #print(matches)
        for dist,sel_ix,bkm15_ix in matches:
            w21_key = ','.join(select.df.loc[sel_ix].w21_key)

            sel_name = select.df.loc[sel_ix].w21t_Glacier

            bkm15_row = bkm15.df.loc[bkm15_ix]
            bkm15_name = bkm15_row.bkm15_allnames
            bkm15_name = [x for x in bkm15_name if isinstance(x, str)]
            bkm15_id = bkm15_row.bkm15_id
            bkm15_lon = bkm15_row.bkm15_lon
            bkm15_lat = bkm15_row.bkm15_lat
            shpout.write(shapely.geometry.Point(bkm15_lon,bkm15_lat), bkm15_id=bkm15_id)
            out.write('{},"{}",{},{},{},"{}"\n'.format(round(dist), w21_key, bkm15_id, bkm15_lon,bkm15_lat,','.join(bkm15_name)))
    
shpout = None
