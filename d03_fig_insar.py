import sys
import numpy as np
import os
import re
import pandas as pd
import pyproj
from uafgi.util import gdalutil,ogrutil,shputil
from uafgi.util import pdutil,shapelyutil
import shapely
import shapely.geometry
from osgeo import ogr,osr
import uafgi.data
import uafgi.data.bkm15
import uafgi.data.cf20
import uafgi.data.fj
import uafgi.data.m17
import uafgi.data.mwp
import uafgi.data.ns481
import uafgi.data.ns642
import uafgi.data.w21 as d_w21
from uafgi.data import d_sl19
import uafgi.data.wkt
from uafgi.data import greenland,stability
import pickle
from uafgi import bedmachine
from uafgi.util import cartopyutil,cptutil,dtutil
import collections
import scipy.stats
import netCDF4


import uafgi.data.wkt
from uafgi.util import ioutil,cptutil
import uafgi.data.stability as d_stability
from uafgi.data import d_velterm
import mpl_toolkits.axes_grid1
import os
import matplotlib.pyplot
import string
import shutil
import subprocess
import numpy as np
import traceback
import pandas as pd

# Plots figure for the paper
# ...the insar_* figures

map_wkt = uafgi.data.wkt.nsidc_ps_north


def write_plot(fig, ofname):
    print('Writing plot to ', ofname)
    # Write plot and shrink
    with ioutil.TmpDir() as tdir:
        fname0 = tdir.filename() + '.png'
        fig.savefig(fname0, dpi=300, transparent=True)
        with ioutil.WriteIfDifferent(ofname) as wid:
            cmd = ['convert', fname0, '-trim', '-strip', wid.tmpfile]
            subprocess.run(cmd, check=True)



def plot_velocity_map(selrow, plot_year):
    """Plots a reference map of a single glacier

    fig:
        Pre-created figure (of a certain size/shape) to populate.
    selrow:
        Row of d_stability.read()"""

    small = (5.5,4.5)
    fig = matplotlib.pyplot.figure(figsize=small)

    # fig = matplotlib.pyplot.figure()

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

    # Read velocities too!
    # Set up the basemap
    ax = fig.add_axes((.1,.1,.9,.86), projection=mapinfo.crs)
    #ax.set_facecolor('xkcd:light grey')    # https://xkcd.com/color/rgb/
    ax.set_facecolor('#E0E0E0')    # Map background https://xkcd.com/color/rgb/

    #ax = fig.add_subplot(spec[2,:], projection=mapinfo.crs)
    ax.set_extent(mapinfo.extents, crs=mapinfo.crs)
#    ax.coastlines(resolution='50m')


    # ------- Plot bed elevations EVERYWHERE
    cmap,_,_ = cptutil.read_cpt('palettes/Blues_09_and_Elev.cpt')
    #cmap,_,_ = cptutil.read_cpt('palettes/caribbean.cpt')
    pcm_elev = ax.pcolormesh(
        xx, yy, bed*.001, transform=mapinfo.crs, cmap=cmap, vmin=-1.000, vmax=1.500)

    velocity_file = uafgi.data.join_outputs('itslive', 'GRE_G0240_{}_1985_2018.nc'.format(selrow.ns481_grid))
    print(velocity_file)
    with netCDF4.Dataset(velocity_file) as nc:
        uu = nc.variables['u_ssa_bc'][plot_year-1985,:]
        vv = nc.variables['v_ssa_bc'][plot_year-1985,:]
        vel = np.sqrt(uu*uu + vv*vv) * .001    # Convert to km/a

    # ---------- Plot velocities in fjord
    fjord_gd = bedmachine.get_fjord_gd(bedmachine_file, selrow.fj_poly)
    fjord = np.flip(fjord_gd, axis=0)
    velm = np.ma.masked_where(np.logical_or(np.logical_not(fjord), vel==0), vel)
#    velm = np.ma.masked_where(np.abs(vel==0), vel)

    cmap,_,_ = cptutil.read_cpt('palettes/001-fire-10.cpt')

    pcm_vel = ax.pcolormesh(
        xx, yy, velm, transform=mapinfo.crs,
        cmap=cmap, vmin=0, vmax=5.000)
