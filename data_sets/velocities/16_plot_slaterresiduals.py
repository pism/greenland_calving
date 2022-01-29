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

map_wkt = uafgi.data.wkt.nsidc_ps_north


margin=(.15,.15,.85,.85)
def plot_year_termpos(fig, slfit):
    """Plots year vs melt and year vs terminus position"""

    ax1 = fig.add_axes(margin)
    ax = ax1.twinx()

    print('Slater termpos by year')

    # Left axis: melt by year
    ax.plot(slfit.bbins1l, slfit.melt_b1l, marker='.')
    ax.set_ylabel('Melt')

    # Right y-axis: terminal position by year
    ax1.set_xlabel('Year', fontsize=14)
    ax1.set_ylabel('Slater Terminus', fontsize=14)
    ax1.plot(slfit.bbins1l, slfit.termpos_b1l, marker='.')
    lr = slfit.termpos_lr
    ax1.plot(slfit.bbins1, lr.slope*slfit.up_len_km_b1 + lr.intercept, marker='.')


def plot_uplen_termpos(fig, slfit):
    """
    slfit: FitSlaterResidualsRet
    """
    ax = fig.add_axes(margin)

    _ = slfit    # shortcut
    #print('up_len_km (x) vs. Slater termpos (y)')
    #print(termpos_lr)
    ax.scatter(_.up_len_km_b1, _.termpos_b1, marker='.')
    ax.plot(
        _.up_len_km_b1,
        _.termpos_lr.slope*_.up_len_km_b1 + _.termpos_lr.intercept)
    ax.set_xlabel('MEASURES Terminus', fontsize=14)
    ax.set_ylabel('Slater Terminus', fontsize=14)

def plot_melt_termpos(fig, slfit):
    """Plotsmelt vs. termpos, 5-year bins (dup of Slater's plot)"""

    ax = fig.add_axes(margin)

    lr = slfit.slater_lr
    ax.scatter(slfit.melt_b, slfit.termpos_b)
    ax.plot(slfit.melt_b, lr.slope*slfit.melt_b + lr.intercept)
    ax.set_xlabel('Melt (Q^.4 * TF)', fontsize=14)
    ax.set_ylabel('Slater Terminus', fontsize=14)

def plot_termpos_residuals(fig, slfit):

    ax = fig.add_axes(margin)

    df = slfit.resid_df
    lr = slfit.resid_lr
    ax.scatter(df.fluxratio, df.termpos_residual)
    ax.plot(df.fluxratio, df.fluxratio * lr.slope + lr.intercept)
    ax.set_xlabel('von Mises Sigma Across Terminus', fontsize=14)
    ax.set_ylabel('Slater Terminus Residual', fontsize=14)


def plot_page(odir, selrow, velterm_df):
    os.makedirs(odir, exist_ok=True)
    shutil.copy('fontsize.sty', odir)

    slfit = stability.fit_slater_residuals(selrow, velterm_df)
    rlr = slfit.resid_lr

    with open(os.path.join(odir, 'page.tex'), 'w') as out:
        out.write(page_tpl.substitute(
            TITLE='{} - {} - w={} r={}'.format(
                selrow['ns481_grid'],
                selrow.w21t_Glacier,
                selrow.w21t_glacier_number, int(selrow.sl19_rignotid)),
            Title1='Terminus (L) vs Melt (R)',
            Title2='Terminus Translation',
            Title3='Melt vs. Terminus (5-yr)',
            Title4=r'Sigma vs. Terminus Residuals \\ \tiny {}R={:1.2f}, p={:1.4f}{}'.format(
                '{', abs(rlr.rvalue), rlr.pvalue, '}'),
        ))


    small = (4.5,4.5)
    for fname,size, do_plot in [
        ('uplen_termpos.png', small, lambda fig: plot_uplen_termpos(fig, slfit)),
        ('year_termpos.png', small, lambda fig: plot_year_termpos(fig, slfit)),
        ('melt_termpos.png', small, lambda fig: plot_melt_termpos(fig, slfit)),
        ('termpos_residuals.png', small, lambda fig: plot_termpos_residuals(fig, slfit)),
        ('map.png', (8.,4.), lambda fig: stability.plot_reference_map(fig, selrow))]:

        fig = matplotlib.pyplot.figure(figsize=size)
        do_plot(fig)
        fig.savefig(os.path.join(odir, fname))

    cmd = ['pdflatex', 'page.tex']
    subprocess.run(cmd, cwd=odir, check=True)


def main():

    select = d_stability.read_select(map_wkt)
    velterm_df = d_velterm.read()

    odir = 'tw_plots2'
    os.makedirs(odir, exist_ok=True)
    selrow = select.df.iloc[11]

    for ix,selrow in select.df.iterrows():
        if np.isnan(selrow.sl19_rignotid):
            continue

        print('========================= ix = {}'.format(ix))
        ofname = os.path.join(odir, '{}_{}_{}.pdf'.format(
            selrow.ns481_grid.replace('.',''),
            selrow.w21t_glacier_number,
            selrow.w21t_Glacier.replace('_','-').replace('.','')))

        # Quicker debugging
        if os.path.exists(ofname):
            continue

        with ioutil.TmpDir() as tdir:
            try:
                plot_page(tdir.location, selrow, velterm_df)
                os.rename(os.path.join(tdir.location, 'page.pdf'), ofname)
            except Exception as e:
                traceback.print_exc()




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
\includegraphics[width=.8\textwidth]{year_termpos}
\end{center}
\end{Cell}

\begin{Cell}{1}
\begin{center}
$Title2 \\
\includegraphics[width=.8\textwidth]{uplen_termpos}
\end{center}
\end{Cell}

\end{Row}
\begin{Row}

\begin{Cell}{1}
\begin{center}
$Title3 \\
\includegraphics[width=.8\textwidth]{melt_termpos}
\end{center}
\end{Cell}

\begin{Cell}{1}
\begin{center}
$Title4 \\
\includegraphics[width=.8\textwidth]{termpos_residuals}
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

