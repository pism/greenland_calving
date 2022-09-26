import subprocess
import os,zipfile,io,sys

ENDPOINT = 'https://arcticdata.io/metacat/d1/mn/v2'
DATASET_PID = 'urn:uuid:d2a541d1-b8a2-4241-9ab6-545253e18bc5'

download_plan = [
    (1, 'greenland_calving/outputs/rapsheets_destabilize.pdf', 'urn:uuid:3e8c7a41-3f27-4828-92ef-eec54921815e'),
    (1, 'greenland_calving/outputs/rapsheets_insignificant.pdf', 'urn:uuid:1ed009ca-744d-421a-9a20-e638db739868'),
    (1, 'greenland_calving/outputs/rapsheets_stabilize.pdf', 'urn:uuid:aa282e60-7e11-4b83-b3bb-8f0f2afca36a'),
    (1, 'greenland_calving/outputs/stability/greenland_calving.csv', 'urn:uuid:a4121508-2994-4cca-abec-b60aef121941'),
    (1, 'greenland_calving/outputs/stability/study_glaciers_igs_names.csv', 'urn:uuid:fb8fe15d-5599-4126-889a-3e12497fb156'),
    (1, 'greenland_calving/outputs/velterm/velterm.csv', 'urn:uuid:07b7a1fd-7b73-4418-8527-c20e3faa7a07'),
    (2, 'data/fj/fjord_outlines.zip', 'urn:uuid:dbeb2fc0-2d3f-4935-b23f-35bfd7a93611'),
    (2, 'data/stability_overrides/bkm15_match.ods', 'urn:uuid:6f88636b-8765-449a-ab03-e58ce6459018'),
    (2, 'data/stability_overrides/overrides.ods', 'urn:uuid:a073c14b-2f99-46c4-96bd-446f220096c9'),
    (2, 'data/stability_overrides/sl19_match.ods', 'urn:uuid:9a73bcfd-3100-408d-81b3-69cd2b6a30e2'),
    (2, 'data/stability_overrides/study_glaciers_overrides.csv', 'urn:uuid:84b2e311-917f-4acc-b7bc-9f7b3f212a08'),
    (2, 'data/stability_overrides/terminus_locations.zip', 'urn:uuid:734715e8-b726-4e14-93aa-0ea76d24ba1d'),
    (2, 'data/upstream/upstream_points.zip', 'urn:uuid:ded8b76a-503f-46f7-9fa9-df8f6d209f9c'),
    (2, 'outputs/itslive/sigma/GRE_G0240_W70_90N_1985_2018_sigma.nc', 'urn:uuid:02cd045b-6c3f-4590-adbf-31036d5d5fb5'),
    (3, '3_greenland_calving_code.zip', 'urn:uuid:951a1d36-0137-40ed-9b0d-050df0ae0c6d'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E61_10N_1985_2018_sigma.nc', 'urn:uuid:cdeed770-f9b4-479c-8aa1-b194b3bd676a'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E61_70N_1985_2018_sigma.nc', 'urn:uuid:24d703b2-48de-46a8-9ed3-da314284d740'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E62_10N_1985_2018_sigma.nc', 'urn:uuid:1cfead0a-1876-4312-a3b9-f6edb6da8677'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E62_55N_1985_2018_sigma.nc', 'urn:uuid:7a83662e-1247-46c0-95b4-64d6bc9d3d92'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E63_00N_1985_2018_sigma.nc', 'urn:uuid:4afc4256-6661-467b-841c-0ce898ced12c'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E63_35N_1985_2018_sigma.nc', 'urn:uuid:b300a672-272a-4de0-ab96-7256a9277db9'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E63_85N_1985_2018_sigma.nc', 'urn:uuid:76feaddf-1808-4c21-a761-2155a91eed03'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E64_35N_1985_2018_sigma.nc', 'urn:uuid:23afde3d-3623-4342-a411-10ca42869fb1'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E64_65N_1985_2018_sigma.nc', 'urn:uuid:ff437ffc-5511-46fb-99a6-e26f9575687e'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E65_10N_1985_2018_sigma.nc', 'urn:uuid:e42d5db8-ade9-4269-bb8f-3efa21283170'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E65_55N_1985_2018_sigma.nc', 'urn:uuid:228db8ad-3982-4887-a76b-69345b023ad7'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E66_50N_1985_2018_sigma.nc', 'urn:uuid:5fcaca78-25b4-4d89-9b93-646c5a52ac5c'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E66_60N_1985_2018_sigma.nc', 'urn:uuid:f11096b0-a0fb-4149-ac8d-70c8d80018c4'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E66_90N_1985_2018_sigma.nc', 'urn:uuid:048c8087-1036-4bec-9930-bb448773fa69'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E67_55N_1985_2018_sigma.nc', 'urn:uuid:e9b2ab89-b096-428f-9e0f-2f61f0cd2327'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E68_50N_1985_2018_sigma.nc', 'urn:uuid:5d2f8127-bad0-4551-b1d6-7dabf79744bd'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E68_80N_1985_2018_sigma.nc', 'urn:uuid:9b5e6374-1eda-4eb1-9f73-4c0d01a887d3'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E71_75N_1985_2018_sigma.nc', 'urn:uuid:80c928a7-4ab7-406b-9e4b-770ee13001ae'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E78_90N_1985_2018_sigma.nc', 'urn:uuid:0050b1da-1a95-40f5-a4c7-7a96400b08c4'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E81_35N_1985_2018_sigma.nc', 'urn:uuid:c1f8da06-372c-4ca3-abc2-e7d74dd18d7e'),
    (4, 'outputs/itslive/sigma/GRE_G0240_E81_45N_1985_2018_sigma.nc', 'urn:uuid:0f8ae581-dda3-4184-a46f-86999b03d089'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W61_70N_1985_2018_sigma.nc', 'urn:uuid:3b75fa52-a1ba-4780-8d70-c978cd809d92'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W62_10N_1985_2018_sigma.nc', 'urn:uuid:c820adc9-976b-4f9b-a9db-46f3b67e1c7c'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W64_25N_1985_2018_sigma.nc', 'urn:uuid:64b2f8e2-5d7e-4c8a-86a0-bedfaa92858f'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W64_75N_1985_2018_sigma.nc', 'urn:uuid:b5cd5fb3-b2cd-4d2d-9af2-3ee8905c6b50'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W69_10N_1985_2018_sigma.nc', 'urn:uuid:4433d408-00ea-41d2-b47f-628a4448223a'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W69_95N_1985_2018_sigma.nc', 'urn:uuid:3a960022-b337-49d3-a8de-50a477773922'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W70_55N_1985_2018_sigma.nc', 'urn:uuid:a9db645a-191a-4a45-ba50-7d3c62dc575b'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W71_65N_1985_2018_sigma.nc', 'urn:uuid:1435584e-08d4-4286-ae51-f5f191df44bb'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W72_00N_1985_2018_sigma.nc', 'urn:uuid:2b5c0623-33dd-4cd5-95b0-b4d88525c1b5'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W72_90N_1985_2018_sigma.nc', 'urn:uuid:503ed5b6-9b6c-4983-adb2-e5c2f1442e6a'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W73_75N_1985_2018_sigma.nc', 'urn:uuid:1aa20a06-7dc2-4cf2-a59c-0d4ac00f18d5'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W74_50N_1985_2018_sigma.nc', 'urn:uuid:6de0f709-29f2-4b61-b93f-9f05af5a3665'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W74_95N_1985_2018_sigma.nc', 'urn:uuid:3b370e34-0e43-4b2e-b700-87fe0ea9ad91'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W75_50N_1985_2018_sigma.nc', 'urn:uuid:65816a5b-86cb-414e-b0e4-df019e4d6c1a'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W75_85N_1985_2018_sigma.nc', 'urn:uuid:74bff514-f8a2-4254-b0f7-e87871253b30'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W76_10N_1985_2018_sigma.nc', 'urn:uuid:90e32120-e26b-47ea-b497-6165b713f78b'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W76_25N_1985_2018_sigma.nc', 'urn:uuid:6a22c189-640a-4409-85d1-1111506e46e9'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W76_35N_1985_2018_sigma.nc', 'urn:uuid:f9faab28-b2be-4a77-ab0f-70978d82a4ed'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W76_40N_1985_2018_sigma.nc', 'urn:uuid:6d84f2ab-dfbc-4f01-98e8-249bfcae2c1f'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W76_45N_1985_2018_sigma.nc', 'urn:uuid:5c411dcb-d746-4e91-8205-5d74388081e8'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W77_55N_1985_2018_sigma.nc', 'urn:uuid:feb5c9a3-4827-4e55-b889-548dc4bbfd71'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W79_75N_1985_2018_sigma.nc', 'urn:uuid:b42708eb-72fc-43a0-85e4-77aa0616db5c'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W80_75N_1985_2018_sigma.nc', 'urn:uuid:051970fc-83f4-41e6-92b6-dc63ec25f29f'),
    (4, 'outputs/itslive/sigma/GRE_G0240_W81_50N_1985_2018_sigma.nc', 'urn:uuid:a31732ec-9dff-4515-a3cf-12e1065c2bec')]

def download_file(ofname, pid, zipdir):

    # See if we already downloaded
    check_file = ofname
    if ofname.endswith('.zip'):
        check_file = os.path.join(zipdir, os.path.split(ofname)[1])
    if os.path.exists(check_file):
        print('ALREADY EXISTS: {}'.format(ofname))
        return

    print('DOWNLOADING: {}\n    {}'.format(ofname, pid))

    # Download the file into memory
    cmd = ['curl',  '-X',  'GET']
    if 'TOKEN' in os.environ:
        cmd += ['-H', f'Authorization: Bearer {os.environ["TOKEN"]}']

    cmd += ['-H', f'Accept: text/xml',
         f'{ENDPOINT}/object/{pid}']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout,_ = proc.communicate()

    # See if what we downloaded was good
    head = stdout[:300]
    if b'errorCode' in head:
        raise FileNotFoundError(head.decode('UTF-8') + '\nDo you need to fix your TOKEN at arcticdata.io?')

    odir = os.path.split(ofname)[0]
    os.makedirs(odir, exist_ok=True)

    if ofname.endswith('.zip'):
        # Unzip the zipfile
        with zipfile.ZipFile(io.BytesIO(stdout)) as file_zip:
            for zi in file_zip.infolist():
                if zi.is_dir():
                    continue
                if '__MACOSX' in zi.filename:
                    continue
                with file_zip.open(zi.filename) as fin:
                    zname = os.path.join(odir, zi.filename)
                    os.makedirs(os.path.split(zname)[0], exist_ok=True)
                    print('    {}'.format(zname))
                    with open(zname, 'wb') as out:
                        out.write(fin.read())

        # Note that we already downloaded
        os.makedirs(zipdir, exist_ok=True)
        with open(check_file, 'w') as out:
            out.write('DOWNLOADED\n')

    else:
        with open(ofname, 'wb') as out:
            out.write(stdout)

if len(sys.argv) < 3:
    print('USAGE: python a00_download_arcticdata.py <dest-dir> <level>\n' +
        '   level = 1: results, 2: also data, 3: also code, 4: also sigma files\n' +
        'NOTE: You may have to authenticate and set the TOKEN environment variable, see:\n' +
        '    https://arcticdata.io/catalog/api')
    sys.exit(0)

oroot = sys.argv[1]
max_level = int(sys.argv[2])
for level,ofname,pid in download_plan:
    if level <= max_level:
        download_file(os.path.join(oroot, ofname), pid, os.path.join(oroot, 'zipdownloads'))

