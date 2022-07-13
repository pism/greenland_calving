import functools
import openpyxl
import uafgi.data
import os

@functools.lru_cache()
def read(map_wkt):

    # Open the worksheet
    ddir = uafgi.data.join('rignot2012')
    ifname = os.path.join(ddir, 'grl29178-sup-0002-ts01.xls')
    workbook = openpyxl.load_workbook(ifname, read_only=True, data_only=True)    # data_only=True: Read values, not formulas
    sheet = next(workbook)
    rows = [[cell.value for cell in row] for row in sheet.rows]

    headers = ['glacier_name', 'reference', 'ice_speed', 'lat', 'lon', 'type', 'region', 'rignotid', 'drainage_area', 'cumulative_area', 'cumulative_area_pct', 'tw_cumulative_area', 'tw_cumulative_area_pct']
    units = rows[3]
    vals = rows[4:]
    df = pd.DataFrame(vals, columns=headers)

    return df
