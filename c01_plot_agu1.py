import subprocess
import datetime
from cffdrs import arcticfire
from uafgi import cptutil

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
from uafgi import gicollections,cfutil,glacier,gdalutil,shputil,pdutil,cartopyutil
import uafgi.data
import uafgi.data.ns642
import netCDF4
import matplotlib.pyplot as plt
import uafgi.data.wkt
import uafgi.data.w21 as d_w21
from mpl_toolkits.axes_grid1 import make_axes_locatable

itslive_file = 'outputs/itslive/GRE_G0240_W70.90N_1985_2018.nc'
sigma_file = 'outputs/itslive/GRE_G0240_W70.90N_1985_2018_sigma.nc'
bm_file = 'outputs/bedmachine/BedMachineGreenland-2017-09-20_W70.90N.nc'
termini_file = 'data/wood2021/Greenland_Glacier_Ice_Front_Positions.shp'

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

    df = shputil.read_df(termini_file, wkt=map_wkt)
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



    # -----------------------------------------------------
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))

    # Get sub-plot to plot on
    #ax = axs[0][0]
    ax = axs
    ax.set_title('Integration of velocity (v) or stress state (vσ) across terminus')
    ax.set_extent(extents, map_crs)

    cmap,_,_ = cptutil.read_cpt('palettes/caribbean.cpt')
    ax.pcolormesh(
        xx, yy, bed, transform=map_crs, cmap=cmap)

    ax.quiver(xx, yy, uu, vv, transform=map_crs, regrid_shape=30, scale=30000)


    # this plots the polygon
    # must declare correct coordinate system of the data
    # here, coordinates in `pgon` are LambertConformal, 
    # it must be specified here as `crs=ccrs.LambertConformal()`
    ax.add_geometries(termini, crs=map_crs, facecolor="none", edgecolor='red', alpha=0.8)

    fig.savefig('agu1b.png', dpi=300, transparent=True)

    # -----------------------------------------------------
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))

    ax = axs
    ax.set_title('Stress state σ of glacier (MPa)')
    ax.set_extent(extents, map_crs)

    pcm = ax.pcolormesh(xx, yy, 1.e-6 * sigma, transform=map_crs, vmin=0.0, vmax=0.5)
    divider = make_axes_locatable(ax)
    # https://stackoverflow.com/questions/30030328/correct-placement-of-colorbar-relative-to-geo-axes-cartopy
#    cax = divider.append_axes("bottom", size='3%', pad=0.05, axes_class=plt.Axes)

    cbar = fig.colorbar(pcm, ax=ax, shrink=0.98)
#    cbar.set_label('Stress State σ (MPa)')

    ax.add_geometries(termini, crs=map_crs, facecolor="none", edgecolor='red', alpha=0.8)


    #plt.show()
    fig.savefig(uafgi.data.join_plots('agu1a.png'), dpi=300, transparent=True)


main()
