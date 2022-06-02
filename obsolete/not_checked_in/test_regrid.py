from uafgi import regrid, make, itslive

def main():

    makefile = make.Makefile()
    grid = 'W69.10N'
    rule = regrid.extract_region(makefile, grid,
        'data/its-live/GRE_G0240_2018.nc',
        'outputs/{}-grid.nc'.format(grid),
        ('vx', 'vy', 'v'), 'outputs').rule

    outputs = rule.outputs

    rule = itslive.merge_to_pism(makefile, grid, 'data/itslive/GRE_G0240_{}.nc',
        (2017,2018), 'outputs').rule
    outputs = rule.outputs

    make.build(makefile, outputs)
    make.cleanup(makefile, outputs)

main()
