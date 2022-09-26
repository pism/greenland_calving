import subprocess
import os,re,zipfile,io
import xml.etree.ElementTree




TOKEN = os.environ['ARCTICDATA_TOKEN']
ENDPOINT = 'https://arcticdata.io/metacat/d1/mn/v2'
DATASET_PID = 'urn:uuid:d2a541d1-b8a2-4241-9ab6-545253e18bc5'


index_xml = 'index.xml'

skips = {'title', 'creator', 'associatedParty', 'pubDate', 'abstract', 'intellectualRights', 'distribution', 'coverage', 'annotation', 'contact', 'keywordSet', 'publisher', 'methods', 'projects', 'project'}

keeps = {'dataTable', 'otherEntity', 'spatialVector'}

excluded_files = {
    '1_greenland_calving_results.zip',
    '2_greenland_calving_data.zip'}

# https://arcticdata.io/catalog/api#get
def get_arcticdata_objects():
    objs = dict()

    if os.path.exists(index_xml):
        with open(index_xml, 'rb') as fin:
            stdout = fin.read()
    else:
        cmd = ['curl',  '-X',  'GET',
            '-H', f'Authorization: Bearer {TOKEN}',
            '-H', f'Accept: text/xml',
             f'{ENDPOINT}/object/{DATASET_PID}']
        print(' '.join("'{}'".format(x) for x in cmd))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdout,_ = proc.communicate()

        with open(index_xml, 'wb') as out:
            out.write(stdout)

    txt = stdout.decode('UTF-8')
    root = xml.etree.ElementTree.fromstring(txt)
#    for dataTable in root.find('dataset').findall('dataTable'):
    for ele in root.find('dataset'):
        if ele.tag in skips:
            continue
        
        if 'id' not in ele.attrib:
            continue

        pid = ele.attrib['id'].replace('urn-uuid-', 'urn:uuid:')
        entity = ele.find('entityName').text
        if entity not in excluded_files:
            objs[entity] = pid
    return objs

root = os.path.abspath('..')
data_dirs = ['../data', 'outputs']
def get_local_paths():
    all_files = list()
    for subdir in data_dirs:
        start_dir = os.path.abspath(os.path.join('.', subdir))
        for path,dirs,files in os.walk(start_dir):
            all_files += [os.path.relpath(os.path.join(path,file), root) for file in files]

    # Match .shp in our data against .zip in the arcticdata.io download
    all_files = [x[:-4]+'.zip' if x.endswith('.shp') else x for x in all_files]

    # Convert leafname to full path
    file_paths = {os.path.split(x)[1] : x for x in all_files}

    # Add special case
    file_paths['3_greenland_calving_code.zip'] = '3_greenland_calving_code.zip'
    return file_paths


greRE = re.compile(r'^GRE_G0240_.*\.nc$')

# Which "original" zipfile this key was found in
_zip_levels = {
    'greenland_calving.csv': 1,
    'study_glaciers_igs_names.csv': 1,
    'velterm.csv': 1,
    'rapsheets_destabilize.pdf': 1,
    'rapsheets_insignificant.pdf': 1,
    'rapsheets_stabilize.pdf': 1,
    'GRE_G0240_W70.90N_1985_2018_sigma.nc': 2,
    '3_greenland_calving_code.zip': 3,
}
def zip_level(leaf):
    try:
        return _zip_levels[leaf]
    except:
        pass

    # Most _sigma files are level 4
    match = greRE.match(leaf)
    if match is not None:
        return 4

    # Everything else is level 2
    return 2


def get_download_plan():
    dlfiles = list()

    aobj = get_arcticdata_objects()
    lpaths = get_local_paths()
    for leaf,pid in aobj.items():

        match = greRE.match(leaf)
        if match is not None:
            # Special case: the _sigma files (which are large so might not have existed in our outputs dir)
            ofname = os.path.join('outputs', 'itslive', 'sigma', leaf)
        else:
            ofname = lpaths[leaf]

        zlev = zip_level(leaf)
        dlfiles.append((zlev, ofname, pid))

    return sorted(dlfiles)


def download_file(ofname, pid, zipdir):
    print('DOWNLOADING: ', ofname, pid)

    # See if we already downloaded
    check_file = ofname
    if ofname.endswith('.zip'):
        check_file = os.path.join(zipdir, os.path.split(ofname)[1])
    if os.path.exists(check_file):
        return

    # Download the file into memory
    cmd = ['curl',  '-X',  'GET',
        '-H', f'Authorization: Bearer {TOKEN}',
        '-H', f'Accept: text/xml',
         f'{ENDPOINT}/object/{pid}']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout,_ = proc.communicate()

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
                    with open(zname, 'wb') as out:
                        out.write(fin.read())

        # Note that we already downloaded
        os.makedirs(zipdir, exist_ok=True)
        with open(check_file, 'w') as out:
            out.write('DOWNLOADED\n')

    else:
        with open(ofname, 'wb') as out:
            out.write(stdout)

def download_all(oroot, max_level):
    dlfiles = get_download_plan()
    for level,ofname,pid in dlfiles:
        if level <= max_level:
            download_file(os.path.join(oroot, ofname), pid, os.path.join(oroot, 'zipdownloads'))

download_all('/Users/eafischer2/tmp/gc', 4)

