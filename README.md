Greenland Calving Paper
=======================

Elizabeth Fischer  
June, 2022

The GitHub repo for this file contains the code used for he study described in the paper: Fischer, E, Aschwanden, A, *Quantitative Assessment of Stabilizing or Destabilizing Effect of Fjord Geometry on Greenland Tidewater Glaciers*.  The contents of this repo, along with additional data files, is bundled up as supplements to the paper.


Supplements for Greenland Calving Paper
=======================================


The paper comes with four supplement files, allowing users to obtain full results of the experiment described in the paper, inspect the code used to produce those results, re-run the graphs, or even replicate the entire experiment.  They are mean to be unzipped into the same top-level directory.

This document describes the nature and contents of each of the four files.  


1_greenland_calving_results.zip
-------------------------------

Contains the full results of the experiment described in the paper, including a single-page "rap sheet" summarizing each glacier studied.  Does not contain the code or data used to generate those results.

outputs/stability/greenland_calving.csv
```````````````````````````````````````

The "master table" of the study, including input datasets and results.  The study relied on data from multiple previous studies, and this table provides the key to corresponding glaciers between studies.  For example, the terminus data provided by Wood et al (2021) in the file `AP Bernstorff Data.nc` corresponds to the glacier called `A.P. Bernstorf Gl.` or glacier number 62 in the Wood et al (2021) supplement spreadsheet.  It is also the same as the glacier `GGN0089` in Bjørk, Kruse, Michaelsen (2015) and Glacier number 190 of NSIDC Dataset 642.  Each dataset is encoded as a column name prefix:

1. **[bkm15]:** Bjørk, A. A., Kruse, L. M., & Michaelsen, P. B. (2015). Brief communication: Getting Greenland's glaciers right–a new data set of all official Greenlandic glacier names. *The Cryosphere, 9*(6), 2215-2218.

   * **bkm15_id:** Alphanumeric ID assigned to each glacier by the source paper.  Additional columns from **[bkm15]** may be obtained by joining with original data.


1. **[cf20]:** Cheng, D., Hayes, W., Larour, E., Mohajerani, Y., Wood, M., Velicogna, I., & Rignot, E. (2021). *Calving Front Machine (CALFIN): glacial termini dataset and automated deep learning extraction method for Greenland, 1972–2019.* The Cryosphere, 15(3), 1663-1675.

   * **cf20_key:** Alphabetic name of each glacier, used in filenames of the CALFIN dataset.

   * **cf20_glacier_id:** The `GlacierID` column found inside each shapefile.


1. **[ns481]:** NSIDC Dataset 0481, described by: Joughin, I., I. Howat, B. Smith, and T. Scambos. 2021.  *MEaSUREs Greenland Ice Velocity: Selected Glacier Site Velocity Maps from InSAR, Version 4.* Boulder, Colorado USA. NASA National Snow and Ice Data Center Distributed Active Archive Center. doi: https://doi.org/10.5067/GQZQY2M5507Z.

   * **ns481_grid:** The identifier for each grid used in the MEaSUREs Greenland Ice Velocity dataset.  For example, `W71.65N` describes the grid found on the West coast of Greenland at 71.65 degrees North.


1. **[ns642]:** NSIDC Dataset 0642, described by: Joughin, I., T. Moon, J. Joughin, and T. Black. 2021. MEaSUREs Annual Greenland Outlet Glacier Terminus Positions from SAR Mosaics, Version 2. Boulder, Colorado USA. NASA National Snow and Ice Data Center Distributed Active Archive Center. doi: https://doi.org/10.5067/ESFWE11AVFKW.

   * **ns642_GlacierID**: Numerical identifier used for each glacier in the referenced paper's dataset of annual terminus positions.


1. **[sl19]:** Slater, D. A., Straneo, F., Felikson, D., Little, C. M., Goelzer, H., Fettweis, X., & Holte, J. (2019). *Estimating Greenland tidewater glacier retreat driven by submarine melting. The Cryosphere, 13(9), 2489-2509.*

   * **sl19_rignotid:** The column called `rignotid` from the `glaciers.mat` file provided with the referenced paper.  Additional columns from **[sl19]** may be obtained by joining with original data.

   * **sl19_key:** Same as **sl19_rignotid**.

   * **sl19_bjorkid:** The `bjorkid` from the `glaciers.mat` file provided with the referenced paper.  Should correspond to the column **bkm15_id** described above.


1. **[w21] and [w21t]:** Wood, M., Rignot, E., Fenty, I., An, L., Bjørk, A., van den Broeke, M., ... & Zhang, H. (2021). Ocean forcing drives glacier retreat in Greenland. *Science advances,* 7(1), eaba7282.


   * **w21_key:** A combination of two fields from the data provided with the referenced paper that, together, uniquely identify each glacier.  Additional columns from **[w21]** may be obtained by joining with original data.

   * **w21t_Glacier:** Alphabetic name of each glacier, used in filenames of terminus positions provided with the referenced paper.  For example, the file `Ussing Braeer Data.nc` contains data for the glacier with `w21t_Glacier == 'Ussing Braeer Data'`.

   * **w21t_glacier_number:** Numeric ID assigned to each glacer in the referenced paper, and used in some parts of the dataset.

   * **w21t_lon, w21t_lat:** Single longitude / latitude point representing the terminus, based on an average of the terminus locations over time, as provided by the referenced paper.


The following datasets were created for the purpose of this study and are included in the download `2_greenland_calving_data.zip`:

1. **[fj]:** Polygons hand-drawn around fjords for the purpose of this study.

   * **fj_fid:** Numeric identifier for each polygon inside the source shapefile.  (Fjords are matched to glaciers through spatial analysis, not matching IDs).  The full polygon may be obtained by joining with the original data.

1. **[up]:** One hand-picked point in the upper regions of each fjord, for the purpose of this study.

   * **fj_fid:** Numeric identifier for each point inside the source shapefile.  (Points are matched to glaciers through spatial analysis, not matching IDs).

   * **(up_lon, up_lat):** Longitude/latitude location of each point.


The following column name prefixes describe three regressions used for the results of this study.  Each regression run by the Python function `scipy.stats.linregress` produces columns `slope`, `intercept`, `rvalue`, p`value` and `stderr`, which are descbed at: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html

* **[tp]:** Regression between terminus positions of **[sl19]** vs up-areas derived from data in **[w21t]**, as described in this study.

* **[sl]:** Repeat of the regressions from **[sl19]**, as described in this study.

* **[rs]:** Regression of terminus reiduals vs sigma, as described in this study.

outputs/velterm/velterm.csv
``````````````````````````

The raw results of integrating each terminus/velocity pair, as described in the study.  Columns are:

* **vel_year:** Date of the ITS-LIVE velocity field used, as decimal year.  (eg. 1985.5 is halfway through the year 1985).

* **future_index:** Set only if the terminus was a "hypothetical" hand-drawn terminus.  Such termini were not used in the end.

* **term_year:** Date of the Wood et al (2021) terminus used, as decimal year.

* **terminus:** Not used, blank.

* **aflux:** The denominator of Eq. 7 of this study (computing sigma_T).

* **sflux:** The numerator of Eq. 7 of this study (computing sigma_T).

* **ncells:** The number of gridcells with data, used in computing `aflux` and `sflux`.

* **up_area:** The up-area, as defined in this study, for the given terminus.

* **fluxratio:** sigma_T, as defined by Eq. 7.  Equal to `sflux / aflux`.

* **glacier_id:** The `w21t_glacier_number` identifying the glacier for this terminus / velocity combination.


outputs/rapsheets_*.pdf
'''''''''''''''''''''''

A "rap sheet" summarizing the results of the experiment on each glacier.  Rap sheets are organized into thee cateogires, as described in this study.  The same rainbow color scale is used to plot points and terminus lines for all plots except the first on each page.

* **rapsheets_destabilize.pdf:** Glaciers for which the fjord geometry was found to be destabilizing.

* **rapsheets_stabilize.pdf:** Glaciers for which the fjord geometry was found to be stabilizing.

* **raphseets_insignificant.pdf:** Glaciers for which there was not statistical significance.



2_greenland_calving_data.zip
----------------------------

These files are used to aid in spatial analysis, as described in the study.

* `data/upstream/upstream_points.shp`: Shapefile providing the hand-picked point for each fjord.

* `data/fj/fjord_outlines.shp`: Shapefile providing the hand-drawn polygon around each fjord.

These files are used to diambiguate when joining disparate datasets.  Automated methods are used for most joins; and entries are made in this file only when the automated methods need "help."  Spreadsheets here are in ODF office document format, see: https://www.oasis-open.org/committees/tc_home.php?wg_abbrev=office.  For more on how these files are used, see `_read_overrides()` in `uafgi/uafgi/data/stability.py` (part of download `3_greenland_calving_code.zip`).

* **data/stability_overrides/overrides.ods:** Master overrides table, in Open Document Spreadsheet (ODF) format.  Columns are described above; ignore `include`.  

* **data/stability_overrides/bkm15_match.ods:** Relationship between w21 (Wood 2021) and bkm15 dataset, as determined by finding pairs (w,b) in which $w ]in w21$, $b \in bkm15$ and the terminus as reported in the datasets of w and b are close together.  The list was then manually culled to determine ACTUAL matches between glaciers of the two datasets.

* **data/stability_overrides/sl19_match.ods:** Relationship between w21 (Wood 2021) and sl19 dataset, as determined by finding pairs (w,s) in which $w ]in w21$, $s \in sl19$ and the terminus as reported in the datasets of w and b are close together.  The list was then manually culled to determine ACTUAL matches between glaciers of the two datasets.

* **`data/stability_overrides/terminus_location.shp`:** Shapefile providing a relationship between `w21_key`, `bkm15_key` and hand-picked point close to the glacier's terminus.  Used to disambiguate some glaciers.


3_greenland_calving_code.zip
--------------

This is a snapshot of the GitHub repositories:

 * **uafgi:** Library code.  See: https://github.com/pism/uafgi

 * **greenland_calving:** Top-level scripts for this study.  See: https://github.com/pism/greenland_calving

The exact git hashes used can be obtained by looking in the files named `GIT_INFO.txt` in the download.  This would allow one to replace `3_zip_code.zip` with two git clones instead, in case one wishes to modify the code.

The code was run using a Python 3.8 Conda environment on macOS 10.15.7 as described in the files `conda_env.yaml` and `conda_env_full.yaml`.  Reconstruction of a Conda environment is beyond the scope of this document, but is necessary to successfully run this code.

Top-level scripts are in the `greenland_calving` repo, and are organized by series and number.  In general, they are to be run in order, from the directory in which they reside, and without arguments.  They are as follows:

* **Series A:** Download and prepare external datasets.  

  * **a01_download_data.py:** Downloads all external datasets.  Required for plot generation.

  * **a02_select_glaciers.py:** Reconstructs the full master table for the experiment, including columns joined in from other datasets.  Not required because `outputs/stability/greenland_calving.csv` (above) already provides this functionality.  Not required for plot generation.

  * **a03_extract_select.py:** Pares down the result of **a02** to produce just the ID columns in `greenland_calving.csv`.  Not required for plot generation.

  * **a04_localize_bedmachine.py:** Extract BedMachine data for each NSIDC-481 grid.  Also includes commented-out code to localize the GimpDEM extracts (not currently used).  Required for plot generation.

  * **a05_localize_itslive.py:** Extract the ITS-LIVE velocity data for each NSIDC-481 grid.  Required for plot generation.


* **Series B:** Run the experiment.

  This runs the core computations involved in the experiments.  Code is provided "as-is," and has not been tested.

  * **b01_compute_sigma.py:** Runs PISM to compute a `sigma` value for each ITS-LIVE velocity map.  This script requires the additional installation of PISM to run; PISM commit `bdd81870272` of August 17, 2021 was used; see https://github.com/pism/pism/tree/bdd81870272a819806bfec7562b188b667ad0f88.  The results of this program may be downloaded via `4_greenland_calving_sigmas.zip`.

 * **b02_run_vel_term_combos.py:** Using `sigma` values computed in step `b01`, integrates each terminus across `sigma` of each velocity field, as described in the study.

 * **b03_export_velterm.py:** Combines the results of step **b02** to create a single file `outputs/velterm/velterm.csv`, which is included in the download `1_greenland_calving_results.zip`.



* **Series C:** Generate plots used for talk at AGU Fall Meeting, 2021.  See Series A for required data downloads.

  * **c01_plot_agu1.py**: Runs, and creates plots.


* **Series D:** Generate rap sheets and plots used for paper.  See Series A for required data downloads.

  * **d01_plot_rapsheets.py**: Generate the rap sheets.

  * **d02 -- d05:** Generate various plots used in the paper.

  * **d06_greenland_map.py:** Generate an index map of Greenland, showing location of all study glaciers.


4_greenland_calving_sigmas.zip
------------------------------

Provides the `sigma` fields derived from the ITS-LIVE velocities by running PISM (see step **b01_compute_sigma.py**).  This download is the largest; but can be used to re-run the experiment without having to re-install PISM.


