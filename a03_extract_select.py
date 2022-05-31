import os
import uafgi.data.wkt
from uafgi.data import stability as d_stability

# Extract only KEY columns from the master select table.
# (Avoid redistributing others' data)

map_wkt = uafgi.data.wkt.nsidc_ps_north
stability = d_stability.read_select(map_wkt)

df = stability.df[['w21t_Glacier', 'w21t_glacier_number', 'w21_key', 'fj_poly', 'fj_fid', 'ns481_grid', 'up_fid', 'up_id', 'up_loc', 'bkm15_id', 'cf20_key', 'cf20_glacier_id', 'ns642_GlacierID', 'sl19_bjorkid', 'sl19_rignotid', 'sl19_key']]

odir = os.path.join('outputs', 'stability')

os.makedirs(odir, exist_ok=True)
df.to_pickle(os.path.join(odir, '01_select_extract.df'))
df.to_csv(os.path.join(odir, '01_select_extract.csv'))
