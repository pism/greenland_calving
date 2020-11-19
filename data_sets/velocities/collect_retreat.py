import re
import os
import netCDF4
import pandas as pd

def collect_retreat():
    odir = 'outputs'
    fnameRE = re.compile('retreat_calfin_W71.65N_{\d\d\d\d\d\d\d\d}_{\d\d\d\d\d\d\d\d}.nc')

    dt0 = list()
    dt1 = list()
    adv_data = list()
    ret_data = list()
    adv_model = list()
    ret_model = list()
    for fname in os.listdir(odir):
        match = fnameRE.match(fname)
        if match is None:
            continue
        dt0.append(datetime.datetime.strptime(match.group(1), '%Y%m%d').date())
        dt1.append(datetime.datetime.strptime(match.group(2), '%Y%m%d').date())

        with netCDF4.Dataset(os.path.join(odir, fname)) as nc:
            adv_data.append(nc.adv_data)
            ret_data.append(nc.ret_data)
            adv_model.append(nc.adv_model)
            ret_model.append(nc.ret_model)

    df = pd.DataFrame(
        {'dt0' : dt0,
        'dt1' : dt1,
        'adv_data' : adv_data,
        'ret_data' : ret_data,
        'adv_model' : adv_model,
        'ret_model' : ret_model})
    return df

        

df = collect_retreat()
df.to_csv('retreats.csv')
