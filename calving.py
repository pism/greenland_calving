import os,sys,argparse
from uafgi import make,glaciers,flowfill
from uafgi.pism import calving, bedmachine
from uafgi.nsidc import nsidc0481

ODIR = 'outputs'
BEDMACHINE_FILE = os.path.join('bedmachine', 'BedMachineGreenland-2017-09-20.nc')
#grid='W69.10N'
#grid='W70.55N'
grid='W71.65N'
CALVING_OUTPUT = os.path.join(ODIR, '{}-calving.nc'.format(grid))

front_centers_jis = {
    'W69.10N' : None,    # Jakobshavn
    'W70.55N' : ((160,135),),    # Store Glacier
    'W71.65N' : ((473,113),),    # Rink Glacier
}

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


    # Merge the velocities into a single file
    if args.local:
        velocity_file = os.path.join(ODIR, 'velocity', grid, 'TSX_'+grid+'_2008_2020_pism_filled_x.nc')
    else:
        filter_attrs=dict(source='TSX', grid=grid)
        rule = glaciers.merge(makefile,
            os.path.join('data', grid),
            nsidc0481.parse, os.path.join(ODIR, 'velocity'),
            os.path.join(ODIR, '{source}_{grid}_2008_2020.nc'),
            ('vx','vy'),
#            max_files=3,
            filter_attrs=filter_attrs,
            blacklist=nsidc0481.blacklist).rule
        merge_rule = rule

        # Convert velocity file to PISM format
        rule = glaciers.rename_velocities_for_pism(makefile, rule.outputs[0], ODIR).rule
        velocity_file = rule.outputs[0]
        outputs.append(velocity_file)

        # Get the global BedMachine file
        rule = bedmachine.fixup_pism(makefile, BEDMACHINE_FILE, os.path.join(ODIR, 'bedmachine'))
        global_bedmachine_path = rule.outputs[0]
        outputs.append(global_bedmachine_path)

        # Extract to the local BedMachine file
        # Use any random original input file to extract the domain
        rule = bedmachine.extract(makefile, grid, global_bedmachine_path, merge_rule.inputs[0], ODIR).rule

        # Merge 2 BedMachine files into one
        rule = bedmachine.merge(makefile, rule.outputs, ODIR).rule
        local_bedmachine_path = rule.outputs[0]
        outputs.append(local_bedmachine_path)


        # Fill in missing velocities
        rule = flowfill.fill_surface_flow_rule(makefile, velocity_file,
            local_bedmachine_path, ODIR,
            prior_weight=0.8, front_centers_ji=front_centers_jis.get(grid,None)).rule
        merged_filled_path = rule.outputs[0]
        outputs.append(merged_filled_path)

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

#    outputs = ['outputs/velocity/TSX_W69.10N_vy_merged.nc']
    # -------------------------------------------------------------

#    make.build(makefile, ('outputs/TSX_W69.10N_vy_merged.nc',))
#    print('********8 outputs ', outputs)
#    print(makefile.format())
#    return

    # Build the outputs of that rule
    make.build(makefile, outputs)
    # Remove intermediate files
    make.cleanup(makefile, outputs)


main()
