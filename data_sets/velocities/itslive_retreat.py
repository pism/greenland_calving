import cf_units
import bisect
import sys,os,subprocess,traceback
import numpy as np
import netCDF4
import geojson
import json
import pyproj
#import scipy
import scipy.stats
#import shapely
import shapely.geometry
from osgeo import ogr
import shapely.ops
import shapely.wkt, shapely.wkb
from uafgi import ioutil,ncutil,cfutil,argutil,make,geoutil,flowfill,shputil,glaciers,cdoutil,bedmachine,calfin,gdalutil
import datetime
import PISM
from uafgi.pism import calving0
from uafgi.make import ncmake
import subprocess
import shapefile
from scipy import signal
import shapely.wkb
import findiff
from uafgi.pism import pismutil



# -------------------------------------------------------------------
class compute(object):

    default_kwargs = dict(calving0.FrontEvolution.default_kwargs.items())
    default_kwargs['min_ice_thickness'] = 50.0

    def __init__(self, makefile, geometry_file, velocity_file, termini_file, termini_closed_file, otemplate, **kwargs0):
        """kwargs0:
            See default_kwargs above
        otemplate:
            Template used to construct output filenames, including directory
            May include: {dt0}, {dt1}
        """
        self.kwargs = argutil.select_kwargs(kwargs0, self.default_kwargs)

        self.geometry_file = geometry_file
        print('geometry_file = {}'.format(self.geometry_file))
        self.velocity_file = velocity_file
        print('velocity_file = {}'.format(self.velocity_file))
        self.termini_file = termini_file
        self.termini_closed_file = termini_closed_file
#        print('trace_file = {}'.format(self.trace_file))


        # Determine terminus pairs
        self.terminus_pairs = list()    # [ ((dt0,ix0), (dt1,ix1)) ]
        attrss = enumerate(iter([attrs for _,attrs in geoutil.read_shapes(termini_closed_file)]))
#        self.odir = os.path.split(otemplate)[0]
        ix0,attrs0 = next(attrss)
        dt0 = datetime.datetime.strptime(attrs0['Date'], '%Y-%m-%d').date()
        self.output_files = list()
        for ix1,attrs1 in attrss:
            dt1 = datetime.datetime.strptime(attrs1['Date'], '%Y-%m-%d').date()

#            if ix0 == 34:    # DEBUGGING: just one
            if dt0.year >= 2012:   # DEBUGGING
                self.terminus_pairs.append((ix0,dt0,ix1,dt1))
                sdt0 = datetime.datetime.strftime(dt0, '%Y%m%d')
                sdt1 = datetime.datetime.strftime(dt1, '%Y%m%d')
                self.output_files.append(otemplate.format(dt0=sdt0, dt1=sdt1))

            ix0,dt0 = ix1,dt1

        self.rule = makefile.add(self.run,
            [geometry_file, velocity_file, termini_file, termini_closed_file],
            self.output_files)

    def run(self):
        pass


def get_fjord(fb, trough_file, bedmachine_file, tdir):
    """
    fb:
        Result of cdoutil.FileInfo(), gives geometry
    trough_file:
        Name of GeoJSON file containing the approximate trough of this
        glacier (and none others).
    bedmachine_file:
    """

    with netCDF4.Dataset(bedmachine_file) as nc:
        bed = nc.variables['bed'][:]

    # ----- Rasterize the approximate trough
    approx_trough = gdalutil.rasterize_polygons(
        ogr.GetDriverByName('GeoJSON').Open(trough_file), bedmachine_file)
    print('approx_trough {}: {}'.format(trough_file, np.sum(np.sum(approx_trough))))

    # Intersect the appxorimate trough with the below-sea-level areas.
    # This gives the mask of
    # points where we check to see ice added/removed
    # during course of a run.
    fjord = (bed < 0)
    this_fjord = (np.logical_and(fjord, approx_trough != 0))

    return this_fjord



