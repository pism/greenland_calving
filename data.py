import itertools

# Specifics of the data/ directory

# These are files for which domain_checksum2() == 0
blacklist_raw = (
    'TSX_W69.10N_02Jun18_13Jun18_09-48-58_{parameter}_v02.0{ext}',
    'TSX_W69.10N_29May15_20Jun15_09-48-37_{parameter}_v02.0{ext}',
    'TSX_W69.10N_31May14_11Jun14_09-48-32_{parameter}_v02.0{ext}',
    'TSX_W69.10N_03Jul09_14Jul09_09-48-07_{parameter}_v02.0{ext}',
    'TSX_W69.10N_13Jun18_05Jul18_09-48-58_{parameter}_v02.0{ext}',
    'TSX_W69.10N_05Jul18_27Jul18_09-49-00_{parameter}_v02.0{ext}',
    'TSX_W69.10N_26May16_17Jun16_09-48-43_{parameter}_v02.0{ext}',
    'TSX_W69.10N_18Jul17_09Aug17_09-48-53_{parameter}_v02.0{ext}',
    'TSX_W69.10N_16Jul13_18Aug13_09-48-29_{parameter}_v02.0{ext}',
    'TSX_W69.10N_30Apr18_02Jun18_09-48-57_{parameter}_v02.0{ext}',
    'TSX_W69.10N_10Nov15_21Nov15_09-48-42_{parameter}_v02.0{ext}',
    'TSX_W69.10N_23Aug11_14Sep11_09-48-21_{parameter}_v02.0{ext}',
    'TSX_W69.10N_18Sep09_29Sep09_09-48-11_{parameter}_v02.0{ext}',
    'TSX_W69.10N_28Apr09_09May09_09-48-04_{parameter}_v02.0{ext}',
    'TSX_W69.10N_09Sep18_20Sep18_09-49-03_{parameter}_v02.0{ext}',
    'TSX_W69.10N_30Jan09_10Feb09_09-48-02_{parameter}_v02.0{ext}',
    'TSX_W69.10N_06Feb11_28Feb11_09-48-12_{parameter}_v02.0{ext}',
    'TSX_W69.10N_21Apr12_02May12_09-48-19_{parameter}_v02.0{ext}',
    'TSX_W69.10N_10Feb14_21Feb14_09-48-29_{parameter}_v02.0{ext}',
    'TSX_W69.10N_23Nov14_04Dec14_09-48-46_{parameter}_v02.0{ext}',
    'TSX_W69.10N_25Aug10_05Sep10_09-48-16_{parameter}_v02.0{ext}',
    'TSX_W69.10N_21Nov10_02Dec10_09-48-17_{parameter}_v02.0{ext}',
    'TSX_W69.10N_14Feb17_25Feb17_09-48-47_{parameter}_v02.0{ext}',
    'TSX_W69.10N_18May15_29May15_09-48-36_{parameter}_v02.0{ext}',
    'TSX_W69.10N_04Feb12_15Feb12_09-48-17_{parameter}_v02.0{ext}',
    'TSX_W69.10N_19Apr18_30Apr18_09-48-57_{parameter}_v02.0{ext}',
    'TSX_W69.10N_21Jul11_01Aug11_09-48-19_{parameter}_v02.0{ext}',
    'TSX_W69.10N_12Feb13_23Feb13_09-48-22_{parameter}_v02.0{ext}',
    'TSX_W69.10N_24Apr11_05May11_09-48-14_{parameter}_v02.0{ext}',
    'TSX_W69.10N_26Apr10_07May10_09-48-11_{parameter}_v02.0{ext}',
    # Right domain but Missing a LOT
    'TSX_W69.10N_03Jul19_25Jul19_20-42-06_{parameter}_v02.0{ext}',
    'TSX_W69.10N_10Sep17_02Oct17_10-06-06_{parameter}_v02.0{ext}', 
)

def _get_blacklist(**kwargs):
    return [x.format(**kwargs) for x in blacklist_raw]

parameters = ('vx', 'vy')
blacklist = set(itertools.chain(*[_get_blacklist(parameter=x,ext='.tif') for x in parameters]))
