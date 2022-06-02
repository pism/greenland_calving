import netCDF4
import pyproj

import cartopy.crs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import osgeo.osr


# ========================================================================
# From: https://github.com/fmaussion/salem/blob/d0aaefab96bd4099c280d5088d4e66b52d20b72b/salem/gis.py#L901-L983
# See: https://github.com/SciTools/cartopy/issues/813
# Copyright: Fabien Maussion, 2014-2016
# License: GPLv3

def check_crs(crs):
    """Checks if the crs represents a valid grid, projection or ESPG string.
    Examples
    --------
    >>> p = check_crs('+units=m +init=epsg:26915')
    >>> p.srs
    '+units=m +init=epsg:26915 '
    >>> p = check_crs('wrong')
    >>> p is None
    True
    Returns
    -------
    A valid crs if possible, otherwise None
    """
    if isinstance(crs, pyproj.Proj): # or isinstance(crs, Grid):
        out = crs
    elif isinstance(crs, dict) or isinstance(crs, str):
        try:
            out = pyproj.Proj(crs)
        except RuntimeError:
            try:
                out = pyproj.Proj(init=crs)
            except RuntimeError:
                out = None
    else:
        out = None
    return out


def proj_to_cartopy(proj):
    """Converts a pyproj.Proj to a cartopy.crs.Projection
    Parameters
    ----------
    proj: pyproj.Proj
        the projection to convert
    Returns
    -------
    a cartopy.crs.Projection object
    """

    proj = check_crs(proj)

    # UserWarning: 'is_latlong()' is deprecated and will be removed in version 2.2.0. Please use 'crs.is_geographic'.
    # if proj.is_latlong():
    if proj.crs.is_geographic:
        return cartopy.crs.PlateCarree()

    srs = proj.srs
    # if has_gdal:    # (True if osgeo.osr imports properly
    if True:
        # this is more robust, as srs could be anything (espg, etc.)
        s1 = osgeo.osr.SpatialReference()
        s1.ImportFromProj4(proj.srs)
        srs = s1.ExportToProj4()

    km_proj = {'lon_0': 'central_longitude',
               'lat_0': 'central_latitude',
               'x_0': 'false_easting',
               'y_0': 'false_northing',
               'k': 'scale_factor',
               'zone': 'zone',
               }
    km_globe = {'a': 'semimajor_axis',
                'b': 'semiminor_axis',
                }
    km_std = {'lat_1': 'lat_1',
              'lat_2': 'lat_2',
              }
    kw_proj = dict()
    kw_globe = dict()
    kw_std = dict()
    for s in srs.split('+'):
        s = s.split('=')
        if len(s) != 2:
            continue
        k = s[0].strip()
        v = s[1].strip()
        try:
            v = float(v)
        except:
            pass


        cartopy_class = {
            'tmerc' : cartopy.crs.TransverseMercator,
            'lcc' : cartopy.crs.LambertConformal,
            'merc' : cartopy.crs.Mercator,
            'utm' : cartopy.crs.UTM,
            'stere' : cartopy.crs.Stereographic,
        }

        if k == 'proj':
            klass = cartopy_class[v]
        if k in km_proj:
            kw_proj[km_proj[k]] = v
        if k in km_globe:
            kw_globe[km_globe[k]] = v
        if k in km_std:
            kw_std[km_std[k]] = v

    globe = None
    if kw_globe:
        globe = cartopy.crs.Globe(**kw_globe)
    if kw_std:
        kw_proj['standard_parallels'] = (kw_std['lat_1'], kw_std['lat_2'])

    # mercatoooor
    if klass.__name__ == 'Mercator':
        kw_proj.pop('false_easting', None)
        kw_proj.pop('false_northing', None)

    return klass(globe=globe, **kw_proj)
# ========================================================================





def main():

    # Read the CRS and conver to Cartopy CRS
    velocity_file = 'outputs/TSX_W69.10N_2008_2020.nc'
    with netCDF4.Dataset(velocity_file) as nc:
        proj_crs = pyproj.CRS.from_string(nc.variables['polar_stereographic'].spatial_ref)
        bounding_xx = nc.variables['x'][:]
        bounding_yy = nc.variables['y'][:]
    ccrs = proj_to_cartopy(proj_crs.to_proj4())



    ax = plt.axes(projection=ccrs)#.PlateCarree())
    limits = [bounding_xx[0],bounding_yy[0], bounding_xx[-1],bounding_yy[-1]]
    print('lllllllllllllllimits ', limits)
    ax.set_extent(limits)
#[-6, 1, 47.5, 51.5])
    ax.coastlines()

    plt.show()

#
#    rotated_crs = ccrs.RotatedPole(pole_longitude=120.0, pole_latitude=70.0)
#    ax0 = plt.axes(projection=rotated_crs)
#    ax0.set_extent([-6, 1, 47.5, 51.5], crs=ccrs.PlateCarree())
#    ax0.add_feature(cfeature.LAND.with_scale('110m'))
#    ax0.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
#
#    plt.figure(figsize=(6.9228, 3))
#    ax1 = plt.axes(projection=ccrs.InterruptedGoodeHomolosine())
#    ax1.coastlines(resolution='110m')
#    ax1.gridlines(draw_labels=True)
#
#    plt.show()
#
#
if __name__ == '__main__':
    main()