def get_terminus_fjord(fb, termini_file, terminus_id, bedmachine_file, tdir, distance_from_terminus=8000):

    """Finds areas of the fjord close to a terminus
    fb:
        Result of cdoutil.FileInfo(), gives geometry
    """

    with netCDF4.Dataset(bedmachine_file) as nc:
        bed = nc.variables['bed'][:]

    # ----- Rasterize the terminus trace
    terminus_d = next(shputil.rasterize_polygons(termini_file, [terminus_id], bedmachine_file, tdir))

    # ------------ Find points close to the terminus trace
    stencil = flowfill.disc_stencil(distance_from_terminus, (fb.dy, fb.dx))  # Distance from terminus
    # WARNING: THIS IS SLOW!!!
#    terminus_domain = (signal.convolve2d(terminus_d, stencil, mode='same') != 0)
    terminus_domain = (signal.fftconvolve2(terminus_d, stencil, mode='same') != 0)
    if np.sum(np.sum(terminus_domain)) == 0:
        raise ValueError('Nothing found in the domain, something is wrong...')

    # ----------------------
    # Intersect points close to terminus trace w/ fjord
    # (areas below sea level).  This gives the mask of
    # points where we check to see ice added/removed
    # during course of a run.
    fjord = (bed < 0)
    terminus_fjord = (np.logical_and(fjord, terminus_domain != 0))

    return terminus_fjord


