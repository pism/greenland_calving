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

MapInfo = collections.namedtuple('MapInfo', ('crs', 'extents'))
def nc_mapinfo(nc, ncvarname):
    """Setup a map from CF-compliant stuff"""

    nx = len(nc.dimensions['x'])
    ny = len(nc.dimensions['y'])

    ncvar = nc[ncvarname]
    map_crs = cartopyutil.crs(ncvar.spatial_ref)

#    map_crs = cartopy.crs.Stereographic(
#        central_latitude=90,
#        central_longitude=-45,
#        false_easting=0, false_northing=0,
#        true_scale_latitude=70, globe=None)

    print('map_crs ', map_crs)

    # Read extents from the NetCDF geotransform
    geotransform = [float(x) for x in ncvar.GeoTransform.split(' ') if x != '']
    x0 = geotransform[0]
    x1 = x0 + geotransform[1] * nx
    y0 = geotransform[3]
    y1 = y0 + geotransform[5] * ny
    extents = [x0,x1,y0,y1]

    return MapInfo(map_crs, extents)
#    ax.set_extent(extents=extents, crs=map_crs)
#    return map_crs


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
        glacier_df = glacier_df0[glacier_df0.term_year < 2020]

        # Useonly termini since 2000
        df = glacier_df[
            (glacier_df['term_year'] > 2000) & (glacier_df.term_year < 2020)]

        # Use only velocities older than the terminus
        df = df[df.vel_year < df.term_year]

        # Convert up_area to up_len_km
        df['up_len_km'] = df['up_area'] / (selrow.w21_mean_fjord_width * 1e6)

        # Order by amount-retreated (instead of year)
        df = df[['up_len_km', 'term_year', 'fluxratio']].groupby('up_len_km').mean()
          
#        fig, axs = plt.subplots(2,2, figsize=(8.5,11))
        # https://towardsdatascience.com/customizing-multiple-subplots-in-matplotlib-a3e1c2e099bc
        fig = plt.figure(figsize=(8.5,11))
        spec = matplotlib.gridspec.GridSpec(ncols=2, nrows=2,
            height_ratios=[1,2])


        # -----------------------------------------------------------
        # (0,0): Sigma by up_len_km
        #df = df.rename(columns={'fluxratio':'past'}).reset_index()
        ax1 = fig.add_subplot(spec[0,0])
        df.sort_values('up_len_km')
        df = df.rename(columns={'fluxratio': 'sigma'})
        df[['sigma']].plot(ax=ax1,marker='o')
        ax1.invert_xaxis()
        ax1.yaxis.set_label('sigma (kPa)')
        axr = ax1.twinx()
        df[['term_year']].plot(ax=axr,color='red', marker="x", linestyle="None")

        # -----------------------------------------------------------
        # (0,1): Retreat by year
        ax2 = fig.add_subplot(spec[0,1])
        ax2.yaxis.set_visible(False)    # Axis on left
        axr = ax2.twinx()
#        ax2.yaxis.set_label_position("right")
        pldf = df[['term_year']].reset_index().set_index('term_year').sort_index()
        pldf.plot(ax=axr)

        lrr = scipy.stats.linregress(pldf.index.to_list(), pldf['up_len_km'].to_list())
        x = np.array([2000, 2020])
        plt.plot(x, lrr.intercept + lrr.slope*x, 'grey')

        # -----------------------------------------------------------
        # (1,0): Map
        # Get local geometry
        bedmachine_file = uafgi.data.join_outputs('bedmachine', 'BedMachineGreenland-2017-09-20_{}.nc'.format(selrow.ns481_grid))
        with netCDF4.Dataset(bedmachine_file) as nc:
            nc.set_auto_mask(False)
            mapinfo = nc_mapinfo(nc, 'polar_stereographic')
            bed = nc.variables['bed'][:]
            xx = nc.variables['x'][:]
            yy = nc.variables['y'][:]

        # Set up the basemap
        ax = fig.add_subplot(spec[1,:], projection=mapinfo.crs)
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
            cmap=cmap)
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
        root = 'gg{:03d}'.format(ix)
        pdf = root + '.pdf'
        if os.path.exists(pdf):
            continue

        print('------------ glacier_id {}'.format(glacier_id))
        try:
            fig = gp.plot_glacier(glacier_id)
        except Exception as e:
            print(e)
            continue

        print('Saving {}'.format(root))
        fig.savefig(root+'.png', dpi=300)
        cmd = ['convert', root+'.png', root+'.pdf']
        subprocess.run(cmd)

#        plt.show()

main()
