#!/usr/bin/env python

import PISM

ctx = PISM.Context()

class Calving(object):
    """Computes and applies the calving rate to produce the new ice extent after a given
    period of time (seconds).

    The computation is performed on the grid defined in velocity_input_file.
    """

    def __init__(self, velocity_input_file):
        self.velocity_input_file = velocity_input_file

        self.min_thickness = ctx.config.get_number("geometry.ice_free_thickness_standard")

        self.grid = PISM.IceGrid.FromFile(ctx.ctx, velocity_input_file,
                                          ["u_ssa_bc"], PISM.CELL_CENTER)

        # allocate the flow law
        flow_law_factory = PISM.FlowLawFactory("calving.vonmises_calving.",
                                               ctx.config, ctx.enthalpy_converter)
        flow_law_factory.set_default("isothermal_glen")
        flow_law = flow_law_factory.create()

        self.bc_mask = PISM.IceModelVec2Int(self.grid, "bc_mask", PISM.WITH_GHOSTS)
        self.bc_mask.set(0.0)

        self.retreat_rate = PISM.IceModelVec2S(self.grid, "total_retreat_rate", PISM.WITHOUT_GHOSTS)
        self.retreat_rate.set(0.0)

        self.melt_rate = PISM.IceModelVec2S(self.grid, "frontal_melt_rate", PISM.WITHOUT_GHOSTS)
        self.melt_rate.set(0.0)

        # allocate and initialize the calving model
        self.model = PISM.CalvingvonMisesCalving(self.grid, flow_law)
        self.model.init()

        self.front_retreat = PISM.FrontRetreat(self.grid)

        # allocate storage for ice enthalpy
        self.ice_enthalpy = PISM.IceModelVec3(self.grid, "enthalpy", PISM.WITH_GHOSTS, 2)
        self.ice_enthalpy.set(0.0)

        # allocate storage for ice velocity
        self.ice_velocity = PISM.IceModelVec2V(self.grid, "_ssa_bc", PISM.WITH_GHOSTS, 2)
        # These two calls set internal and "human-friendly" units. Data read from a file will be
        # converted into internal units.
        self.ice_velocity.set_attrs("input", "x-component of ice velocity", "m / s", "m / year", "", 0)
        self.ice_velocity.set_attrs("input", "y-component of ice velocity", "m / s", "m / year", "", 1)


        # allocate storage for all geometry-related fields. This does more than we need (but it's
        # easy).
        self.geometry = PISM.Geometry(self.grid)


    def run(self, velocity_record_index, t_final, geometry_input_file, output_file):
        """Run the calving model and update the calving front location to capture the effect of
        calving after t_final seconds.

        Ice geometry is read from geometry_input_file. Results are written to output_file.

        Uses the record velocity_record_index from self.velocity_input_file for this computation.

        """
        self.ice_velocity.read(self.velocity_input_file, velocity_record_index)

        geometry = self.geometry

        # read the last record of ice thickness and bed elevation using bilinear interpolation
        geometry.ice_thickness.regrid(geometry_input_file, critical=True)
        geometry.bed_elevation.regrid(geometry_input_file, critical=True)
        geometry.sea_level_elevation.set(0.0)

        # ensure consistency of geometry (computes surface elevation and cell type)
        geometry.ensure_consistency(self.min_thickness)

        output = PISM.util.prepare_output(output_file, append_time=False)
        PISM.append_time(output, "time", 0)
        # save initial ice thickness
        geometry.ice_thickness.write(output)

        t = 0
        while t < t_final:

            # compute the calving rate
            self.model.update(geometry.cell_type, geometry.ice_thickness, self.ice_velocity, self.ice_enthalpy)

            # combine calving rate with the frontal melt rate to produce the total retreat rate
            self.retreat_rate.copy_from(self.model.calving_rate())
            self.retreat_rate.add(1.0, self.melt_rate)

            # compute the maximum allowed time step length
            dt = self.front_retreat.max_timestep(geometry.cell_type, self.bc_mask, self.retreat_rate).value()
            dt = min(dt, t_final - t)

            self.front_retreat.update_geometry(dt, geometry, self.bc_mask, self.retreat_rate,
                                               geometry.ice_area_specific_volume,
                                               geometry.ice_thickness)
            geometry.ensure_consistency(self.min_thickness)

            t += dt

            # save results
            PISM.append_time(output, "time", t)
            self.model.calving_rate().write(output)
            geometry.ice_thickness.write(output)

        output.close()

if __name__ == "__main__":

    # reduce sigma_max to make this test more interesting
    ctx.config.set_number("calving.vonmises_calving.sigma_max", 1e2)

    C = Calving("Ross_combined.nc")

    # compute the ice extent after 1 year
    t_final = 1 * 12 * 30 * 86400
    velocity_index = 0
    C.run(velocity_index, t_final, "Ross_combined.nc", "new_geometry.nc")