def add_analysis(output_file4, itime, dt0, dt1, bedmachine_file1, velocity_file, fb, fjord):
    """Analyzes the run and adds variables to the file with that analysis.
    output_file4:
        File to analyze
    bedmachine_file1: (IN/OUT)
        Extract of BedMachine to get other stuff out of
    fb: FileInfo
        Domain bounds, consistent with bedmachine_file1
    """

    # ----------------------------------------------------
    # Examine first and last frame of the PISM run
    print('Getting thk from: {}'.format(output_file4))
    with netCDF4.Dataset(output_file4) as nc:
        ncthk = nc.variables['thk']
        ntime = ncthk.shape[0]
        thk0 = ncthk[0,:,:]
        thk1 = ncthk[ntime-1,:,:]

    # Advance: Place starting with no ice, but now have ice
    where_advance = np.logical_and(thk0 == 0, thk1 != 0)
    where_advance[np.logical_not(fjord)] = False
    # Retreat: Place starting with ice, not has no ice
    where_retreat = np.logical_and(thk0 != 0, thk1 == 0)
    where_retreat[np.logical_not(fjord)] = False

    # Total volume of advance / retreat
    adv = thk1.copy()
    adv[np.logical_not(where_advance)] = 0
    ret = thk0.copy()
    ret[np.logical_not(where_retreat)] = 0
    advret = adv - ret
    thkdiff = thk1 - thk0

    # ------------------ Compute area of advance/retret in data vs. simulation
    print('where_advance ', where_advance)
    print('   sum ',np.sum(where_advance))
    dyx_area = fb.dx*fb.dy
    print('    dyx_area = ',dyx_area)
    adv_model = np.sum(where_advance) * dyx_area
    ret_model = np.sum(where_retreat) * dyx_area
    print('AdvRet: {}'.format([adv_model, ret_model]))

    # ============================================================
    # --------------- Compute functions of velocity
    with netCDF4.Dataset(velocity_file) as nc:
        # Flux, not surface velocity
        vv = thk0 * nc.variables['v_ssa_bc'][itime,:]
        uu = thk0 * nc.variables['u_ssa_bc'][itime,:]

    # Compute Jacobian (gradiant) of Velocity vector
    d_dy = findiff.FinDiff(0, fb.dy)
    d_dx = findiff.FinDiff(1, fb.dx)
    dv_dy = d_dy(vv)
    dv_dx = d_dx(vv)
    du_dy = d_dy(uu)
    du_dx = d_dx(uu)
    print('shapes1: {} {}'.format(vv.shape, dv_dx.shape))

    # div = dv_dy + du_dx

    # Compute strain rate tensor
    # Follows: https://en.wikipedia.org/wiki/Strain-rate_tensor
    # L = [[dv_dy, du_dy],
    #      [dv_dx, du_dx]]
    # E = 1/2 (L + L^T)    [symmetric tensor]
    E_yy = dv_dy
    E_xx = du_dx
    E_yx = .5 * (du_dy + dv_dx)


    # Obtain eigenvalues (L1,L2) of the strain rate tensor
    # Closed form eigenvalues of a 2x2 matrix
    # http://people.math.harvard.edu/~knill/teaching/math21b2004/exhibits/2dmatrices/index.html
    T = E_yy + E_xx    # Trace of strain rate tensor = divergence of flow
    flux_divergence = T    # Trace of tensor is same as flux divergence of flow (v,u)
    D = E_yy*E_xx - E_yx*E_yx   # Determinate of strain rate tensor
    qf_A = .5*T
    qf_B = np.sqrt(.25*T*T - D)
    L1 = qf_A + qf_B   # Biggest eigenvalue
    L2 = qf_A - qf_B   # Smaller eigenvalue


    # Follows Morlighem et al 2016: Modeling of Store
    # Gletscher's calving dynamics, West Greenland, in
    # response to ocean thermal forcing
    # https://doi.org/10.1002/2016GL067695
    print(type(L1))
    print('shape2', L1.shape)
    maxL1 = np.maximum(0.,L1)
    maxL2 = np.maximum(0.,L2)
    # e2 = [effective_tensile_strain_rate]^2
    e2 = .5 * (maxL1*maxL1 + maxL2*maxL2)    # Eq 6

    glen_exponent = 3    # n=3

    # PISM computes ice hardness (B in Morlighem et al) as follows:
    # https://github.com/pism/pism/blob/44db29423af6bdab2b5c990d08793010b2476cc5/src/rheology/IsothermalGlen.cc
    # https://github.com/pism/pism/blob/44db29423af6bdab2b5c990d08793010b2476cc5/src/rheology/FlowLaw.cc
    hardness_power = -1. / glen_exponent


    # Table from p. 75 of:
    # Cuffey, K., and W. S. B. Paterson (2010), The
    # Physics of Glaciers, Elsevier, 4th ed., Elsevier,
    # Oxford, U. K.
    # Table 3.4: Recommended base values of creep
    #            parameter $A$ at different temperatures
    #            and $n=3$
    # T (degC) | A (s-1Pa-3)
    #  0    2.4e-24
    #- 2    1.7e-24
    #- 5    9.3e-25
    #-10    3.5e-25
    #-15    2.1e-25
    #-20    1.2e-25
    #-25    6.8e-26
    #-30    3.7e-26
    #-35    2.0e-26
    #-40    1.0e-26
    #-45    5.2e-27
    #-50    2.6e-27

    # https://github.com/pism/pism/blob/5e1debde2dcc69dfb966e8dec7a58963f1967caf/src/pism_config.cdl
    # pism_config:flow_law.isothermal_Glen.ice_softness = 3.1689e-24;
    # pism_config:flow_law.isothermal_Glen.ice_softness_doc = "ice softness used by IsothermalGlenIce :cite:`EISMINT96`";
    # pism_config:flow_law.isothermal_Glen.ice_softness_type = "number";
    # pism_config:flow_law.isothermal_Glen.ice_softness_units = "Pascal-3 second-1";
    softness_A = 3.1689e-24
    hardness_B = pow(softness_A, hardness_power)

    # Compute tensile von Mises stress, used for threshold calving
    tensile_von_Mises_stress = np.sqrt(3) * hardness_B * \
        np.power(e2, (1./(2*glen_exponent)))    # Eq 7
    # =============================================================================


    # ------------------- Append results to NetCDF file
    with netCDF4.Dataset(output_file4, 'a') as nc:
#        nc.success = ('t' if error_msg is None else 'f')
#        nc.adv_data = adv_data
        nc.adv_model = adv_model
#        nc.ret_data = ret_data
        nc.ret_model = ret_model
        nc.t0 = datetime.datetime.strftime(dt0, '%Y-%m-%d')
        nc.t1 = datetime.datetime.strftime(dt1, '%Y-%m-%d')

