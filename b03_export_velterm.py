from uafgi.data import d_velterm
import uafgi.data
import os
import pandas as pd

# Export the velterm pickle files to a single master CSV file

odir = uafgi.data.join_outputs('velterm')
os.makedirs(odir, exist_ok=True)

df = d_velterm.df_files()
df.to_csv(os.path.join(odir, 'velterm.csv'))
