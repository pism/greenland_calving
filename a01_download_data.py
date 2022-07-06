import itertools
import subprocess
import collections
import os

# Root folder on our Google Drive archive
GDRIVE_DATA0 = '1E4vpeHYGpQqXu5pykTKIOekMfFlSxxvA'
GREENLAND_CALVING = os.path.abspath('.')
DATA = os.path.abspath('data')
Rule = collections.namedtuple('Rule', ('inputs', 'outputs', 'action'))

class Makefile:
    def __init__(self):
        self.targets = list()
        self.rules = list()
    def add(self, rule):
        self.targets += rule.outputs
        self.rules.append(rule)

    def generate(self, ofname):
        with open(ofname, 'w') as out:
            out.write('all: {}\n\n'.format(' '.join(self.targets)))

            for rule in self.rules:
                out.write('{} : | {}\n'.format(' '.join(rule.outputs), ' '.join(rule.inputs)))
                # Create output directories for all created files
                odirs = {os.path.split(output)[0] for output in rule.outputs}
                for odir in odirs:
                    out.write('\tmkdir -p {}\n'.format(odir))

                # Run the actual actions
                for line in rule.action:
                    out.write('\t{}\n'.format(line))

                out.write('\n')

makefile = Makefile()

# -----------------------------------------------------------
def shapefiles(fname):
    return [fname+suffix for suffix in ('.shx','.shp','.qpj','.prj','.dbf')]
def shapefiles2(fname):
    return [fname+suffix for suffix in ('.cpg', '.dbf','.prj','.shp', '.shx')]


## Data Generated in this Study: Join Overrides Table
#odir = os.path.join(DATA, 'stability_overrides')
#leaves = ['overrides.ods', 'sl19_match.ods'] + shapefiles('terminus_locations')
#makefile.add(Rule(
#    [], [os.path.join(odir,leaf) for leaf in leaves],
#    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy greenland_calving:/stability_overrides/ {odir}']))

## Data Generated in this Study: Fjord Outlines
#odir = os.path.join(DATA, 'fj')
#leaves = ['README.txt'] + shapefiles('fjord_outlines')
#makefile.add(Rule(
#    [], [os.path.join(odir,leaf) for leaf in leaves],
#    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy greenland_calving:/fj/ {odir}']))

## Data Generated in this Study: Upstream Point for each glacier
#odir = os.path.join(DATA, 'upstream')
#leaves = ['README.txt'] + shapefiles('upstream_points')
#makefile.add(Rule(
#    [], [os.path.join(odir,leaf) for leaf in leaves],
#    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy greenland_calving:/upstream/ {odir}']))


# -----------------------------------------------------------
# Wood et al 2021
# The file aba7282_Table_S1.xlsx may be downloaded MANUALLY from:
#    https://www.science.org/doi/10.1126/sciadv.aba7282
# "The ice fronts digitized in this study and all derived time series from each glacier are available at doi.org/10.7280/D1667W".  This also requires a MANUAL download.
odir = os.path.join(DATA, 'wood2021')
leaves = ['aba7282_Table_S1.xlsx', 'doi_10.7280_D1667W__v6-3.zip']
makefile.add(Rule(
    [], [os.path.join(odir,leaf) for leaf in leaves],
    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy greenland_calving:/wood2021/ {odir}',
    f'python download_scripts/unzip_wood2021.py']))

# Extract / preprocess Wood et al 2021 data
makefile.add(Rule(
    [os.path.join(odir, 'doi_10.7280_D1667W__v6-3.zip')],
    [os.path.join(odir, 'data', 'index.df')],
    ['python download_scripts/unzip_wood2021.py']))

leaves = ['CE','CW','N','NE','NW','SE','SW']
makefile.add(Rule(
    [os.path.join(odir, 'aba7282_Table_S1.xlsx')],
    [os.path.join(odir, f'{leaf}.csv') for leaf in leaves],
    ['python download_scripts/convert_wood2021_to_csv.py']))


# -----------------------------------------------------------
# Slater 2019
# SLATER Donald <donald.slater@ed.ac.uk>
# Dec 7, 2021, 1:12 AM
# Dear Elizabeth,
# That’s great that you’re looking to improve the glacier regression. Here is the glacier-by-glacier data (L, Q, TF etc):
#   https://github.com/ismip/ismip6-gris-ocean-processing/blob/master/glaciers/glaciers.mat
# I’ve also attached code to make Figs. 4-7 of the paper (run “makeplots(i)” where i is the figure number).
# Let me know if you have any difficulty using the data or code, or if anything else would be helpful.
ofname = os.path.join(DATA, 'slater2019', 'glaciers.mat')
makefile.add(Rule(
    [], [ofname],
    [f'curl -L https://github.com/ismip/ismip6-gris-ocean-processing/raw/499fb53c36c29c82283658eb8b5c5fe5e5a548d1/glaciers/glaciers.mat -o {ofname}']))

