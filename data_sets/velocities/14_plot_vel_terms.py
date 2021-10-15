import pandas as pd
import csv,os
import numpy as np
import pandas as pd
import itertools
import pyproj
import shapely
import copy
from uafgi import gicollections,cfutil,glacier,gdalutil,shputil,pdutil
import uafgi.data.ns642
import netCDF4
import matplotlib.pyplot as plt
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
import uafgi.data.fj
import uafgi.data.future_termini
from uafgi.data import d_velterm
import re
import uafgi.data.stability as d_stability

map_wkt = uafgi.data.wkt.nsidc_ps_north

#pd.set_option("display.max_rows", 30, "display.max_columns", None)
#pd.set_option("display.max_rows", 200, "display.max_columns", None)


class GlacierPlots:
    def __init__(self):
        self.select = d_stability.read_select(map_wkt)
        self.select.df = self.select.df.set_index('w21t_glacier_number')
        self.velterm_df = d_velterm.read()

    def plot_glacier(self, glacier_id):
        # Select rows for just our glacier
        glacier_df0 = self.velterm_df[self.velterm_df.glacier_id == glacier_id]
        selrow = self.select.df.loc[glacier_id]

         # Select just ACTUAL termini, no "sample" future termini.
        glacier_df = glacier_df0[glacier_df0.term_year < 2020]

        # Useonly termini since 2000
        df = glacier_df[
            (glacier_df['term_year'] > 2000) & (glacier_df.term_year < 2020)]

        # Use only velocities older than the terminus
        df = df[df.vel_year < df.term_year]

        # Order by amount-retreated (instead of year)
        df = df[['up_area', 'term_year', 'fluxratio']].groupby('up_area').mean()
          
        fig, (ax1, ax2) = plt.subplots(1,2, figsize=(14,5))
                

        #df = df.rename(columns={'fluxratio':'past'}).reset_index()
        df.sort_values('up_area')
        df.columns
        df[['fluxratio']].plot(ax=ax1,marker='o')
        ax1.invert_xaxis()
        axr = ax1.twinx()
        df[['term_year']].plot(ax=axr,color='g', marker="x", linestyle="None")

        df[['term_year']].reset_index().set_index('term_year').sort_index().plot(ax=ax2)


        fig.subplots_adjust(top=0.85)
        fig.suptitle('{} - {} - {}\nHello\nWorld'.format(selrow['w21t_Glacier'], glacier_id, selrow['ns481_grid']))

        # TODO: Also plot ocean warming timeseries from Wood et al 2021

        return fig


def main():

    gp = GlacierPlots()
    fig = gp.plot_glacier(191)
    plt.show()

main()
