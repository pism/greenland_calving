from uafgi import pdutil,shputil
import uafgi.data
import uafgi.data.wkt
from uafgi.data import stability
from osgeo import ogr
import shapely.geometry
from uafgi.data import d_sl19

# Manual code that was used (in Jupyter Notebook) to join in the sl19
# dataset.  Join was done sem-manually by computing the distance from
# each sl19 point to each fj fjord polygon.

def main():
    select = pdutil.ExtDf.read_pickle('outputs/stability/01_select.dfx')
    # Only try to match glaciers we haven't already matched via bkm15
    select.df = select.df[select.df.sl19_rignotid.isna()]

    sl19 = d_sl19.read(uafgi.data.wkt.nsidc_ps_north)

    over = stability.read_overrides()

    # -----------------------------------------------
    distances = list()
    for sel_ix,poly in select.df.fj_poly.items():
        for sl19_ix,loc in sl19.df.sl19_loc.items():
            d = loc.distance(poly)
            distances.append((d, sel_ix, sl19_ix))
    print(sorted(distances))

#    return
    # -----------------------------------

    overx_w21 = over.set_index('w21_key')
    overx_sl19 = over.set_index('sl19_rignotid')
    sel_remain = set(select.df.index.tolist())
    matches = list()
    for dist,sel_ix,sl19_ix in sorted(distances):

        # Avoid previoulsy matched fjord outlines; unless we have multiple inside the polygon
        if (dist != 0) and (sel_ix not in sel_remain):
            continue

        # It's just not a match..
        if dist > 50000:
            break

        w21_key = select.df.loc[sel_ix].w21_key
        sl19_rignotid = sl19.df.loc[sl19_ix].sl19_rignotid


        # Already matched this one!
    #    print(overx.index)
        if w21_key in overx_w21.index:
            try:
                sel_remain.remove(sel_ix)
            except KeyError:
                pass
            continue
        if sl19_rignotid in overx_sl19.index:
            continue

        
        matches.append((dist,sel_ix,sl19_ix))
        try:
            sel_remain.remove(sel_ix)
        except KeyError:
            pass

    # -----------------------------------
    with shputil.ShapefileWriter('match.shp' ,'Point', [('sl19_rignotid',ogr.OFTInteger)]) as shpout:
        # This file match.csv must be hand-edited, leaving on the lines that make sense
        with open('match.csv', 'w') as out:
            out.write('distance,w21_key,sl19_rignotid,sl19_lon,sl19_lat,sl19_name')
            matches.sort(key=lambda x: (x[1], x[0]) )
            #print(matches)
            for dist,sel_ix,sl19_ix in matches:
                w21_key = ','.join(select.df.loc[sel_ix].w21_key)

                sel_name = select.df.loc[sel_ix].w21t_Glacier

                sl19_row = sl19.df.loc[sl19_ix]
                sl19_name = sl19_row.sl19_allnames
                sl19_name = [x for x in sl19_name if isinstance(x, str)]
                sl19_rignotid = int(sl19_row.sl19_rignotid)
                #print('rignotid {} {}'.format(type(sl19_rignotid), int(sl19_rignotid)))
                sl19_lon = sl19_row.sl19_lon
                sl19_lat = sl19_row.sl19_lat
                shpout.write(shapely.geometry.Point(sl19_lon,sl19_lat), sl19_rignotid=sl19_rignotid)
                out.write('{},"{}",{},{},{},"{}"\n'.format(round(dist), w21_key, sl19_rignotid, sl19_lon,sl19_lat,','.join(sl19_name)))
        
    shpout = None

main()