#        if error_msg is not None:
#            nc.error_msg = error_msg

        ncv = nc.createVariable('advret', 'd', ('y','x'), zlib=True)
        ncv.description = 'Thickness change of advancing (positive) and retreating (negative) ice'
        ncv[:] = advret

        ncv = nc.createVariable('thkdiff', 'd', ('y','x'), zlib=True)
        ncv.units = 'm'
        ncv.description = 'Thickness changes between first and last frame'
        ncv[:] = thkdiff

        ncv = nc.createVariable('xflux_divergence', 'd', ('y','x'), zlib=True)
        ncv.units = 's-1'
        ncv.description = 'Flux divergence of flow'
        ncv[:] = flux_divergence

        ncv = nc.createVariable('sigma', 'd', ('y','x'), zlib=True)
        ncv.units = 'Pa'
        ncv.description = 'Tensile von Mises stress (Morlighem et al 2016)'
        ncv[:] = tensile_von_Mises_stress



        # ------------------- Concatenate in vars from the _bedmachine.nc file
        with netCDF4.Dataset(bedmachine_file1) as ncin:
            nccopy = ncutil.copy_nc(ncin, nc)
            vnames = ('polar_stereographic', 'thickness', 'bed')
            nccopy.define_vars(vnames, zlib=True)
            for vname in vnames:
                nccopy.copy_var(vname)



def do_retreat(bedmachine_file, velocity_file, year, termini_file, termini_closed_file, terminus_id, output_file4, tdir, ofiles_only=False, **kwargs0):
    """
    bedmachine_file: <filename>
        Local bedmachine file extract
    velocity_file: <filename>
        File of velocities; must have same CRS and bounds as bedmachine_file
    ofiles_only:
        True if this should just compute output filenames and return
        (for use in make rules)
    kwargs0:
        kwargs given to PISM run
    """

    # Names of output files
    #output_file3 = os.path.splitext(output_file4)[0] + '.nc3'
    output_shp = os.path.splitext(output_file4)[0] + '_advret.shp'

    if ofiles_only:
        return [output_file4, output_shp]


