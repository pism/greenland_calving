import os
import numpy as np
import pandas as pd
import uafgi.data
import uafgi.data.stability as d_stability
import uafgi.data.wkt

map_wkt = uafgi.data.wkt.nsidc_ps_north


catorder = {'destabilize': 0, 'stabilize': 1, 'stable': 2, 'inretreat': 3}

cattrans = {'destabilize': 'Destablizing', 'stabilize': 'Stabilizing', 'stable': 'Stable', 'inretreat': 'In Retreat'}

tpl_head = r"""\begin{tabular}{rccrrcc}
\multicolumn{1}{c}{ID} &
\multicolumn{1}{c}{Name} &
\multicolumn{1}{c}{Latitude} &
\multicolumn{1}{c}{Retreat} &
\multicolumn{1}{c}{$\nu$} &
\multicolumn{1}{c}{p-value} &
\multicolumn{1}{c}{mean $\bar{\sigmat}$} \\
   &      &          &
\multicolumn{1}{c}{(\si{\meter})} &
        &         &
\multicolumn{1}{c}{(\si{\kilo\pascal})} \\

\hline
"""

tpl_foot = r"""
\end{tabular}
"""


#rowtpl = """{row.w21t_glacier_number} & {row.w21t_Glacier_x} & {row.side}-{row.w21t_lat:0.1f} & {row.total_retreat_m:0.0f} & {row.rs_slope:1.1g} & {row.rs_pvalue_pct:0.0f} & {row.mean_bar_sigmat:0.0f}"""
rowtpl = """{row.sl19_rignotid:0.0f} & {row.w21t_Glacier_x} & {row.side}-{row.w21t_lat:0.1f} & {row.total_retreat_m:0.0f} & {row.rs_slope:1.1g} & {row.rs_pvalue:0.2f} & {row.mean_bar_sigmat:0.0f}"""



def main():
    resid_df = pd.read_pickle(uafgi.data.join_outputs('rapsheets', 'regressions.pik'))
    gdf = pd.read_pickle(uafgi.data.join_outputs('stability', 'greenland_calving.pik'))
    df = resid_df.merge(gdf, on='w21t_glacier_number')

#    print(resid_df)
    print(df.columns)

    print(df.iloc[0].fluxratio.mean())

    # > §6: I think that a table with lat/lon or region, total retreat, values of \nu, p-values, \bar{\sigma_T}, and classification (stabilizing, retreating, rapidly retreating, stable) for each glacier would be helpful.

    df['side'] = df['ns481_grid_x'].map(lambda x: x[0])
    df['mean_bar_sigmat'] = .001 * df['fluxratio'].map(lambda x: np.mean(x))

    df = df[['w21t_glacier_number', 'w21t_Glacier_x', 'sl19_rignotid', 'side', 'w21t_lat',
        'total_retreat_lsqr', 'rs_slope', 'rs_pvalue', 'mean_bar_sigmat', 'category']]

    df['total_retreat_m'] = 1000. * df['total_retreat_lsqr']
    df['order'] = df['category'].map(lambda x: catorder[x])
    df['scategory'] = df['category'].map(lambda x: cattrans[x])
    df = df.sort_values(['order','side','w21t_lat'])
    print(df)


    # Prepare the LaTeX
    lines = list()
    for (order,scat),df1 in df.groupby(['order', 'scategory']):

        lines.append("\hline")
        lines.append(r"\multicolumn{7}{c}{" + scat + "} \\\\")
        lines.append("\hline")
        
        catlines = list()
        for row in df1.itertuples():
            catlines.append(rowtpl.format(row=row))
        scatrows = '\\\\\n'.join(catlines)    # \\ <newline>
        lines.append(scatrows)
        lines.append('\\\\\n')

    lines = lines[:-1]    # Remove last newline

    stab = tpl_head + '\n'.join(lines) + tpl_foot
    ofname = os.path.abspath(uafgi.data.join_outputs('rapsheets', 'results.tex'))
    print(f'Writing {ofname}')
    with open(ofname, 'w') as out:
        out.write(stab)


main()



#Index(['bbins1', 'termpos_b1', 'up_len_km_b1', 'bbins1l', 'melt_b1l',
#       'termpos_b1l', 'bbins', 'melt_b', 'termpos_b', 'termpos_lr',
#       'slater_lr', 'resid_lr', 'total_retreat_lsqr', 'stable_terminus',
#       'term_year', 'fluxratio', 'termpos_residual', 'plot_page',
#       'ns481_grid_x', 'w21t_glacier_number', 'w21t_Glacier_x', 'category',
#       'Unnamed: 0', 'w21t_Glacier_y', 'greenlandic_name', 'w21t_lon',
#       'w21t_lat', 'w21_key', 'w21_data_fname', 'fj_fid', 'ns481_grid_y',
#       'up_fid', 'up_id', 'up_lon', 'up_lat', 'bkm15_id', 'cf20_key',
#       'cf20_glacier_id', 'ns642_GlacierID', 'sl19_bjorkid', 'sl19_rignotid',
#       'sl19_key', 'tp_slope', 'tp_intercept', 'tp_rvalue', 'tp_pvalue',
#       'tp_stderr', 'sl_slope', 'sl_intercept', 'sl_rvalue', 'sl_pvalue',
#       'sl_stderr', 'rs_slope', 'rs_intercept', 'rs_rvalue', 'rs_pvalue',
#       'rs_stderr'],
#      dtype='object')
