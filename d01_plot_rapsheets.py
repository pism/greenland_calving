import netCDF4
import sys
import uafgi.data
import uafgi.data.wkt
from uafgi import stability,bedmachine
from uafgi.util import ioutil,cptutil,cartopyutil,dtutil
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

#PUB_ROOT = '/Users/eafischer2/overleaf/CalvingPaper/plots'
map_wkt = uafgi.data.wkt.nsidc_ps_north

#margin=(.17,.15,.83,.85)    # left, bottom, width, height
margin=(.15,.15,.98,.98)    # left, bottom, right, top
def _rect(*delta):
    """
    delta: (left margin, bottom margin, right margin, top margin)
        Change to standard margins
        For right and top, negative number means bigger margin
    """

    mm = [m+d for m,d in zip(margin,delta)]
    return (mm[0], mm[1], mm[2]-mm[0], mm[3]-mm[1])



# ------------------------------------------------------------
ELEV_RANGE = (-1000, 0)


#def plot_reference_cbar(fig):
##    # Get local geometry
##    bedmachine_file = uafgi.data.join_outputs('bedmachine', 'BedMachineGreenland-2017-09-20_{}.nc'.format(#selrow.ns481_grid))
##    with netCDF4.Dataset(bedmachine_file) as nc:
##        nc.set_auto_mask(False)
##        mapinfo = cartopyutil.nc_mapinfo(nc, 'polar_stereographic')
#
#    cmap,_,_ = cptutil.read_cpt('palettes/Blues_09a.cpt')
#    pltutil.plot_cbar(
#        fig, cmap,
#        ELEV_RANGE[0], ELEV_RANGE[1], 'horizontal')


def plot_reference_cbar(fig):
    """cax:
        Axes to use
    """
    cmap,_,_ = cptutil.read_cpt('palettes/Blues_09a.cpt')
    norm = matplotlib.colors.Normalize(vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1], clip=True)
    ax = fig.add_axes((.1,.6,.8,.35))

    # Plot colorbar
    cb1 = matplotlib.colorbar.ColorbarBase(
        ax, cmap=cmap, norm=norm,
        orientation='horizontal')
    cb1.locator = matplotlib.ticker.FixedLocator([-1000, -800, -600, -400, -200, 0])
    cb1.update_ticks()

    return cb1


def plot_reference_map(fig, selrow, pub=False):
    """Plots a reference map of a single glacier

    fig:
        Pre-created figure (of a certain size/shape) to populate.
    selrow:
        Row of d_stability.read()"""

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

    # Set up the basemap
    ax = fig.add_axes((.1,.1,.9,.86), projection=mapinfo.crs)
    #ax.set_facecolor('xkcd:light grey')    # https://xkcd.com/color/rgb/
    ax.set_facecolor('#E0E0E0')    # Map background https://xkcd.com/color/rgb/

    #ax = fig.add_subplot(spec[2,:], projection=mapinfo.crs)
    ax.set_extent(mapinfo.extents, crs=mapinfo.crs)
#    ax.coastlines(resolution='50m')


    # Plot depth in the fjord
    fjord_gd = bedmachine.get_fjord_gd(bedmachine_file, selrow.fj_poly)
    fjord = np.flip(fjord_gd, axis=0)
    bedm = np.ma.masked_where(np.logical_not(fjord), bed)

    bui_range = (0.,350.)
    cmap,_,_ = cptutil.read_cpt('palettes/Blues_09a.cpt')

    pcm = ax.pcolormesh(
        xx, yy, bedm, transform=mapinfo.crs,
        cmap=cmap, vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1])
    if not pub:
        cbar = fig.colorbar(pcm, ax=ax)
        cbar.set_label('Fjord Bathymetry (m)')
##    plot_reference_cbar(pcm, 'refmap_cbar.png')

    # Plot the termini
    date_termini = sorted(selrow.w21t_date_termini)

    yy = [dtutil.year_fraction(dt) for dt,_ in date_termini]
    year_termini = [(y,t) for y,(_,t) in zip(yy, date_termini) if y > 2000]

    norm = matplotlib.colors.Normalize(vmin=1980, vmax=2020, clip=True)
    mapper = matplotlib.cm.ScalarMappable(norm=norm, cmap=sigma_by_velyear_cmap)
    edgecolor = 'red'    # Default
    for year,term in year_termini:
        edgecolor = mapper.to_rgba(year)
        ax.add_geometries([term], crs=mapinfo.crs, edgecolor=edgecolor, facecolor='none', alpha=.8)

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


