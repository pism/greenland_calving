import os,sys,argparse
from uafgi import make,glaciers,flowfill
from uafgi.pism import calving, bedmachine
from uafgi.nsidc import nsidc0481

ODIR = 'outputs'
BEDMACHINE_FILE = os.path.join('bedmachine', 'BedMachineGreenland-2017-09-20.nc')
CALVING_OUTPUT = os.path.join(ODIR, 'calving.nc')

def main():

    parser = argparse.ArgumentParser(description='Process velocity files through calving model')
    parser.add_argument('--local', action='store_true',
        help='Only run the last few steps, assumes BedMachine and TSX files are already there')
    args = parser.parse_args()


    # Create a blank makefile
    makefile = make.Makefile()
    # Things we want to keep
    outputs = []

    # --------------------------------------------------------------
    # Create the internal Makefile

    grid='W69.10N'

    # Merge the velocities into a single file
    if args.local:
        velocity_file = os.path.join(ODIR, 'velocity', 'TSX_'+grid+'_2008_2020_pism_filled.nc')
    else:
        filter_attrs=dict(source='TSX', grid=grid)
        rule = glaciers.merge(makefile, 'data', nsidc0481.parse, os.path.join(ODIR, 'velocity'),
            os.path.join(ODIR, '{source}_{grid}_2008_2020.nc'),
            ('vx','vy'),
#            max_files=3,
            filter_attrs=filter_attrs,
            blacklist=nsidc0481.blacklist).rule

        # Convert velocity file to PISM format
        rule = glaciers.rename_velocities_for_pism(makefile, rule.outputs[0], ODIR).rule
        velocity_file = rule.outputs[0]
        outputs.append(velocity_file)

        # Get the global BedMachine file
        rule = bedmachine.fixup_pism(makefile, BEDMACHINE_FILE, os.path.join(ODIR, 'bedmachine'))
        global_bedmachine_path = rule.outputs[0]
        outputs.append(global_bedmachine_path)

        # Extract to the local BedMachine file
        rule = bedmachine.extract(makefile, grid, global_bedmachine_path, velocity_file, ODIR).rule

        # Merge 2 BedMachine files into one
        rule = bedmachine.merge(makefile, rule.outputs, ODIR).rule
        local_bedmachine_path = rule.outputs[0]
        outputs.append(local_bedmachine_path)


        # Fill in
        rule = flowfill.fill_surface_flow_rule(makefile, velocity_file,
            local_bedmachine_path, ODIR, max_timesteps=3).rule
        merged_filled_path = rule.outputs[0]
        outputs.append(merged_filled_path)


#    # Fixup bedmachine file
#    if args.local:
#        bedmachine_file = os.path.join(ODIR, 'bedmachine', 'BedMachineGreenland-2017-09-20_pism.nc4')
#    else:
#        rule = bedmachine.fixup_pism(makefile, BEDMACHINE_FILE, os.path.join(ODIR, 'bedmachine'))
#        bedmachine_file = rule.outputs[0]
#        outputs.append(bedmachine_file)
#
    # Compute calving based on velocity file
    rule = calving.compute(
        makefile, local_bedmachine_path, merged_filled_path,
        (merged_filled_path,('u_ssa_bc',)),
        CALVING_OUTPUT).rule
#    rule = calving.compute(
#        makefile, local_bedmachine_path, velocity_file,
#        (velocity_file,('u_ssa_bc',)),
#        CALVING_OUTPUT).rule

    outputs.extend(rule.outputs)

    # -------------------------------------------------------------

#    make.build(makefile, ('outputs/TSX_W69.10N_vy_merged.nc',))
    print('********8 outputs ', outputs)

    # Build the outputs of that rule
    make.build(makefile, outputs)
    # Remove intermediate files
    make.cleanup(makefile, outputs)


main()
