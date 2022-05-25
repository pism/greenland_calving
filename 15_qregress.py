from uafgi.data import d_velterm
import uafgi.data.stability as d_stability
import uafgi.data.wkt
from uafgi.pism import qregress
import matplotlib.pyplot as plt

# Implement Slater et al 2019

def main():
    # Read our set of glaciers
    map_wkt = uafgi.data.wkt.nsidc_ps_north
    select = d_stability.read_select(map_wkt)

    # Read data from my experiment
    velterm_df = d_velterm.read()

    # Returns wdfs[] 2 dataframes:
    #     wdfs[0] = dataframe for glaciers in regions SE,SW,CE,CW,NE
    #     wdfs[1] = dataframe for glaciers in regions N,NW
    wdfs = qregress.wood_q4tf(select)   # Q^4 * TempFjord
    rdf = qregress.read_retreats(select)
    mdfs = qregress.join_retreats_q4tf(rdf,wdfs,decade_mean=True)

    print(mdfs)

    kappas = qregress.regress_kappas(mdfs)

    for i,mdf in enumerate(mdfs):
        mdf.plot.scatter('q4tf', 'up_len')
#        plt.show()
        plt.savefig(f'x{i}.png')

    print(kappas)

main()