# ------------------------------------------------------------
def plot_year_termpos(fig, slfit, pub=False):
    """Plots year vs melt and year vs terminus position
    pub: bool
        Is this for publication?"""

    ax = fig.add_axes(_rect(0.009,0, -.12,0))
    ax1 = ax.twinx()

    print('Slater termpos by year')

    # Left y-axis: terminal position by year
    if not pub:
        ax.set_xlabel('Year', fontsize=14)
        ax.set_ylabel('Terminus (km)', fontsize=14)
    ax.plot(slfit.bbins, slfit.termpos_b, marker='.')
    lr = slfit.termpos_lr
    ax.plot(slfit.bbins1, lr.slope*slfit.up_len_km_b1 + lr.intercept, marker='.')
    ax.set_xlim((1980,2020))
    ax.set_xticks([1980,1990,2000,2010,2020])

    # ------- Right axis: melt by year
    # 5-year melt plot
    ax1.plot(slfit.bbins, slfit.melt_b, marker='.', color='green')
    # 1-year melt plot
    # ax1.plot(slfit.bbins1, slfit.melt_b1, marker='.', color='green')
    if not pub:
        ax1.set_ylabel('Melt ($Q^{0.4}$ TF)')



def plot_uplen_termpos(fig, slfit, pub=False):
    """
    slfit: FitSlaterResidualsRet
    """
    ax = fig.add_axes(_rect(.02,0, 0,0))

    _ = slfit    # shortcut

    #print('up_len_km (x) vs. Slater termpos (y)')
    #print(termpos_lr)
    ax.scatter(_.up_len_km_b1, _.termpos_b1, marker='.', c=_.bbins1, cmap=sigma_by_velyear_cmap)
    ax.plot(
        _.up_len_km_b1,
        _.termpos_lr.slope*_.up_len_km_b1 + _.termpos_lr.intercept)
    if not pub:
        ax.set_xlabel('Wood Terminus (km)', fontsize=14)
        ax.set_ylabel('Slater Terminus (km)', fontsize=14)

sigma_by_velyear_cmap,_,_ = cptutil.read_cpt('palettes/pride_flag_1978x.cpt')

def plot_year_cbar(fig):
    """cax:
        Axes to use
    """
    cmap = sigma_by_velyear_cmap
    norm = matplotlib.colors.Normalize(vmin=1980, vmax=2020, clip=True)
    ax = fig.add_axes((.1,.6,.8,.35))

    # Plot colorbar
    cb1 = matplotlib.colorbar.ColorbarBase(
        ax, cmap=cmap, norm=norm,
        orientation='horizontal')
#    ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately
#    if not pub:
#        cb1.set_label('Surface Velocity Year')
#    cb1.locator = matplotlib.ticker.FixedLocator([1980,1984,1988,1992,1996,2000,])
    cb1.locator = matplotlib.ticker.FixedLocator([1980,1990,2000,2010,2020])
    cb1.update_ticks()

    return cb1

def plot_sigma_by_velyear(fig, slfit, pub=False):

    # Set up mapping between vel_year and color
    cmap = sigma_by_velyear_cmap
    norm = matplotlib.colors.Normalize(vmin=1980, vmax=2020, clip=True)
    mapper = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)

    # Create axes for main plot and colorbar
    ax = fig.add_axes(_rect(.0,0, -.15,0))
    divider = mpl_toolkits.axes_grid1.make_axes_locatable(ax)   # Make room for colorscale
    cax = divider.append_axes('right', size='3%', pad=0.05)

    # Plot main plot
    for vel_year,df in slfit.glacier_df.groupby('vel_year'):
        df['fluxratio'] = df['fluxratio'] / 1000.   # Convert to kPa
        ax.plot(df.set_index('term_year')[['fluxratio']], linewidth=.5,marker='.', color=mapper.to_rgba(vel_year))
    ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([2000,2005,2010,2015,2020]))
    if not pub:
        ax.set_xlabel('Terminus Year')
        ax.set_ylabel('von Mises \u03C3 across Terminus (kpa)')

    # Plot colorbar
    cb1 = matplotlib.colorbar.ColorbarBase(
        cax, cmap=cmap, norm=norm,
        orientation='vertical')
    if not pub:
        cb1.set_label('Surface Velocity Year')
#    cb1.locator = matplotlib.ticker.FixedLocator([1980,1984,1988,1992,1996,2000,])
    cb1.locator = matplotlib.ticker.FixedLocator([1980,1985,1990,1995,2000,2005,2010,2015,2020])
    cb1.update_ticks()


