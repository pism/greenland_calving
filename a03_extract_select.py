import pyproj
import os
import uafgi.data.wkt
from uafgi.data import stability as d_stability

# Extract only KEY columns from the master select table.
# (Avoid redistributing others' data)

def transformer_wkt_to_wgs84(wkt1):
    """Creates a transformer from map projection to lon/lat.
    wkt1: WKT string
        The map projection being used (our favorite stereographic in this case)
    """
    # Get map projection
    crs0 = pyproj.CRS.from_string(wkt1)

    # Get WGS84
    crs1 = pyproj.CRS.from_string("epsg:4326")

    # Converts from crs0 to crs1
    # See for always_xy: https://proj.org/faq.html#why-is-the-axis-ordering-in-proj-not-consistent
    return pyproj.Transformer.from_crs(crs0, crs1, always_xy=True)


map_wkt = uafgi.data.wkt.nsidc_ps_north
stability = d_stability.read_select(map_wkt)

print(stability.df.iloc[0].to_string())


# Convert up_loc to lon/lat; avoid unusual datatypes in the dataframe
to_wgs84 = transformer_wkt_to_wgs84(map_wkt)
col_lonlat = stability.df.up_loc.map(lambda pt: to_wgs84.transform(pt.x, pt.y))
stability.df['up_lon'] = col_lonlat.map(lambda pt: pt[0])
stability.df['up_lat'] = col_lonlat.map(lambda pt: pt[1])


# Select out columns for data publication
df = stability.df[['w21t_Glacier', 'w21t_glacier_number', 'w21t_lon', 'w21t_lat', 'w21_key', 'fj_fid', 'ns481_grid', 'up_fid', 'up_id', 'up_lon', 'up_lat', 'bkm15_id', 'cf20_key', 'cf20_glacier_id', 'ns642_GlacierID', 'sl19_bjorkid', 'sl19_rignotid', 'sl19_key']]

odir = os.path.join('outputs', 'stability')

os.makedirs(odir, exist_ok=True)
#df.to_pickle(os.path.join(odir, '01_select_extract.df'))
df.to_csv(os.path.join(odir, '01_select_extract.csv'))
