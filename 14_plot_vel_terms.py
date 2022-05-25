#import datetime
import traceback
import subprocess
import cartopy.crs
import collections
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
from uafgi import cartopyutil,cptutil,dtutil
from uafgi import bedmachine
import numpy.ma
import scipy.stats
import matplotlib.gridspec

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
        print('14_plot_vel_terms ', self.select.df.columns)
        selrow = self.select.df.loc[glacier_id]

         # Select just ACTUAL termini, no "sample" future termini.
#        print(self.velterm_df)
#        print(self.velterm_df['glacier_id'].unique())
#        print('xxxxxx ',glacier_id)
#        print('gggggggggggggggg ', glacier_df)

        glacier_df = glacier_df0[glacier_df0.term_year < 2020]


        # Useonly termini since 2000
        df = glacier_df[
            (glacier_df['term_year'] > 2000) & (glacier_df.term_year < 2020)]

        # Use only velocities older than the terminus
        df = df[df.vel_year < df.term_year]

        # Convert up_area to up_len_km
        df['up_len_km'] = df['up_area'] / (selrow.w21_mean_fjord_width * 1e6)

        # Order by amount-retreated (instead of year)
        gdf = df[['up_len_km', 'term_year', 'fluxratio']].groupby('up_len_km').mean()
          
#        fig, axs = plt.subplots(2,2, figsize=(8.5,11))
        # https://towardsdatascience.com/customizing-multiple-subplots-in-matplotlib-a3e1c2e099bc
        fig = plt.figure(figsize=(8.5,11))
        spec = matplotlib.gridspec.GridSpec(ncols=3, nrows=3,
            height_ratios=[.5,.5,2])

        # -----------------------------------------------------------
        # (0,0): Sigma by up_len_km
        #df = df.rename(columns={'fluxratio':'past'}).reset_index()
        ax1 = fig.add_subplot(spec[0:2,0])
        gdf.sort_values('up_len_km')
        gdf = gdf.rename(columns={'fluxratio': 'sigma'})
        gdf[['sigma']].plot(ax=ax1,marker='o')
        ax1.invert_xaxis()
        ax1.yaxis.set_label('sigma (kPa)')
        axr = ax1.twinx()
        gdf[['term_year']].plot(ax=axr,color='red', marker="x", linestyle="None")

        # -----------------------------------------------------------
        # (0,1): Retreat by year
        ax2 = fig.add_subplot(spec[0,1])
        ax2.yaxis.set_visible(False)    # Axis on left
        axr = ax2.twinx()
#        ax2.yaxis.set_label_position("right")
        pldf = gdf[['term_year']].reset_index().set_index('term_year').sort_index()
        pldf.plot(ax=axr)

        lrr = scipy.stats.linregress(pldf.index.to_list(), pldf['up_len_km'].to_list())
        x = np.array([2000, 2020])
        plt.plot(x, lrr.intercept + lrr.slope*x, 'grey')

        # -----------------------------------------------------------
        # (0,2); Wood et al plot
        ax = fig.add_subplot(spec[0:2,2])

        # Shrink current axes' height by 20%
        box = ax.get_position()
        ax.set_position([box.x0, box.y0 + box.height*.2,
                 box.width, box.height * 0.8])

        data_fname = '{} Data.nc'.format(selrow['w21t_Glacier'])
        df = d_w21.glacier_cumulative_df(data_fname)
#        df = df.loc[datetime.datetime(2000,1,1):]
        df = df.loc[2000:]

        # Convert to rates [km a-1]
        cols = dict([(cname, df[cname].diff()) for cname in df.columns])
        dfr = pd.DataFrame.from_dict(cols)

        # compute sigma/sigma_max
        #sigma_pct = 1. - (dfr['ice_advection'] - dfr['calving']) / dfr['ice_advection']

        #dfr['advdiff'] = dfr['ice_advection'] - dfr['calving']