def plot_melt_termpos(fig, slfit, pub=False):
    """Plotsmelt vs. termpos, 5-year bins (dup of Slater's plot)"""

    ax = fig.add_axes(_rect(0,0,0,0))

    lr = slfit.slater_lr
    ax.scatter(slfit.melt_b, slfit.termpos_b)
    ax.plot(slfit.melt_b, lr.slope*slfit.melt_b + lr.intercept)
    ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([2000,2005,2010,2015,2020]))
    if not pub:
        ax.set_xlabel('Melt ($Q^{0.4}$ TF)', fontsize=14)
        ax.set_ylabel('Slater Terminus (km)', fontsize=14)

def plot_termpos_residuals(fig, slfit, pub=False):

    ax = fig.add_axes(_rect(0,0,0,0))

    df = slfit.resid_df
    lr = slfit.resid_lr
    ax.scatter(df.fluxratio*1e-3, df.termpos_residual, c=df.term_year, cmap=sigma_by_velyear_cmap)
#    ax.scatter(df.fluxratio*1e-3, df.termpos_residual, c='green', cmap=sigma_by_velyear_cmap)
    ax.plot(df.fluxratio*1e-3, df.fluxratio * lr.slope + lr.intercept)
    if not pub:
        ax.set_xlabel('von Mises \u03C3 Across Terminus (kPa)', fontsize=14)    # Sigma
        ax.set_ylabel('Slater Terminus Residual (km)', fontsize=14)

    ax.set_ylim((-4.,2.))
#    ax.set_yticks([1980,1990,2000,2010,2020])

# ---------------------------------------------------------
# Combos we want to publish

_triplet_vars = ('year_termpos', 'termpos_residuals', 'map')
def triplet(gname):
    return [(gname,vname) for vname in _triplet_vars]

publish_combos = {
    ('Hayes N', 'sigma_by_year'),
    ('Lille', 'mapcbar'),
    ('Lille', 'yearcbar'),
    ('Lille', 'map'),
    ('Lille', 'termpos_residuals'),
}

for gname in ('Puisortoq N', 'Puisortoq S', 'Eqip Sermia', 'Gyldenlove N', 'Kujalleq', 'Lille', 'AP Bernstorff', 'Inngia', 'Cornell N', 'Hayes NN', 'Rink Isbrae', 'Sermeq Avannarleq', 'Koge Bugt S', 'Daugaard Jensen', 'Mogens Heinesen S', 'Kangilernata', 'Uunartit'):
    for x in triplet(gname):
        publish_combos.add(x)
# ---------------------------------------------------------

def plot_page(odir_gl, odir_pub, selrow, velterm_df, make_rapsheet=True, pub=False):
    slfit = stability.fit_slater_residuals(selrow, velterm_df)
    rlr = slfit.resid_lr

#    if rlr.pvalue > 0.15:
#        raise ValueError('Residual Fit Not Significant')
#
#    if abs(slfit.up_len_km_b1[-1] - slfit.up_len_km_b1[0]) < .8:
#        raise ValueError('Not Enough Retreat')

    if make_rapsheet:
        os.makedirs(odir_gl, exist_ok=True)
        shutil.copy('fontsize.sty', odir_gl)

        with open(os.path.join(odir_gl, 'page.tex'), 'w') as out:
            out.write(page_tpl.substitute(
                TITLE='{} - {} - w={} r={}'.format(
                    selrow['ns481_grid'],
                    selrow.w21t_Glacier,
                    selrow.w21t_glacier_number, int(selrow.sl19_rignotid)),
                Title1=r'Terminus and Melt \\ \tiny{blue: Slater Terminus; orange: Wood Terminus; green: Melt}',
                Title2='Terminus Translation',
                Title3='$\sigma_{\scriptscriptstyle T}$ by Velocity Year',
                #Title3='Melt vs. Terminus (5-yr)',
                Title4=r'{} vs. Terminus Residuals \\ \tiny {}slope={:1.3f}, R={:1.2f}, p={:1.4f}{}'.format(
                    r'$\bar{\sigma_{\scriptscriptstyle T}}$', '{', rlr.slope*1000, abs(rlr.rvalue), rlr.pvalue, '}'),
            ))


