import pandas as pd
from uafgi.data import stability as d_stability
from uafgi.data import d_r12
import uafgi.data.wkt

# Generate a list of the names we were given for the glaciers in the study.
# This output was used to manually compile the file:
#      data/stability_overrides/study_glaciers_overrides.csv
def main():

    map_wkt = uafgi.data.wkt.nsidc_ps_north
    df = d_stability.read_extract(map_wkt, joins={'sl19', 'r12'}, version=1, keep_all=True)
    catdf = pd.read_csv('category_results.csv')

    # Both of these provide the same answer.  This shows the ID numbers were transcribed
    # correctly off the rapsheets.
#    df = pd.merge(df, catdf, on='w21t_glacier_number', how='left', suffixes=('','_y'))
    len0 = len(df)
    df = pd.merge(df, catdf, on='sl19_rignotid', how='left', suffixes=('','_y'))
    assert len(df) == len0    # Ensure no rows lost

    df = df[['w21t_glacier_number', 'category', 'w21t_Glacier', 'r12_glacier_name', 'greenlandic_name', 'w21t_lon', 'w21t_lat', 'rs_slope', 'sl19_rignotid']]
    df = df[df.rs_slope.notna()]
    df.to_csv('study_glaciers.csv')
    print(df[['w21t_Glacier', 'greenlandic_name', 'sl19_rignotid', 'r12_glacier_name']])

main()
