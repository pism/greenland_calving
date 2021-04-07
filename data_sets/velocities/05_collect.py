import re
import os
import numpy as np
import pandas as pd
import netCDF4
from uafgi import glacier,make
import uafgi.data

re0 = re.compile('(\d\d\d)_(.*)')
re1 = re.compile('stab_(\d\d\d)_(\d\d\d\d)_(\d+)_(.*)')
def stab_files():
    """List available files from experiment.
    Screens them by name, to avoid including extraneous files.
    Lists them on per-glacier (directory) basis."""

    # Find per-glacier subdirectories
    subdirs = list()
    ddir0 = uafgi.data.join_outputs('stability')
    for name0 in os.listdir(ddir0):

        # Determine ID info
        match = re0.match(name0)
        if match is None:
            continue
        glacier_id = int(match.group(1))
        glacer_name = match.group(2)

        # Only look at directories
        ddir1 = os.path.join(ddir0, name0)
        if not os.path.isdir(ddir1):
            continue

        # Look inside glacier dir
        leaves = list()
        for name1 in os.listdir(ddir1):
            match = re1.match(name1)
            if match is None:
                continue
            leaves.append(name1)

        # Yield all files on a per-dir basis
        if len(leaves) > 0:
            yield ddir1,leaves



def _read_file(ifname):
    import netCDF4
    import numpy as np
    from uafgi import glacier
    _rf_exclude = {'history', 'NCO', 'creator'}

    print('Reading {}'.format(ifname))
    row = dict()
    with netCDF4.Dataset(ifname) as nc:

        # Read existing attributes (except for _rf_exclude)
        for aname in nc.ncattrs():
            if aname not in _rf_exclude:
                row[aname] = nc.getncattr(aname)

        # Get grid spacing dy,dx
        yy = nc.variables['y'][:]
        dy = yy[1] - yy[0]
        xx = nc.variables['x'][:]
        dx = xx[1] - xx[0]

        # Identify original fjord
        fjc = nc.variables['fjord_classes'][:].data
        fjord = np.isin(fjc, glacier.ALL_FJORD)

        # Compute upstream fjord ice area for first and last
        time_d = nc.dimensions['time']
        stab_ice = list()
        for itime in (0,len(time_d)-1):
            thk = nc.variables['thk'][itime,:]
            up_ice = dy * dx * np.sum(np.logical_and(fjord, thk>0))
            stab_ice.append(up_ice)
        row['stab_ice_extent0'] = stab_ice[0]
        row['stab_ice_extent1'] = stab_ice[1]

    return row

def collect_dir_rule(ddir, names):
    """Creates a single dataframe per directory.
    ddir:
        The directory
    names:
        Leaf names of files in ddir to process.
    """

    force_fname = os.path.join(ddir, os.path.split(ddir)[1] + '.force')
    df_fname = os.path.join(ddir, os.path.split(ddir)[1] + '.df')
    csv_fname = os.path.join(ddir, os.path.split(ddir)[1] + '.csv')
    read_file = _read_file    # Import into thunk namespace

    def action(tdir):
        import os
        import pandas as pd

        rows = list()
        index = list()

        # Use existing dataframe to keep already-computed rows
        if os.path.exists(df_fname):
            df0 = pd.read_pickle(df_fname)
            df0_tm = os.path.getmtime(df_fname)
        else:
            df0 = None

        # Filter out already-processed files
        nread = 0
        for name in sorted(names):

            if (df0 is None) or \
                (name not in df0.index) or \
                (os.path.getmtime(os.path.join(ddir, name)) > df0_tm):

                # File not yet processed or is stale: read it
                fname = os.path.join(ddir, name)
                rows.append(read_file(fname))
                index.append(name)

                nread += 1
#                if nread > 5:
#                    break
            else:
                # File already processed: use existing row
                row = df0.loc[name].to_dict()
                rows.append(row)
                index.append(name)


        # Convert back to dataframe
        df = pd.DataFrame(rows, index=index).sort_index()

        # Save back
        if nread > 0:
            pd.to_pickle(df, df_fname)
            df.to_csv(csv_fname)


        return df
    return make.Rule(action, [], [df_fname+'force', df_fname])

def merge_rule(df_fnames, ofname):

    def action(tdir):
        import pandas as pd

        dfs = list()
        for df_fname in df_fnames:
            dfs.append(pd.read_pickle(df_fname))
        df = pd.concat(dfs)
        df.to_pickle(ofname)


    return make.Rule(action, df_fnames, [ofname]) 

def main():
#    ofname = uafgi.data.join_outputs('stability', '05_collect.df')
#    row = read_file('outputs/stability/153_KangerlussuaqGl/stab_153_2015_016_KangerlussuaqGl.nc')

    makefile = make.Makefile()
    targets = list()

    ddirs = list()
    df_fnames = list()
    for dir,names in stab_files():
        ddirs.append(dir)

        print('=== dir: {}'.format(dir))
        rule = collect_dir_rule(dir, names)
        makefile.add(rule)
        targets.append(rule.outputs[0])
        df_fnames.append(rule.outputs[1])


    ofname = uafgi.data.join_outputs('stability', 'stability.df')
    rule = merge_rule(df_fnames, ofname)
    targets.append(rule.outputs[0])
    makefile.add(rule)

    makefile.generate(targets, '05_collect.mk')



main()
