#%matplotlib notebook
#%matplotlib inline

# https://stackoverflow.com/questions/43599018/is-there-a-way-to-get-matplotlib-path-contains-points-to-be-inclusive-of-boundar
#I do quite like this command in Jupiter notebook:
from IPython.core.display import display, HTML
display(HTML("<style>.container { width:95% !important; }</style>"))
#It makes things wider and not waste the space on your screen
import pandas as pd
import importlib
import csv,os
import numpy as np
import pandas as pd
import itertools
import pyproj
import shapely
import copy
from uafgi import gicollections,cfutil,glacier,gdalutil,shputil,pdutil,ioutil
import uafgi.data
import uafgi.data.ns642
import netCDF4
import matplotlib.pyplot as plt
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
map_wkt = uafgi.data.wkt.nsidc_ps_north
pd.set_option("display.max_rows", 30, "display.max_columns", None)
pd.set_option("display.max_rows", 200, "display.max_columns", None)

from uafgi.data import d_velterm
import uafgi.data.stability as d_stability
import scipy,subprocess
from uafgi.pism import qregress

def write_plot(fig, ofname):
    # Write plot and shrink
    with ioutil.TmpDir() as tdir:
        fname0 = tdir.filename() + '.png'
        print('Saving initial plot to {}'.format(fname0))
        fig.savefig(fname0, dpi=300, transparent=True)
        with ioutil.WriteIfDifferent(ofname) as wid:
            cmd = ['convert', fname0, '-trim', '-strip', wid.tmpfile]
            print(cmd)
            subprocess.run(cmd, check=True)

# =================================================
def main():
    select = d_stability.read_extract(map_wkt)
    velterm_df = d_velterm.read()

    # Cache sigmas computation while we get the graph right.
    try:
        sigmas = pd.read_pickle('sigmas.df')
    except FileNotFoundError:
        sigmas = qregress.fit_sigma_maxs(select,velterm_df)
        sigmas.to_pickle('sigmas.df')

    # Convert to kPa
    sigmas.sigma_max = sigmas.sigma_max * 1.e-3

    # -----------------------------------------
    #%matplotlib notebook
    #%matplotlib inline

    plt.rcParams['font.size'] = 12
    plt.rcParams['figure.figsize'] = [8, 6]


    # Boxplot properties
    # https://stackoverflow.com/questions/35160956/pandas-boxplot-set-color-and-properties-for-box-median-mean
    #boxprops = dict(linestyle='-', linewidth=4, color='k')
    #medianprops = dict(linestyle='-', linewidth=4, color='k')
    medianprops = dict(linestyle='-', linewidth=2, color='red')

    # Boxplot sorted by median
    # https://stackoverflow.com/questions/21912634/how-can-i-sort-a-boxplot-in-pandas-by-the-median-values
    sg = sigmas[sigmas.sigma_max.abs() < 1.e3]
    sgg = sg.groupby('glacier_id')
    sg2 = pd.DataFrame({col:vals['sigma_max'] for col,vals in sgg})
    meds = sg2.median().sort_values()
    sg2 = sg2[meds.index]
    ax = sg2.boxplot(grid=False, showfliers=False, medianprops=medianprops)

    ## https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.boxplot.html#matplotlib.pyplot.boxplot
    #ax = sg.boxplot(column='sigma_max', by='glacier_id', grid=False, showfliers=False)
    ##plt.xticks(rotation=90)
    ## https://stackoverflow.com/questions/12998430/remove-xticks-in-a-matplotlib-plot
    ax.set_xticks([],[])




    # Boxplot sorted by glacier_id
    #sg = sigmas[sigmas.sigma_max.abs() < 1.e3].sort_values(by='sigma_max')
    ## https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.boxplot.html#matplotlib.pyplot.boxplot
    #ax = sg.boxplot(column='sigma_max', by='glacier_id', grid=False, showfliers=False)
    ##plt.xticks(rotation=90)
    ## https://stackoverflow.com/questions/12998430/remove-xticks-in-a-matplotlib-plot
    #ax.set_xticks([],[])

    write_plot(plt, uafgi.data.join_plots('sigma_max_by_glacier.png'))

    # -----------------------------------------
    plt.rcParams['font.size'] = 12
    plt.rcParams['figure.figsize'] = [7, 6]

    sg = sigmas[sigmas.sigma_max.abs() < 1.e3]
    #sg = sg.rename(columns={'time':'year'})
    sg['year'] = sg.time.astype('i')
    # https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.boxplot.html#matplotlib.pyplot.boxplot
    sg.boxplot(column='sigma_max', by='year', grid=False, showfliers=False, medianprops=medianprops)
    plt.xticks(rotation=90)

    plt.suptitle('')    # Remove title added by boxplot()
    plt.title('')
    write_plot(plt, uafgi.data.join_plots('sigma_max_by_year.png'))


main()