#        dfr['sigma_pct'] = np.log(sigma_pct)
        #dfr[['sigma_pct']].plot()
        #dfr[['advdiff', 'ice_advection']].plot(markersize=120)
        #dfr.plot()
        ax.yaxis.set_visible(False)    # Axis on left
        ax = ax.twinx()
        df.plot(ax=ax)

        # Put a legend below current axis
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.5),
          fancybox=True, shadow=True, ncol=1)

        #sigma_pct.plot()
        #plt.title(data_fname)

        # -----------------------------------------------------------
        # (0,1); Wood calving to flux ratio
        ax = fig.add_subplot(spec[1,1])
        ax.yaxis.set_visible(False)    # Axis on left
        ax = ax.twinx()

        df['calving_by_advect'] = -dfr['calving'] / dfr['ice_advection']
        df[['calving_by_advect']].plot(ax=ax)




        # -----------------------------------------------------------
        # (1,0): Map
        # Get local geometry
        bedmachine_file = uafgi.data.join_outputs('bedmachine', 'BedMachineGreenland-2017-09-20_{}.nc'.format(selrow.ns481_grid))
        with netCDF4.Dataset(bedmachine_file) as nc:
            nc.set_auto_mask(False)
            mapinfo = cartopyutil.nc_mapinfo(nc, 'polar_stereographic')
            bed = nc.variables['bed'][:]
            xx = nc.variables['x'][:]
            yy = nc.variables['y'][:]

        # Set up the basemap
        ax = fig.add_subplot(spec[2,:], projection=mapinfo.crs)
        ax.set_extent(mapinfo.extents, crs=mapinfo.crs)
        ax.coastlines(resolution='50m')


        # Plot depth in the fjord
        fjord_gd = bedmachine.get_fjord_gd(bedmachine_file, selrow.fj_poly)
        fjord = np.flip(fjord_gd, axis=0)
        bedm = numpy.ma.masked_where(np.logical_not(fjord), bed)

        bui_range = (0.,350.)
        cmap,_,_ = cptutil.read_cpt('caribbean.cpt')
        pcm = ax.pcolormesh(
            xx, yy, bedm, transform=mapinfo.crs,
            cmap=cmap, vmin=-1000, vmax=0)
        cbar = fig.colorbar(pcm, ax=ax)
        cbar.set_label('Fjord Bathymetry (m)')
        
#        # Plot colorbar for depth
#        sm = plt.cm.ScalarMappable(cmap=cmap)#, norm=plt.Normalize(*bui_range))
#
#
#        fig.subplots_adjust(top=0.85)
#cbar_ax = fig.add_axes([.1, .1, .9, .03])# 0.85, 0.15, 0.05, 0.7])
#cbar_ax.axis('off')    # Don't display spurious axes


        # Plot the termini
        date_termini = sorted(selrow.w21t_date_termini)

        yy = [dtutil.year_fraction(dt) for dt,_ in date_termini]
        year_termini = [(y,t) for y,(_,t) in zip(yy, date_termini) if y > 2000]

        for year,term in year_termini:
            ax.add_geometries([term], crs=mapinfo.crs, edgecolor='red', facecolor='none', alpha=.8)

        bounds = date_termini[0][1].bounds
        for _,term in date_termini:
            bounds = (
                min(bounds[0],term.bounds[0]),
                min(bounds[1],term.bounds[1]),
                max(bounds[2],term.bounds[2]),
                max(bounds[3],term.bounds[3]))
        x0,y0,x1,y1 = bounds
        ax.set_extent(extents=(x0-5000,x1+5000,y0-5000,y1+5000), crs=mapinfo.crs)

        # Plot scale in km
        cartopyutil.add_osgb_scalebar(ax)


        # ------------------------------------------------------------
        fig.subplots_adjust(top=0.85)
        fig.suptitle('{} - {} - {}\nRetreat R-value = {:0.2}'.format(
            selrow['w21t_Glacier'], glacier_id, selrow['ns481_grid'], lrr.rvalue))

        # TODO: Also plot ocean warming timeseries from Wood et al 2021

        # ----------------------------------------------------------------


        #fig.tight_layout()
        return fig


def main():

    gp = GlacierPlots()
    for ix,(glacier_id,row) in enumerate(gp.select.df.iterrows()):
#        print('glacier_id = ', glacier_id)
#        if glacier_id != 1:
#            continue

        root = 'gg{:03d}'.format(ix)
        pdf = root + '.pdf'
        if os.path.exists(pdf):
            continue

        print('------------ glacier_id {}'.format(glacier_id))
        try:
            fig = gp.plot_glacier(glacier_id)
        except Exception:
            traceback.print_exc()
            continue

        print('Saving {}'.format(root))
        fig.savefig(root+'.png', dpi=300)
#        break

        cmd = ['convert', root+'.png', root+'.pdf']
        subprocess.run(cmd)

#        plt.show()

main()
