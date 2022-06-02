import uafgi.data
import os
import pandas as pd

# Export the velterm pickle files to csv

idir = uafgi.data.join_outputs('velterm')
odir = os.path.join('outputs0', 'velterm')
os.makedirs(odir, exist_ok=True)

for leaf in os.listdir(idir):
    print(leaf)
    ifname = os.path.join(idir, leaf)
    ofname = os.path.join(odir, os.path.splitext(leaf)[0]+'.csv')
    df = pd.read_pickle(ifname)
    df.to_csv(ofname)
