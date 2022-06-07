import uafgi.data
import cartopy
import cartopy.crs
import matplotlib.pyplot as plt
import uafgi.data.wkt
from uafgi import cartopyutil,bedmachine,cptutil
import uafgi.data.stability as d_stability
import netCDF4
import numpy as np
import matplotlib.colors

"""NOTE: Before this is run, you must run a04_localize_bedmachine.py"""

label_font = {'family': 'sans serif',
        'color':  'black',
        'weight': 'normal',
        'size': 6,
        }

# w21t_glacier_number of the glaciers we ended up using
# See pro.pdf, con.pdf, insig.pdf
pro_glaciers = [181, 38,37,185,15,207,41,53,50,48,169,9,225]
con_glaciers = [65,204,13,10,7,11,214]
insig_glaciers = [62,221,43,212,126,208,206,40,76,1,98,4,22,14,8,71,54,55,3,171,170,12,2,92]

glacier_colors = dict()
for glist,color in ((pro_glaciers,'xkcd:green'), (con_glaciers,'xkcd:red'), (insig_glaciers,'xkcd:blue')):
    for gnum in glist:
        glacier_colors[gnum] = color


ELEV_RANGE = (-1000, 0)
def main():
    fig = plt.figure(figsize=(10,10))
    ax,map_wkt,crs = uafgi.data.wkt.greenland_map(fig.add_axes, (.1,.1,.8,.8))

#    ax.add_feature(cartopy.feature.LAND, edgecolor='black',alpha=.5,zorder=1)
    ax.add_feature(cartopy.feature.LAND, edgecolor='black', facecolor='none',zorder=0)


    select = d_stability.read_select(map_wkt)
    for ix,selrow in select.df.iterrows():
        try:
            glacier_color = glacier_colors[selrow.w21t_glacier_number]
        except KeyError:
            continue

        # Get local geometry
        bedmachine_file = uafgi.data.join_outputs('bedmachine', 'BedMachineGreenland-2017-09-20_{}.nc'.format(selrow.ns481_grid))
        with netCDF4.Dataset(bedmachine_file) as nc:
            nc.set_auto_mask(False)
            mapinfo = cartopyutil.nc_mapinfo(nc, 'polar_stereographic')
            bed = nc.variables['bed'][:]
            xx = nc.variables['x'][:]
            yy = nc.variables['y'][:]

        # Plot fjord polygon
#        ax.add_geometries([selrow.fj_poly], crs=mapinfo.crs, edgecolor=None, facecolor='red', alpha=.2)


        # Plot depth in the fjord
        fjord_gd = bedmachine.get_fjord_gd(bedmachine_file, selrow.fj_poly)
        fjord = np.flip(fjord_gd, axis=0)
#        bedm = np.ma.masked_where(np.logical_not(fjord), bed)
#        bedm = np.ma.masked_where(np.logical_not(fjord), bed)

#        # Plot extent of fjord, not depths
        bedm = np.zeros(fjord.shape) - 1000.
        bedm = np.ma.masked_where(np.logical_not(fjord), bedm)

#        cmap,_,_ = cptutil.read_cpt('Blues_09a.cpt')
        cmap = matplotlib.colors.ListedColormap([glacier_color], name='from_list', N=None)
        print(type(mapinfo.crs), type(crs))
        pcm = ax.pcolormesh(
#            xx, yy, bedm, transform=mapinfo.crs,
            xx, yy, bedm, transform=crs,
            cmap=cmap, vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1], zorder=2)

#        leaf = '{}_{}_{}'.format(
#            selrow.ns481_grid.replace('.',''),
#            selrow.w21t_glacier_number,
#            selrow.w21t_Glacier.replace('_','-').replace('.',''))


        label = '{}: {}'.format(selrow.ns481_grid, selrow.w21t_Glacier)
        ax.text(selrow.w21t_tloc.x, selrow.w21t_tloc.y, label, fontdict=label_font, zorder=3)
        


#        break

    print(list(select.df.columns))
    plt.savefig(uafgi.data.join_plots('greenland.png'), dpi=300)

main()