#    # Check if the output already exists
#    if os.path.exists(output_file4):
#        return

    # Get total kwargs to use for PISM
    default_kwargs = dict(calving0.FrontEvolution.default_kwargs.items())
    default_kwargs['min_ice_thickness'] = 50.0
    default_kwargs['sigma_max'] = 1e6
    kwargs = argutil.select_kwargs(kwargs0, default_kwargs)

    remover = glaciers.IceRemover2(bedmachine_file)

    # Get CRS out of shapefile
    termini_crs = shputil.crs(termini_file)

    # Get years out of velocity file
    fb = gdalutil.FileInfo(velocity_file)
    years_ix = dict((dt.year,ix) for ix,dt in enumerate(fb.datetimes))

    # Run the glacier between timesteps
    # terminus_ix = 187    # Index in terminus file
    itime = years_ix[year]    # Index in velocity file

    # Prepare to store the output file
    odir = os.path.split(output_file4)[0]
    if len(odir) > 0:
        os.makedirs(odir, exist_ok=True)

    # Get ice thickness, adjusted for the present grounding line
    thk = remover.get_thk(termini_closed_file, terminus_id, odir, tdir)
    print('thk sum: {}'.format(np.sum(np.sum(thk))))
    bedmachine_file1 = tdir.filename()
    bedmachine.replace_thk(bedmachine_file, bedmachine_file1, thk)

    # Obtain start and end time in PISM units (seconds)
    dt0 = datetime.datetime(year,1,1)
    t0_s = fb.time_units_s.date2num(dt0)
    dt1 = datetime.datetime(year+1,1,1)
    #dt1 = datetime.datetime(year,1,3)
    t1_s = fb.time_units_s.date2num(dt1)


    # ---------------------------------------------------------------

    print('============ Running year {}'.format(year))
    print('     ---> {}'.format(output_file3))
    output_file3 = tdir.filename()
    try:

        # The append_time=True argument of prepare_output
        # determines if after this call the file will contain
        # zero (append_time=False) or one (append_time=True)
        # records.
        output = PISM.util.prepare_output(output_file3, append_time=False)

        #### I need to mimic this: Ross_combined.nc plus the script that made it
        # Script in the main PISM repo, it's in examples/ross/preprocess.py
        # bedmachine_file = "~/github/pism/pism/examples/ross/Ross_combined.nc"
        # bedmachine_file = "Ross_combined.nc"
        ctx = PISM.Context()
        # TODO: Shouldn't this go in calving0.init_geometry()?
        ctx.config.set_number("geometry.ice_free_thickness_standard", kwargs['min_ice_thickness'])

        grid = calving0.create_grid(ctx.ctx, bedmachine_file1, "thickness")
        geometry = calving0.init_geometry(grid, bedmachine_file1, kwargs['min_ice_thickness'])

        ice_velocity = calving0.init_velocity(grid, velocity_file)
        print('ice_velocity sum: '.format(np.sum(np.sum(ice_velocity))))

        # NB: For debugging I might use a low value of sigma_max to make SURE things retreat
        # default_kwargs = dict(
        #     ice_softness=3.1689e-24, sigma_max=1e6, max_ice_speed=5e-4)
        fe_kwargs = dict(sigma_max=0.1e6)
        front_evolution = calving0.FrontEvolution(grid, sigma_max=kwargs['sigma_max'])

        # ========== ************ DEBUGGING *****************
        #xout = PISM.util.prepare_output('x.nc', append_time=False)
        #PISM.append_time(xout, front_evolution.config, 17)
        #geometry.ice_thickness.write(xout)
        #geometry.cell_type.write(xout)
    

        # Iterate through portions of (dt0,dt1) with constant velocities
        ice_velocity.read(velocity_file, itime)   # 0 ==> first record of that file (if time-dependent)
        front_evolution(geometry, ice_velocity,
           t0_s, t1_s,
           output=output)
        exception = None
    except Exception as e:
        print('********** Error: {}'.format(str(e)))
        traceback.print_exc() 
        exception = e
    finally:
        output.close()

    output_file4_tmp = tdir.filename()
    pismutil.fix_output(output_file3, exception, fb.time_units_s, output_file4_tmp)

    cfn = calfin.ParseFilename(termini_file)
    trough_file = os.path.join('troughs', cfn.glacier_name + '.geojson')

    # Reproject...
    #ogr2ogr -f 'ESRI Shapefile' data/troughs/Rink-Isbrae.shp x.shp -t_srs EPSG:3413
    fjord = get_fjord(fb, trough_file, bedmachine_file1, tdir)

    # Debug
    with netCDF4.Dataset(output_file4_tmp, 'a') as nc:
        ncv = nc.createVariable('fjord', 'i1', ('y','x'), zlib=True)
        ncv[:] = fjord


    add_analysis(output_file4_tmp, itime, dt0, dt1, bedmachine_file1, velocity_file, fb, fjord)

    # ------------------- Create final output file
    os.rename(output_file4_tmp, output_file4)





def main():
    makefile = make.Makefile()
    bedmachine_file = 'outputs/BedMachineGreenland-2017-09-20_pism_W71.65N.nc'
#    velocity_file = 'outputs/TSX_W71.65N_2008_2020_filled.nc'
    velocity_file = 'outputs/GRE_G0240_W71.65N_2011_2018.nc'

    # Use terminus #187
    termini_file = 'data/calfin/domain-termini/termini_1972-2019_Rink-Isbrae_v1.0.shp'
    termini_closed_file = 'data/calfin/domain-termini-closed/termini_1972-2019_Rink-Isbrae_closed_v1.0.shp'
    otemplate = 'outputs/retreat_calfin_W71.65N_{dt0}_{dt1}/data.nc'

#    compute(makefile,
#        bedmachine_file, velocity_file, termini_file, termini_closed_file, otemplate).run()


    with ioutil.TmpDir() as tdir:
        do_retreat(bedmachine_file, velocity_file, 2017, termini_file, termini_closed_file, 187, 'retreated.nc', tdir, sigma_max=1e5)

main()
