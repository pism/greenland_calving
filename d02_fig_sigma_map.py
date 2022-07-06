import subprocess
import datetime
#from cffdrs import arcticfire
from uafgi import cptutil

# Derived from plot_agu1.py

# https://stackoverflow.com/questions/43599018/is-there-a-way-to-get-matplotlib-path-contains-points-to-be-inclusive-of-boundar
#I do quite like this command in Jupiter notebook:
#from IPython.core.display import display, HTML
#display(HTML("<style>.container { width:95% !important; }</style>"))
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
from uafgi.util import shputil,cartopyutil,ioutil
import uafgi.data.ns642
import netCDF4
import matplotlib.pyplot as plt
import uafgi.data
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
from mpl_toolkits.axes_grid1 import make_axes_locatable

itslive_file = 'outputs/itslive/GRE_G0240_W70.90N_1985_2018.nc'
sigma_file = 'outputs/itslive/sigma/GRE_G0240_W70.90N_1985_2018_sigma.nc'
bm_file = 'outputs/bedmachine/BedMachineGreenland-2017-09-20_W70.90N.nc'
termini_file = 'data/wood2021/Greenland_Glacier_Ice_Front_Positions.shp'

def write_plot(fig, ofname):
    # Write plot and shrink
    with ioutil.TmpDir() as tdir:
        fname0 = tdir.filename() + '.png'
        fig.savefig(fname0, dpi=300, transparent=True)
        with ioutil.WriteIfDifferent(ofname) as wid:
            cmd = ['convert', fname0, '-trim', '-strip', wid.tmpfile]
            subprocess.run(cmd, check=True)

def main():

    # Convert geotransform to extents
    # TODO: Add to cartopyutil
    #def geotransform_to_extents(gt):
    #    x0 = gt[0]
    #    x1 = 

    # Get projection, etc. and data too
    with netCDF4.Dataset(itslive_file) as nc:
        map_crs,extents = cartopyutil.nc_mapinfo(nc, 'polar_stereographic')

        map_wkt = nc.variables['polar_stereographic'].spatial_ref
        xx = nc.variables['x'][:]
        yy = nc.variables['y'][:]

        # Data
        uu = nc.variables['u_ssa_bc'][-1,:]
        vv = nc.variables['v_ssa_bc'][-1,:]

    termdf = shputil.read_df(termini_file, wkt=map_wkt)
    df = termdf.df
    print(df.columns)
    df = df[df.Glacier.isin(['Kangilleq', 'Sermeq Silarleq']) & (df.Year == 2018)]
    termini = df['loc'].tolist()


    with netCDF4.Dataset(bm_file) as nc:
        bed = nc.variables['bed'][:]


    with netCDF4.Dataset(sigma_file) as nc:
        sigma = nc.variables['sigma'][-1,:]

    # ---------------------------------------------------

    # Shrink the domain
    extents[2] = extents[3] + .5*(extents[2]-extents[3])



    # ===================================================================
    # vector_map.png
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))

    # Get sub-plot to plot on
    #ax = axs[0][0]
    ax = axs
    #ax.set_title('Integration of velocity (v) or stress state (vσ) across terminus')
    ax.set_extent(extents, map_crs)

    cmap,_,_ = cptutil.read_cpt('palettes/Blues_09_and_Elev.cpt')
    #cmap,_,_ = cptutil.read_cpt('palettes/caribbean.cpt')
    pcm = ax.pcolormesh(
        xx, yy, bed, transform=map_crs, cmap=cmap, vmin=-1000, vmax=1500)

    ax.quiver(xx, yy, uu, vv, transform=map_crs, regrid_shape=30, scale=30000)


    # this plots the polygon
    # must declare correct coordinate system of the data
    # here, coordinates in `pgon` are LambertConformal, 
    # it must be specified here as `crs=ccrs.LambertConformal()`
    ax.add_geometries(termini, crs=map_crs, facecolor="none", edgecolor='red', alpha=0.8)
    cartopyutil.add_osgb_scalebar(ax, text_color='black')

    write_plot(fig, uafgi.data.join_plots('vector_map.png'))


    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    cbar_ax = axs
    cbar = fig.colorbar(pcm, ax=cbar_ax)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately
    write_plot(fig, uafgi.data.join_plots('vector_map_cbar.png'))


    # ===================================================================
    # sigma_map.png

    # -----------------------------------------------------
    # Sample \tilde{\sigma} plot from PISM

    fig,axs = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))

    ax = axs
    #ax.set_title('Stress state σ of glacier (MPa)')
    ax.set_extent(extents, map_crs)

    pcm = ax.pcolormesh(xx, yy, 1.e-3 * sigma, transform=map_crs, vmin=0.0, vmax=500)
    divider = make_axes_locatable(ax)
    # https://stackoverflow.com/questions/30030328/correct-placement-of-colorbar-relative-to-geo-axes-cartopy
#    cax = divider.append_axes("bottom", size='3%', pad=0.05, axes_class=plt.Axes)

#    cbar = fig.colorbar(pcm, ax=ax, shrink=0.98)
#    cbar.set_label('Stress State σ (MPa)')

    ax.add_geometries(termini, crs=map_crs, facecolor="none", edgecolor='red', alpha=0.8)
    cartopyutil.add_osgb_scalebar(ax, text_color='white')

    #plt.show()
    write_plot(fig, uafgi.data.join_plots('sigma_map.png'))

    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    cbar_ax = axs
    cbar = fig.colorbar(pcm, ax=cbar_ax)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately
    write_plot(fig, uafgi.data.join_plots('sigma_map_cbar.png'))




main()
