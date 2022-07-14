import functools
import xlrd
import uafgi.data
from uafgi.util import pdutil
import os
import pandas as pd
import numpy as np

def _fixup(x):
    if isinstance(x, str):
        return x.strip()
    return x

@functools.lru_cache()
def read(map_wkt):

    # Open the worksheet
    ddir = uafgi.data.join('rignot2012')
    ifname = os.path.join(ddir, 'grl29178-sup-0002-ts01.xls')
    workbook = xlrd.open_workbook(ifname)
    sheet = workbook.sheet_by_index(0)

    rows = [[_fixup(cell.value) for cell in sheet.row(ri)] for ri in range(sheet.nrows)]
    rows = [row for row in rows if not all(r=='' for r in row)]    # Remove blank lines at end

    headers = ['glacier_name', 'reference', 'ice_speed', 'lat', 'lon', 'type', 'region', 'rignotid', 'drainage_area', 'cumulative_area', 'cumulative_area_pct', 'tw_cumulative_area', 'tw_cumulative_area_pct']

    headers = [
        ('glacier_name', str),
        ('reference', str),
        ('ice_speed', np.float64),
        ('lat', np.float64),
        ('lon', np.float64),
        ('type', str),
        ('region', str),
        ('rignotid', np.int32),
        ('drainage_area', np.float64),
        ('cumulative_area', np.float64),
        ('cumulative_area_pct', np.float64),
        ('tw_cumulative_area', np.float64),
        ('tw_cumulative_area_pct', np.float64),
    ]

    units = rows[3]
    vals = rows[4:]
    df = pd.DataFrame(vals, columns=[h for h,_ in headers])

    # replace field that's entirely space (or empty) with NaN
#    df = df.replace(r'^\s*$', np.nan, regex=True)

#    # Set types
#    for h,t in headers:
#        df[h] = df[h].astype(t)

#    print(list(zip(df.columns, df.dtypes)))

    return pdutil.ext_df(df, map_wkt, add_prefix='r12_',
        keycols=['rignotid'],
        lonlat=('lon','lat'))
#        namecols=['glac'])


# This would be the right code for .xlsx format
# import openpyxl
#@functools.lru_cache()
#def read(map_wkt):
#
#    # Open the worksheet
#    ddir = uafgi.data.join('rignot2012')
#    ifname = os.path.join(ddir, 'grl29178-sup-0002-ts01.xls')
#    workbook = openpyxl.load_workbook(ifname, read_only=True, data_only=True)    # data_only=True: Read values, not formulas
#    sheet = next(workbook)
#    rows = [[cell.value for cell in row] for row in sheet.rows]
#
#    headers = ['glacier_name', 'reference', 'ice_speed', 'lat', 'lon', 'type', 'region', 'rignotid', 'drainage_area', 'cumulative_area', 'cumulative_area_pct', 'tw_cumulative_area', 'tw_cumulative_area_pct']
#    units = rows[3]
#    vals = rows[4:]
#    df = pd.DataFrame(vals, columns=headers)
#
#    return df
#
