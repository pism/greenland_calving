from uafgi.data import d_velterm
from uafgi import stability,ioutil
import uafgi.data.wkt
import uafgi.data.stability as d_stability
import matplotlib.pyplot as plt
import os,subprocess
import matplotlib

PUB_ROOT = '/Users/eafischer2/overleaf/CalvingPaper/plots'
map_wkt = uafgi.data.wkt.nsidc_ps_north

def write_plot(fig, ofname):
    # Write plot and shrink
    with ioutil.TmpDir() as tdir:
        fname0 = tdir.filename() + '.png'
        fig.savefig(fname0, dpi=300, transparent=True)
        with ioutil.WriteIfDifferent(ofname) as wid:
            cmd = ['convert', fname0, '-trim', '-strip', wid.tmpfile]
            subprocess.run(cmd, check=True)

def main():
    # Bigger fonts
    # https://stackabuse.com/change-font-size-in-matplotlib/
    # (refer back if this doesn't fix tick label sizes)
    matplotlib.pyplot.rcParams['font.size'] = '16'

    select = d_stability.read_select(map_wkt)
    velterm_df = d_velterm.read()

    # Get AP Barnstorff Glacier (ID 65)
    df = select.df.set_index('w21t_glacier_number')
#    selrow = df.loc[62]
    selrow = select.df[select.df.w21t_glacier_number == 62].iloc[0]
    print(selrow)
    print(list(df.columns))
    print(selrow['w21t_glacier_number'])
    print(selrow.w21t_glacier_number)
    print(selrow.w21t_Glacier)

    # Plot the Slater predictions vs. our measured reality
    slfit = stability.fit_slater_residuals(selrow, velterm_df)
    rdf = slfit.resid_df
    plt.vlines(rdf.term_year, rdf.our_termpos, rdf.sl19_pred_termpos, color='xkcd:dark grey')
    plt.plot(rdf.term_year, rdf.our_termpos, marker='*')
    plt.plot(rdf.term_year, rdf.sl19_pred_termpos, marker='*')
    plt.xticks(ticks=[2000, 2005, 2010, 2015, 2020])

#    plt.title(selrow.w21t_Glacier)

    leaf = 'resid_{}'.format(selrow.ns481_grid)
    write_plot(plt, os.path.join(PUB_ROOT, leaf+'.png'))

main()