#    if pub:
#        os.makedirs(odir_pub, exist_ok=True)

    small = (5.5,4.5)
    for fname,size, do_plot in [
        ('uplen_termpos', small, lambda fig: plot_uplen_termpos(fig, slfit, pub=pub)),
        ('year_termpos', small, lambda fig: plot_year_termpos(fig, slfit, pub=pub)),
        ('melt_termpos', small, lambda fig: plot_melt_termpos(fig, slfit, pub=pub)),
        ('sigma_by_year', small, lambda fig: plot_sigma_by_velyear(fig, slfit, pub=pub)),
        ('termpos_residuals', small, lambda fig: plot_termpos_residuals(fig, slfit, pub=pub)),
        ('map', (8.,4.), lambda fig: plot_reference_map(fig, selrow, pub=pub)),
        ('mapcbar', (5.,0.6), lambda fig: plot_reference_cbar(fig)),
        ('yearcbar', (5.,0.6), lambda fig: plot_year_cbar(fig))]:

        if make_rapsheet:
            fig = matplotlib.pyplot.figure(figsize=size)
            do_plot(fig)
            fig.savefig(os.path.join(odir_gl, fname+'.png'))

        if pub and (selrow.w21t_Glacier, fname) in publish_combos:
            ofname = os.path.join(odir_pub, fname+'_300.png')
            print('fname = ', ofname)
            fig = matplotlib.pyplot.figure(figsize=size)
            do_plot(fig)
            os.makedirs(odir_pub, exist_ok=True)
            with ioutil.TmpDir(dir=odir_pub) as tdir:
                fname0 = tdir.filename() + '.png'
                fig.savefig(fname0, dpi=300)   # Hi-res version

                with ioutil.WriteIfDifferent(ofname) as wid:
                    cmd = ['convert', fname0, '-trim', '-strip', wid.tmpfile]
                    subprocess.run(cmd, check=True)
#                    shutil.copy(fname0, wid.tmpfile)

            fig.clf()

    if make_rapsheet:
        cmd = ['pdflatex', 'page.tex']
        env = dict(os.environ.items())
        env['TEXINPUTS'] = '.:..:../..:'
        subprocess.run(cmd, cwd=odir_gl, env=env, check=True)

    # Return the data we computed along the way
    ret = slfit._asdict()
    del ret['glacier_df']

    rdf = ret['resid_df']
    for field in ('term_year', 'fluxratio', 'termpos_residual'):
        ret[field] = rdf[field].values
    del ret['resid_df']
    return ret

def all_plots(make_rapsheet, pub):

    # Bigger fonts
    # https://stackabuse.com/change-font-size-in-matplotlib/
    # (refer back if this doesn't fix tick label sizes)
    matplotlib.pyplot.rcParams['font.size'] = '16'

#    select = d_stability.read_select(map_wkt)
    select = d_stability.read_extract(map_wkt, joins={'w21', 'sl19', 'fj', 'w21t'})
    velterm_df = d_velterm.read()

    #odir = 'tw_plots2'
    #os.makedirs(odir, exist_ok=True)

    rows = list()
    rows2 = list()
    for ix,selrow in select.iterrows():
        if np.isnan(selrow.sl19_rignotid):
            # No Slater19 data
            continue

#        if selrow.w21t_glacier_number != 65:
#            continue

        print('========================= ix = {}'.format(ix))
        leaf = '{}_{}_{}'.format(
            selrow.ns481_grid.replace('.',''),
            selrow.w21t_glacier_number,
            selrow.w21t_Glacier.replace('_','-').replace('.',''))
        odir_gl = uafgi.data.join_outputs('rapsheets', leaf)
        #odir_gl = os.path.join(odir, leaf)
        #odir_pub = os.path.join(PUB_ROOT, leaf)
        odir_pub = uafgi.data.join_plots(leaf)

#        os.makedirs(odir_gl, exist_ok=True)
#        os.makedirs(odir_pub, exist_ok=True)

        # Quicker debugging
#        if os.path.exists(ofname):
#            continue

#        with ioutil.TmpDir() as tdir:
        if True:
            try:
                row = plot_page(odir_gl, odir_pub, selrow, velterm_df, make_rapsheet=make_rapsheet, pub=pub)
                #os.rename(os.path.join(tdir.location, 'page.pdf'), ofname)
                # Make DataFrame for collect program
                row['plot_page'] = leaf
                row['ns481_grid'] = selrow.ns481_grid
                row['w21t_glacier_number'] = selrow.w21t_glacier_number
                row['w21t_Glacier'] = selrow.w21t_Glacier
                rows.append(row)

                # Make CSV-able DataFrame for users
                row2 = dict()
#                row2['w21t_Glacier'] = selrow.w21t_Glacier
                row2['w21t_glacier_number'] = selrow.w21t_glacier_number