# -----------------------------------------------------------
# NSIDC-0642 Termini
#

odir = os.path.join(DATA, 'measures-nsidc0642')

roots = ['termini_0001_v01.2', 'termini_0506_v01.2', 'termini_0607_v01.2', 'termini_0708_v01.2', 'termini_0809_v01.2', 'termini_1213_v01.2', 'termini_1415_v01.2', 'termini_1516_v01.2', 'termini_1617_v01.2']

leaves = list(itertools.chain.from_iterable(
    [shapefiles2(f'{root}') for root in roots]))
makefile.add(Rule(
    [], [os.path.join(odir,leaf) for leaf in leaves],
    [f'cd {odir};python {GREENLAND_CALVING}/download_scripts/nsidc-download_NSIDC-0642.001_2021-02-27.py']))



# -----------------------------------------------------------
# MeASURES Grids
# download_nsidc0481_grids.py is a modified version of an NSIDC-supplied script.
# This process requires a ~/.netrc file (see README.md)

odir = os.path.join(DATA, 'measures-nsidc0481', 'grids')
outputs = [os.path.join(odir, x) for x in (
    'E61.10N_grid.nc', 'E61.70N_grid.nc', 'E62.10N_grid.nc', 'E62.55N_grid.nc', 'E63.00N_grid.nc',
    'E63.35N_grid.nc', 'E63.85N_grid.nc', 'E64.35N_grid.nc', 'E64.65N_grid.nc', 'E65.10N_grid.nc',
    'E65.55N_grid.nc', 'E66.50N_grid.nc', 'E66.60N_grid.nc', 'E66.90N_grid.nc', 'E67.55N_grid.nc',
    'E68.50N_grid.nc', 'E68.80N_grid.nc', 'E71.75N_grid.nc', 'E78.90N_grid.nc', 'E79.40N_grid.nc',
    'E81.35N_grid.nc', 'E81.45N_grid.nc', 'W61.70N_grid.nc', 'W62.10N_grid.nc', 'W64.25N_grid.nc',
    'W64.75N_grid.nc', 'W67.05N_grid.nc', 'W68.60N_grid.nc', 'W69.10N_grid.nc', 'W69.95N_grid.nc',
    'W70.55N_grid.nc', 'W70.90N_grid.nc', 'W71.65N_grid.nc', 'W72.00N_grid.nc', 'W72.90N_grid.nc',
    'W73.45N_grid.nc', 'W73.75N_grid.nc', 'W74.50N_grid.nc', 'W74.95N_grid.nc', 'W75.50N_grid.nc',
    'W75.85N_grid.nc', 'W76.10N_grid.nc', 'W76.25N_grid.nc', 'W76.35N_grid.nc', 'W76.40N_grid.nc',
    'W76.45N_grid.nc', 'W77.55N_grid.nc', 'W79.75N_grid.nc', 'W80.75N_grid.nc', 'W81.25N_grid.nc',
    'W81.50N_grid.nc')]
makefile.add(Rule(
    [], outputs,
    [f'cd {odir}; python {GREENLAND_CALVING}/download_scripts/download_nsidc0481_grids.py']))
#    f'rm {odir}/TSX_*.tif']))


# -----------------------------------------------------------
# ITS-LIVE
# https://nsidc.org/apps/itslive/
odir = os.path.join(DATA, 'itslive')
for year in range(1985,2019):
    leaf = f'GRE_G0240_{year:04d}.nc'
    makefile.add(Rule(
        [], [os.path.join(odir, leaf)],
        [f'curl -L https://its-live-data.s3.amazonaws.com/velocity_mosaic/landsat/v00.0/annual/{leaf} -o {odir}/{leaf}.t1',
        f'mv {odir}/{leaf}.t1 {odir}/{leaf}']))


