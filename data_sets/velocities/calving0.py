#!/usr/bin/env python

"""This script reads in data from a file and runs PISM's von Mises calving model.
The calving rate is saved to "output.nc".
The calving model has the following inputs
- x and y components of the ice velocity
- "cell type" mask (used to locate the calving front)
The following three are used to compute the vertically-averaged ice hardness:
- ice thickness
- ice enthalpy
- the flow law
This script uses the isothermal flow law, so ice thickness is irrelevant but should be
positive in the ice-covered area. The enthalpy value does not matter.
"""

#### I need to mimic this: Ross_combined.nc plus the script that made it
# Script in the main PISM repo, it's in examples/ross/preprocess.py
#input_file = "~/github/pism/pism/examples/ross/Ross_combined.nc"
#input_file = "Ross_combined.nc"
velocity_file = 'outputs/TSX_W69.10N_2008_2020_pism_filled.nc'
bedmachine_file = 'outputs/BedMachineGreenland-2017-09-20_pism_W69.10N.nc'
import PISM
ctx = PISM.Context()
config = ctx.config

# This is a way to set the ice softness (and therefore hardness)
# We will have to make a decision about this, we are not modeling T profile of ice
# It makes sense to use an isothermal flow law: ice softness is a prescribed constant
# and hardness is related to softness.
config.set_number("flow_law.isothermal_Glen.ice_softness", 3.1689e-24)

# get grid information from the variable "thk" in a file.
# (Not a full-blown 3D grid, by getting from thk which is a 2D variable)
grid = PISM.IceGrid.FromFile(ctx.ctx, bedmachine_file, ["thickness"], PISM.CELL_CENTER)

# allocate storage for ice enthalpy
# Has to be there because model expects as part of input, but its content doesn't matter.
# It has a dummy vertical dimension with as few vertical levels as possible,
# it only has 2 levels.
ice_enthalpy = PISM.IceModelVec3(grid, "enthalpy", PISM.WITH_GHOSTS, 2)
ice_enthalpy.set(0.0)

# allocate storage for ice velocity
# 2V ===> Vectorfield, allocates 2 fields, stored interlaced in RAM, separately in files.
ice_velocity = PISM.IceModelVec2V(grid, "_ssa_bc", PISM.WITH_GHOSTS, 2)

# These two calls set internal and "human-friendly" units. Data read from a file will be
# converted into internal units.
# Ignore "input", long_name, internal_units, human_units, std_name, index into vector
ice_velocity.set_attrs("input", "x-component of ice velocity", "m / s", "m / year", "", 0)
ice_velocity.set_attrs("input", "y-component of ice velocity", "m / s", "m / year", "", 1)
ice_velocity.read(velocity_file, 0)   # 0 ==> first record of that file (if time-dependent)

# Geometry is a struct containing a bunch of these IceModelVec instances.
# It automatically pre-fills the constructor of Geometry, all the attributes.
# It's easier to just do that, rather than allocating the handful of them we may need.
# allocate storage for all geometry-related fields. This does more than we need (but it's
# easy).
geometry = PISM.Geometry(grid)

# read the first (0th) record of ice thickness and bed elevation
#geometry.ice_thickness.read(bedmachine_file, 0)
#geometry.bed_elevation.read(bedmachine_file, 0)
geometry.ice_thickness.regrid(bedmachine_file, critical=True)
geometry.bed_elevation.regrid(bedmachine_file, critical=True)
geometry.sea_level_elevation.set(0.0)

# Compute ice_free_thickness_standard based on what we just set above.
# We're grabbing ice_free_thickness_standard from our config database and
# using it to compute surface elevation and cell type.
# Generally, think of ice_free_thickness_standard == 0
# ensure consistency of geometry (computes surface elevation and cell type)
geometry.ensure_consistency(config.get_number("geometry.ice_free_thickness_standard"))

# allocate the flow law
flow_law_factory = PISM.FlowLawFactory("calving.vonmises_calving.",
                                       ctx.config, ctx.enthalpy_converter)
flow_law_factory.set_default("isothermal_glen")
flow_law = flow_law_factory.create()

# allocate and initialize the calving model
model = PISM.CalvingvonMisesCalving(grid, flow_law)
model.init()

# compute the calving rate
model.update(geometry.cell_type, geometry.ice_thickness, ice_velocity, ice_enthalpy)

# Writes just a scalar: movement of the front in horizontal direction, by how much (s-1)
# the front retreats.  Currently, how it's used in PISM, it's computed at ice-free locations
# immediately adjacent to the calving front.  That's where it would be applied by
# PISM's parameterization of sub-grid position of the calving front.
# save to an output file
output = PISM.util.prepare_output("output.nc")
model.calving_rate().write(output)
geometry.ice_thickness.write(output)    # One more thing to write
output.close()

# this is a way to access the calving rate in a Python script without saving to a file
# rate = model.calving_rate().numpy()

front_retreat = PISM.FrontRetreat(grid)

retreat_rate = PISM.IceModelVec2S(grid, "total_retreat_rate", PISM.WITHOUT_GHOSTS)
retreat_rate.set_attrs("output", "rate of ice front retreat", "m / s", "m / s", "", 0)

# Use our calving for retreat rate: produces dtmax_s = NaN (_s = seconds)
retreat_rate.copy_from(model.calving_rate())
# Use this, and it produces a super-large dtmax_s
#retreat_rate.set(0.0)
# Do this, and it produces a "resonable" dtmax_s
#retreat_rate.set(1000.0)

bc_mask = PISM.IceModelVec2Int(grid, "bc_mask", PISM.WITH_GHOSTS)
bc_mask.set(0.0)

dtmax_s = front_retreat.max_timestep(
    geometry.cell_type,
    bc_mask, retreat_rate).value()

print('dtmax_s = {} s ({} days)'.format(dtmax_s, dtmax_s/86400.))
