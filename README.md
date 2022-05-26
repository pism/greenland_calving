# Analysis Code for Calving Paper

Quantitative Assessment of Stabilizing or Destabilizing Effect of Fjord Geometry on Greenland Tidewater Glaciers, *Elizabeth Fischer, Andy Aschwanden*, *May, 2022*

This work also depends on Python code in the UAFGI library: https://github.com/pism/uafgi/

# Setting Up Environment

## Python Environment

1. Install Miniconda

2. Install `greenland_calving.yaml` environment.


## NSIDC Earthdata Account

1. If you don't have one already, sign up for an Earthdata account at NSIDC:
   https://urs.earthdata.nasa.gov/users/new

2. Create a `~/.netrc` file with your username and password, for programmatic access:
   ```
   echo 'machine urs.earthdata.nasa.gov login <uid> password <password>' >> ~/.netrc
   chmod 0600 ~/.netrc
   ```

https://nsidc.org/support/how/v0-programmatic-data-access-guide




# Datasets

## G

## `bedmachine/`

The file `BedMachineGreenland-2017-09-20.nc` (BedMachine v3) is no longer available for download.  Copied from `data0/`.

## 


## Download Datasets

```
mkdir outputs
```