# -----------------------------------------------------------
# Bedmachine
# BedMachine v3 file no longer available
# See here on Google Drive:
#   https://drive.google.com/drive/u/1/folders/158Iv-bxrKuJ3BmkGa3bGvAVC-cYrcxD_
makefile.add(Rule(
    [], [os.path.join(DATA, 'bedmachine', 'BedMachineGreenland-2017-09-20.nc')],
    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy greenland_calving:/bedmachine/BedMachineGreenland-2017-09-20.nc {DATA}/bedmachine']))

# -----------------------------------------------------------
# Bjørk et al, 2015
# "Brief communication: Getting Greenland’s glaciers right – a new data set of all official Greenlandic glacier names"
# https://doi.org/10.5194/tc-9-2215-2015
odir = os.path.join(DATA, 'bkm15')
leaves = ['tc-9-2215-2015-supplement.zip', 'tc-9-2215-2015.pdf']
makefile.add(Rule(
    [], [os.path.join(odir,leaf) for leaf in leaves],
    [f'curl -L https://tc.copernicus.org/articles/9/2215/2015/{leaf} -o {odir}/{leaf}' for leaf in leaves]))

makefile.add(Rule(
    [os.path.join(odir, 'tc-9-2215-2015-supplement.zip')],
    [os.path.join(odir, 'tc-9-2215-2015-supplement.csv')],
    [f'cd {odir}; unzip tc-9-2215-2015-supplement.zip',
    # This second step might not be needed; it looks like it's essentialy the same as an
    # existing CSV file that comes with the supplement.
    f'cd {odir}; ogr2ogr -f CSV tc-9-2215-2015-supplement.csv GreenlandGlacierNames_GGNv01_WGS84.shp']))

# -------------------------------------------------------------------
# CALFIN Termini Dataset, 2020
# https://doi.org/10.7280/D1FH5D

calfins = [
    'Akullersuup-Sermia', 'Akullikassaap-Sermia', 'Alanngorliup-Sermia',
    'Alanngorsuup-Sermia', 'Alianaatsup-Sermia', 'Alison-Gletsjer',
    'Bruckner-Gletscher', 'Christian-IV-Gletsjer',
    'Cornell-Gletsjer', 'Courtauld-Gletsjer', 'Dietrichson-Gletsjer',
    'Docker-Smith-Gletsjer', 'Eqip-Sermia',
    'Fenris-Gletsjer', 'Frederiksborg-Gletsjer',
    'Gade-Gletsjer', 'Glacier-de-France', 'Hayes-Gletsjer',
    'Heim-Gletscher', 'Helheim-Gletsjer',
    'Hutchinson-Gletsjer', 'Illullip-Sermia',
    'Inngia-Isbrae', 'Jakobshavn-Isbrae', 'Kaelvegletsjer',
    'Kakivfait-Sermia', 'Kangerluarsuup-Sermia',
    'Kangerlussuaq-Gletsjer', 'Kangerlussuup-Sermia',
    'Kangiata-Nunaata-Sermia', 'Kangilernata-Sermia',
    'Kangilinnguata-Sermia', 'Kangilleq-Kangigdleq-Isbrae',
    'Kjer-Gletsjer', 'Kong-Oscar-Gletsjer',
    'Kronborg-Gletsjer', 'Lille-Gletsjer',
    'Midgard-Gletsjer', 'Morell-Gletsjer',
    'Naajarsuit-Sermiat', 'Nansen-Gletsjer',
    'Narsap-Sermia', 'Nordenskiold-Gletsjer',
    'Nordfjord-Gletsjer', 'Nordre-Parallelgletsjer',
    'Peary-Gletscher', 'Perlerfiup-Sermia',
    'Petermann-Gletsjer', 'Polaric-Gletsjer',
    'Qeqertarsuup-Sermia', 'Rink-Gletsjer', 'Rink-Isbrae',
    'Rosenborg-Gletsjer', 'Saqqarliup-Sermia',
    'Sermeq-Avannarleq-69N', 'Sermeq-Avannarleq-70N',
    'Sermeq-Silarleq', 'Sermilik-Isbrae',
    'Sondre-Parallelgletsjer', 'Sorgenfri-Gletsjer',
    'Steenstrup-Gletsjer', 'Store-Gletsjer',
    'Styrtegletscher', 'Sverdrup-Gletsjer',
    'Umiammakku-Sermiat', 'Upernavik-Isstrom-N-C',
    'Upernavik-Isstrom-NW', 'Upernavik-Isstrom-S',
    'Ussing-Braer-N', 'Ussing-Braer']

odir = os.path.join(DATA, 'calfin')
for id,folder,suffix,zipleaf in [
    ('458631', 'domain-termini', '_v1.0', 'level-1_shapefiles-domain-termini.zip'),
    ('458632', 'domain-termini-closed', '_closed_v1.0', 'level-1_shapefiles-domain-termini-closed.zip')]:
    zip_fname = os.path.join(odir,zipleaf)
    makefile.add(Rule(
        [], [zip_fname],
        [f'cd {odir}; curl -L https://datadryad.org/stash/downloads/file_stream/{id} -o {zipleaf}']))
    leaves = list(itertools.chain.from_iterable(
        [shapefiles2(f'termini_1972-2019_{calfin}{suffix}') for calfin in calfins]))
    subdir = os.path.join(odir,folder)
    makefile.add(Rule(
        [zip_fname], [os.path.join(subdir,leaf) for leaf in leaves],
        [f'cd {subdir}; unzip {odir}/{zipleaf}']))

# --------------------------------------------------
mkf = 'a01_download_data.mk'
makefile.generate(mkf)
cmd = ['make', '-f', mkf]
subprocess.run(cmd)

