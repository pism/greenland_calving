import os.path


if 'UAFGI_ROOT' in os.environ:
    UAFGI_ROOT = os.environ['UAFGI_ROOT']
else:
    UAFGI_ROOT = 'data'
#UAFGI_ROOT = os.environ['UAFGI_ROOT']

# Convenience function
def join(*path):
    return os.path.join(UAFGI_ROOT, *path)
def join_outputs(*path):
    return os.path.join(OUTPUTS, *path)
# -------------------------------------------------------

# Root directories
DATA = UAFGI_ROOT
OUTPUTS = 'outputs'

# Core files
BEDMACHINE_ORIG = os.path.join(DATA, 'bedmachine/BedMachineGreenland-2017-09-20.nc')
BEDMACHINE_PISM = os.path.join(OUTPUTS, 'bedmachine/BedMachineGreenland-2017-09-20_pism.nc')

def measures_grid_file(ns481_grid):
    """File describing an NSIDC-0481 (MEASURES) grid."""
    return os.path.join(DATA, 'measures/grids/{}_grid.nc'.format(ns481_grid))

def bedmachine_local(grid):
    """BedMachine file localized for a NSIDC 0481 (MEASURES) grid"""
    return os.path.join(
        OUTPUTS, 'bedmachine/BedMachineGreenland-2017-09-20_{}.nc'.format(grid))

def gimpdem_local(grid):
    """Gimpdem file localized for a NSIDC 0481 (MEASURES) grid"""
    return os.path.join(
        OUTPUTS, 'gimpdem-nsidc0645/gimpdem_v01.1_{}.nc'.format(grid))

# -------------------------------------------------------