#    cbar = fig.colorbar(pcm_vel, ax=ax)
#    cbar.set_label('Velocities (m/a)')
        
    # Plot the termini
    date_termini = sorted(selrow.w21t_date_termini)

    yy = [dtutil.year_fraction(dt) for dt,_ in date_termini]
#    year_termini = [(y,t) for y,(_,t) in zip(yy, date_termini) if y > 2000]
    year_termini = [(y,t) for y,(_,t) in zip(yy, date_termini) if y >= plot_year]

    for year,term in year_termini:
        print(year)
        if int(year) == plot_year:
            ax.add_geometries([term], crs=mapinfo.crs, edgecolor='xkcd:neon green', facecolor='none', alpha=.8)

    bounds = date_termini[0][1].bounds
    for _,term in date_termini:
        bounds = (
            min(bounds[0],term.bounds[0]),
            min(bounds[1],term.bounds[1]),
            max(bounds[2],term.bounds[2]),
            max(bounds[3],term.bounds[3]))
    x0,y0,x1,y1 = bounds

    # Limit extent to near terminus
    #dx=5000
    dx=10000
    ax.set_extent(extents=(x0-13000,x1+5000,y0-5000,y1+14000), crs=mapinfo.crs)
#    ax.set_extent(extents=(x0-5000,x1+5000,y0-5000,y1+5000), crs=mapinfo.crs)

    # Plot scale in km
    cartopyutil.add_osgb_scalebar(ax)#, at_y=(0.10, 0.080))

    # Add an arrow showing ice flow
    dir = selrow.ns481_grid[0]
    if dir == 'E':
        coords = (.5,.05,.45,0)
    else:    # 'W'
        coords = (.95,.05,-.45,0)
    arrow = ax.arrow(
        *coords, transform=ax.transAxes,
        head_width=.03, ec='black', length_includes_head=True,
        shape='full', overhang=1,
        label='Direction of Ice Flow')
    ax.annotate('Ice Flow', xy=(.725, .07), xycoords='axes fraction', size=10, ha='center')

    leaf = 'insar_{}_{}'.format(selrow.ns481_grid, str(plot_year))
    write_plot(fig, uafgi.data.join_plots(leaf+'.png'))



    # ---------- The colorbar
    for suffix,pcm in (('elev', pcm_elev), ('vel', pcm_vel)):
        fig,axs = matplotlib.pyplot.subplots(
            nrows=1,ncols=1,
            figsize=small)
        cbar_ax = axs
        cbar = fig.colorbar(pcm, ax=cbar_ax)
#        cbar = matplotlibl.colorbar.ColorbarBase(

#        cbar.ax.xaxis.set_ticks_position("top")
        cbar.ax.yaxis.set_ticks_position('left')

        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately
#        cbar_ax.yaxis.set_label_position('left')

        write_plot(fig, uafgi.data.join_plots('insar_{}_{}.png'.format(selrow.ns481_grid, suffix)))








def main():
    # Bigger fonts
    # https://stackabuse.com/change-font-size-in-matplotlib/
    # (refer back if this doesn't fix tick label sizes)
    matplotlib.pyplot.rcParams['font.size'] = '16'

    #select = d_stability.read_select(map_wkt)
    select = d_stability.read_extract(map_wkt, joins={'fj','w21t'})
    velterm_df = d_velterm.read()

    # Get AP Barnstorff Glacier (ID 65)
    df = select.set_index('w21t_glacier_number')
    selrow = df.loc[62]
    print(selrow)

#    plot_velocity_map(fig, selrow)

#    for plot_year in (1990, 1995, 1996, 2005):
    for plot_year in (1990, 1996, 2005):
        plot_velocity_map(selrow, plot_year)
#    plot_year = 2005   # A bit wrong
#    plot_year = 1996   # No good data
#    plot_year = 1995   # No good data
#    plot_year = 1990   # Some of both



#    odir='.'
#    fig.savefig(os.path.join(odir, 'x.png'))

main()
