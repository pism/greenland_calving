import collections
import os

# Root folder on our Google Drive archive
GDRIVE_DATA0 = '1E4vpeHYGpQqXu5pykTKIOekMfFlSxxvA'
GREENLAND_CALVING = '.'
DATA = 'data'
Rule = collections.namedtuple('Rule', ('inputs', 'outputs', 'action'))

class Makefile:
    def __init__(self):
        self.targets = list()
        self.rules = list()
    def add(self, rule):
        self.targets += rule.outputs
        self.rules.append(rule)

makefile = Makefile()

# -----------------------------------------------------------
# Bedmachine
# BedMachine v3 file no longer available
# See here on Google Drive:
#   https://drive.google.com/drive/u/1/folders/158Iv-bxrKuJ3BmkGa3bGvAVC-cYrcxD_
makefile.add(Rule(
    [], [os.path.join(DATA, 'bedmachine', 'BedMachineGreenland-2017-09-20.nc')],
    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy alaska:bedmachine/BedMachineGreenland-2017-09-20.nc {DATA}/bedmachine']))

# -----------------------------------------------------------
# ITS-LIVE
# https://nsidc.org/apps/itslive/
for year in range(1985,2019):
    leaf = f'GRE_G0240_{year:04d}.nc'
    makefile.add(Rule(
        [], [os.path.join(DATA, 'itslive', leaf],
        [f'curl -L https://its-live-data.s3.amazonaws.com/velocity_mosaic/landsat/v00.0/annual/{leaf} -o {leaf}'])))

# -----------------------------------------------------------
# Slater 2019
# SLATER Donald <donald.slater@ed.ac.uk>
# Dec 7, 2021, 1:12 AM
# Dear Elizabeth,
# That’s great that you’re looking to improve the glacier regression. Here is the glacier-by-glacier data (L, Q, TF etc):
#   https://github.com/ismip/ismip6-gris-ocean-processing/blob/master/glaciers/glaciers.mat
# I’ve also attached code to make Figs. 4-7 of the paper (run “makeplots(i)” where i is the figure number).
# Let me know if you have any difficulty using the data or code, or if anything else would be helpful.
ofname = os.path.join(DATA, 'slater2019', glaciers.mat)
makefile.add(Rule(
    [], [ofname],
    [f'curl -L https://github.com/ismip/ismip6-gris-ocean-processing/raw/499fb53c36c29c82283658eb8b5c5fe5e5a548d1/glaciers/glaciers.mat -o {ofname}']))

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
    [f'cd odir; python {GREENLAND_CALVING}/download_nsidc0481_grids.py',
    f'cd odir; rm TSX_*.tif']))


# -----------------------------------------------------------
# Wood et al 2021
# The file aba7282_table_s1.xlsx may be downloaded MANUALLY from:
#    https://www.science.org/doi/10.1126/sciadv.aba7282
makefile.add(Rule(
    [], [os.path.join(DATA, 'wood2021', 'aba7282_table_s1.xlsx')],
    [f'rclone --verbose --drive-root-folder-id={GDRIVE_DATA0} copy alaska:wood2021/aba7282_table_s1.xlsx {DATA}/wood2021']))

