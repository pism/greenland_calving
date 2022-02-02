import os
import subprocess
import pandas as pd

odir = 'tw_plots2'

def main():
    resid_df = pd.read_pickle('16_slfit.df')

    pro = list()
    con = list()
    insig = list()
    for ix,row in resid_df.iterrows():
        print(row)
        rlr = row.resid_lr

        # Not significant
        if rlr.pvalue > 0.13:
            insig.append(row)
            continue

#        # Not enough retreat
#        if abs(row.up_len_km_b1[-1] - row.up_len_km_b1[0]) < .8:
#            insig.append(row)
#            continue

        if row.resid_lr.slope < 0:
            pro.append(row)
            continue
        else:
            con.append(row)
            continue


    for catname,eles in (('pro',pro), ('con',con), ('insig',insig)):
        fnames = [os.path.join(odir,row.plot_page) for row in eles]
        cmd = ['pdftk'] + fnames + ['cat', 'output', '{}.pdf'.format(catname)]
        subprocess.run(cmd)

main()
