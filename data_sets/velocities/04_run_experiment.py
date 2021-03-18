


    def run_row(self, row):

        # Determine the local grid
        grid = row['ns481_grid']
        grid_file = datasets.measures_grid_file(grid)
        grid_info = gdalutil.FileInfo(grid_file)
        bedmachine_file = datasets.bedmachine_local(grid)

        # Load the fjord
        fjord = bedmachine.get_fjord(bedmachine_file, row['fj_poly'])

        # Obtain past terminus traces
        ns642_this = self.ns642_dict[row['ns642_GlacierID']]['ns642_terminus'].to_list()
        termini = ns642_this['ns642_terminus'].to_list()

        # Determine the most-retreated terminus
        def _up_termini():
            for terminus in termini:
                up_fjord = glacier.upstream_fjord(fjord, grid_info, up_loc, terminus)
                yield np.sum(np.sum(up_fjord)), terminus, up_fjord
        _, terminus, up_fjord = min(
            _up_termini(),
            key=lambda x: x[0])

        # Mask of downstream portions of the fjord
        down_fjord = np.logical_and(fjord, np.logical_not(up_fjord))

        # Get ice thickness, adjusted for the present grounding line
        bedmachine_file0 = uafgi.data.bedmachine_local(grid)
        with netCDF4.Dataset(bedmachine_file0) as nc:
            thickness = nc.variables['thickness'][:]
        thickness[down_fjord] = 0




        # Copy original local BedMachine file, with new ice terminus
        bedmachine_file1 = tdir.filename(suffix='.nc')
        bedmachine.replace_thk(bedmachine_file0, bedmachine_file1, thk)

        # Obtain start and end time in PISM units (seconds)
        dt0 = datetime.datetime(year,1,1)
        t0_s = fb.time_units_s.date2num(dt0)
        #dt1 = datetime.datetime(year+1,1,1)
        dt1 = datetime.datetime(year,4,1)
        t1_s = fb.time_units_s.date2num(dt1)
