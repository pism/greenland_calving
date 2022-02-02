import uafgi.data.wkt
from uafgi import stability,ioutil
import uafgi.data.stability as d_stability
from uafgi.data import d_velterm
import os
import matplotlib.pyplot
import string
import shutil
import subprocess
import numpy as np
import traceback
import pandas as pd

map_wkt = uafgi.data.wkt.nsidc_ps_north

#margin=(.17,.15,.83,.85)    # left, bottom, width, height
margin=(.15,.15,.98,.98)    # left, bottom, right, top
def _rect(*delta):
    mm = [m+d for m,d in zip(margin,delta)]
    return (mm[0], mm[1], mm[2]-mm[0], mm[3]-mm[1])

def plot_year_termpos(fig, slfit):
    """Plots year vs melt and year vs terminus position"""

    ax = fig.add_axes(_rect(0,0, -.12,0))
    ax1 = ax.twinx()

    print('Slater termpos by year')

    # Left y-axis: terminal position by year
    ax.set_xlabel('Year', fontsize=14)
    ax.set_ylabel('Slater Terminus (km)', fontsize=14)
    ax.plot(slfit.bbins, slfit.termpos_b, marker='.')
    lr = slfit.termpos_lr
    ax.plot(slfit.bbins1, lr.slope*slfit.up_len_km_b1 + lr.intercept, marker='.')

    # Right axis: melt by year
    ax1.plot(slfit.bbins, slfit.melt_b, marker='.', color='green')
    ax1.set_ylabel('Melt')



def plot_uplen_termpos(fig, slfit):
    """
    slfit: FitSlaterResidualsRet
    """
    ax = fig.add_axes(_rect(.02,0, 0,0))

    _ = slfit    # shortcut
    #print('up_len_km (x) vs. Slater termpos (y)')
    #print(termpos_lr)
    ax.scatter(_.up_len_km_b1, _.termpos_b1, marker='.')
    ax.plot(
        _.up_len_km_b1,
        _.termpos_lr.slope*_.up_len_km_b1 + _.termpos_lr.intercept)
    ax.set_xlabel('MEASURES Terminus (km)', fontsize=14)
    ax.set_ylabel('Slater Terminus (km)', fontsize=14)

def plot_melt_termpos(fig, slfit):
    """Plotsmelt vs. termpos, 5-year bins (dup of Slater's plot)"""

    ax = fig.add_axes(_rect(0,0,0,0))

    lr = slfit.slater_lr
    ax.scatter(slfit.melt_b, slfit.termpos_b)
    ax.plot(slfit.melt_b, lr.slope*slfit.melt_b + lr.intercept)
    ax.set_xlabel('Melt (Q^.4 * TF)', fontsize=14)
    ax.set_ylabel('Slater Terminus', fontsize=14)

def plot_termpos_residuals(fig, slfit):

    ax = fig.add_axes(_rect(0,0,0,0))

    df = slfit.resid_df
    lr = slfit.resid_lr
    ax.scatter(df.fluxratio*1e-3, df.termpos_residual)
    ax.plot(df.fluxratio*1e-3, df.fluxratio * lr.slope + lr.intercept)
    ax.set_xlabel('von Mises \u03C3 Across Terminus (kPa)', fontsize=14)    # Sigma
    ax.set_ylabel('Slater Terminus Residual (km)', fontsize=14)


def plot_page(odir, selrow, velterm_df):
    os.makedirs(odir, exist_ok=True)
    shutil.copy('fontsize.sty', odir)

    slfit = stability.fit_slater_residuals(selrow, velterm_df)
    rlr = slfit.resid_lr

#    if rlr.pvalue > 0.15:
#        raise ValueError('Residual Fit Not Significant')
#
#    if abs(slfit.up_len_km_b1[-1] - slfit.up_len_km_b1[0]) < .8:
#        raise ValueError('Not Enough Retreat')

    with open(os.path.join(odir, 'page.tex'), 'w') as out:
        out.write(page_tpl.substitute(
            TITLE='{} - {} - w={} r={}'.format(
                selrow['ns481_grid'],
                selrow.w21t_Glacier,
                selrow.w21t_glacier_number, int(selrow.sl19_rignotid)),
            Title1='Terminus (L) vs Melt (R)',
            Title2='Terminus Translation',
            Title3='Melt vs. Terminus (5-yr)',
            Title4=r'{} vs. Terminus Residuals \\ \tiny {}slope={:1.3f}, R={:1.2f}, p={:1.4f}{}'.format(
                r'$\sigma$', '{', rlr.slope*1000, abs(rlr.rvalue), rlr.pvalue, '}'),
        ))


    small = (5.5,4.5)
    for fname,size, do_plot in [
        ('uplen_termpos.png', small, lambda fig: plot_uplen_termpos(fig, slfit)),
        ('year_termpos.png', small, lambda fig: plot_year_termpos(fig, slfit)),
        ('melt_termpos.png', small, lambda fig: plot_melt_termpos(fig, slfit)),
        ('termpos_residuals.png', small, lambda fig: plot_termpos_residuals(fig, slfit)),
        ('map.png', (8.,4.), lambda fig: stability.plot_reference_map(fig, selrow))]:

        fig = matplotlib.pyplot.figure(figsize=size)
        do_plot(fig)
        fig.savefig(os.path.join(odir, fname))
        fig.clf()

    cmd = ['pdflatex', 'page.tex']
    subprocess.run(cmd, cwd=odir, check=True)

    # Return the data we computed along the way
    ret = slfit._asdict()
    del ret['glacier_df']

    rdf = ret['resid_df']
    for field in ('term_year', 'fluxratio', 'termpos_residual'):
        ret[field] = rdf[field].values
    del ret['resid_df']
    return ret

def main():

    select = d_stability.read_select(map_wkt)
    velterm_df = d_velterm.read()

    odir = 'tw_plots2'
    os.makedirs(odir, exist_ok=True)
    selrow = select.df.iloc[11]

    rows = list()
    for ix,selrow in select.df.iterrows():
        if np.isnan(selrow.sl19_rignotid):
            # No Slater19 data
            continue

        print('========================= ix = {}'.format(ix))
        leaf = '{}_{}_{}.pdf'.format(
            selrow.ns481_grid.replace('.',''),
            selrow.w21t_glacier_number,
            selrow.w21t_Glacier.replace('_','-').replace('.',''))
        ofname = os.path.join(odir, leaf)

        # Quicker debugging
#        if os.path.exists(ofname):
#            continue

        with ioutil.TmpDir() as tdir:
            try:
                row = plot_page(tdir.location, selrow, velterm_df)
                os.rename(os.path.join(tdir.location, 'page.pdf'), ofname)
                row['plot_page'] = leaf
                rows.append(row)
                #break        # DEBUG: Just one plot
            except Exception as e:
                traceback.print_exc()

    df = pd.DataFrame(rows)
    df.to_pickle('16_slfit.df')




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
\includegraphics[width=.9\textwidth]{melt_termpos}
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