#                row2['ns481_grid'] = selrow.ns481_grid

                lr = row['termpos_lr']
                for k in lr._fields:
                    row2[f'tp_{k}'] = getattr(lr, k)

                lr = row['slater_lr']
                for k in lr._fields:
                    row2[f'sl_{k}'] = getattr(lr, k)

                lr = row['resid_lr']
                for k in lr._fields:
                    row2[f'rs_{k}'] = getattr(lr, k)
                rows2.append(row2)

                #break        # DEBUG: Just one plot
            except Exception as e:
                shutil.rmtree(odir_gl, ignore_errors=True)
                sys.stdout.flush()
                traceback.print_exc()
                sys.stderr.flush()

    if make_rapsheet:
        # Main CSV file for users
        df = pd.DataFrame(rows2)
        select = d_stability.read_extract_raw()
        df = pd.merge(select, df, how='left', on='w21t_glacier_number')
        df.to_csv(uafgi.data.join_outputs('stability', 'greenland_calving.csv'))
        df.to_pickle(uafgi.data.join_outputs('stability', 'greenland_calving.pik'))


        resid_df = pd.DataFrame(rows)

        cats = list()
        for ix,row in resid_df.iterrows():
            rlr = row.resid_lr
            if row.stable_terminus:
                cat = 'stable'
            elif rlr.pvalue >= 0.21:
                cat = 'inretreat'
            elif row.resid_lr.slope < 0:
                cat = 'destabilize'
            else:
                cat = 'stabilize'
            cats.append(cat)
        resid_df['category'] = cats


        # No need to write out, we use it right here!
        resid_df.to_pickle(uafgi.data.join_outputs('rapsheets', 'regressions.pik'))
        # resid_df = pd.read_pickle(uafgi.data.join_outputs('rapsheets', 'regressions.pik'))

        # Categorize glacier behavior, and put in different PDF files
        destabilize = list()
        stabilize = list()
        inretreat = list()
        stable = list()
        for ix,row in resid_df.iterrows():
            print(row)
#            rlr = row.resid_lr

            locals()[row.category].append(row)
#            if row.stable_terminus:
#                stable.append(row)
#            elif rlr.pvalue >= 0.21:
#                inretreat.append(row)
#            elif row.resid_lr.slope < 0:
#                destabilize.append(row)
#            else:
#                stabilize.append(row)


        for catname,eles in (('destabilize',destabilize), ('stabilize',stabilize), ('inretreat', inretreat), ('stable',stable)):
            fnames = [uafgi.data.join_outputs('rapsheets', row.plot_page, 'page.pdf') for row in eles]
            cmd = ['pdftk'] + fnames + ['cat', 'output', uafgi.data.join_outputs(f'rapsheets_{catname}.pdf')]
            subprocess.run(cmd)


def main():
    # Make select publication plots
    all_plots(False, True)

    # Make rapsheets for all glaciers
    all_plots(True, False)


page_tpl = string.Template(r"""
\documentclass{article}

\usepackage{times}
\usepackage[fontsize=11pt]{fontsize}
\usepackage{grid-system}
\usepackage{graphicx}
\usepackage[letterpaper,portrait,margin=.5in]{geometry}

% https://stackoverflow.com/questions/877597/how-do-you-change-the-document-font-in-latex
\renewcommand{\familydefault}{\sfdefault}

% No indents  https://github.com/PierreSenellart/erc-latex-template/issues/1
\setlength{\parindent}{0pt}
\pagestyle{empty}

\begin{document}

\begin{center}{\LARGE $TITLE}\end{center}

\begin{Row}

\begin{Cell}{1}
\begin{center}
$Title1 \\
\includegraphics[width=.9\textwidth]{year_termpos}
\end{center}
\end{Cell}

\begin{Cell}{1}
\begin{center}
$Title2 \\
\includegraphics[width=.9\textwidth]{uplen_termpos}
\end{center}
\end{Cell}

\end{Row}
\begin{Row}

\begin{Cell}{1}
\begin{center}
$Title3 \\
\includegraphics[width=.9\textwidth]{sigma_by_year}
\end{center}
\end{Cell}

\begin{Cell}{1}
\begin{center}
$Title4 \\
\includegraphics[width=.9\textwidth]{termpos_residuals}
\end{center}
\end{Cell}

\end{Row}


\begin{Row}
\vspace{1ex}
\begin{Cell}{4}
\begin{center}
\includegraphics[width=.8\textwidth]{map.png}
\end{center}

\end{Cell}
\end{Row}


\end{document}
""")






main()



#Textual data:
#
#w21 name
#nsidc481 grid
#w21t_glacier_id
#regnot_id
#iloc in our dataframe

