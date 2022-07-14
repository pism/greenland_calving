import numpy as np
import pandas as pd
from uafgi.data import stability as d_stability
from uafgi.data import d_r12
import uafgi.data.wkt

def igs_names(df):
    igs_names = list()
    for _,row in df.iterrows():
        names = list()

        gname = row['gname']
        if gname == 'g':
            gname = row['greenlandic_name']
        elif gname == 'r':
            gname = row['r12_glacier_name']
        elif gname == 'w':
            gname = row['w21t_Glacier']

        if isinstance(gname, str):
            names.append(gname)

        fname = row['fname']
        if fname == 'g':
            fname = row['greenlandic_name']
        elif fname == 'r':
            fname = row['r12_glacier_name']
        elif fname == 'w':
            fname = row['w21t_Glacier']

        if isinstance(fname, str):
            names.append(f'({fname})')

        igs_names.append(' '.join(names))
    return igs_names

def main():
    map_wkt = uafgi.data.wkt.nsidc_ps_north
    fname = uafgi.data.join('stability_overrides', 'study_glaciers_overrides.csv')
    df = pd.read_csv(fname)

    df['igs_name'] = igs_names(df)
    df['sl19_rignotid'] = df.sl19_rignotid.astype('i')

    df = df[['w21t_glacier_number', 'sl19_rignotid', 'igs_name', 'w21t_Glacier', 'r12_glacier_name', 'greenlandic_name', 'w21t_lon', 'w21t_lat', 'rs_slope']]
    ofname = uafgi.data.join_outputs('stability', 'study_glaciers_igs_names.csv')
    df.to_csv(ofname)

main()
