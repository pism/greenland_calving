import zipfile
from uafgi.util import ioutil
import os
import shutil
import netCDF4
import re
import pandas as pd

odir = 'data/wood2021'

with ioutil.TmpDir(dir=odir) as tdir:
    with zipfile.ZipFile(os.path.join(odir, 'doi_10.7280_D1667w__v6-3.zip')) as zip:
        # ['Glacier_Data.zip', 'Greenland_Glacier_Ice_Front_Positions.zip', 'Greenland_Glacier_Retreat_Summary.pdf']
        zip.extract('Glacier_Data.zip', path=tdir.location)
        zip.extract('Greenland_Glacier_Ice_Front_Positions.zip', path=tdir.location)
        zip.extract('Greenland_Glacier_Retreat_Summary.pdf', path=odir)


    # Extract per-glacier data files
    with zipfile.ZipFile(os.path.join(tdir.location, 'Glacier_Data.zip')) as zip:
        # https://stackoverflow.com/questions/4917284/extract-files-from-zip-without-keeping-the-structure-using-python-zipfile
        for zip_info in zip.infolist():
            if zip_info.filename[-1] == '/':
                continue
            zip_info.filename = os.path.basename(zip_info.filename)
            zip.extract(zip_info, path=os.path.join(odir, 'data'))


    # Extract ice front positions
    with zipfile.ZipFile(os.path.join(tdir.location, 'Greenland_Glacier_Ice_Front_Positions.zip')) as zip:
        for zip_info in zip.infolist():
            if not zip_info.filename.startswith('Greenland_Glacier_Ice_Front_Positions'):
                continue
            zip.extract(zip_info, path=odir)

# Index the per-glacier files
data_dir = os.path.join(odir, 'data')
rows = list()
for fname in sorted(list(os.listdir(data_dir))):
    if not fname.endswith('.nc'):
        continue

    row = {'data_fname' : fname}
    with netCDF4.Dataset(os.path.join(data_dir, fname)) as nc:
        for aname in nc.ncattrs():
            row[aname] = nc.getncattr(aname)

    print('Indexing {}'.format(row['popular_name']))
    rows.append(row)

df = pd.DataFrame(data=rows)
print(df.columns)
df = df.sort_values(['glacier_number'])
df.to_csv(os.path.join(data_dir, 'index.csv'))
df.to_pickle(os.path.join(data_dir, 'index.df'))

