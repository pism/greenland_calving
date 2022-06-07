from uafgi import gitutil,ioutil
import os,subprocess,zipfile
import uafgi.data

harness_root = gitutil.harness_root('.')
odir = uafgi.data.join_outputs('zips')
os.makedirs(odir, exist_ok=True)


def zip_results():
    with zipfile.ZipFile(
        os.path.join(odir, '1_greenland_calving_results.zip'),
        mode='w') as ozip:

        with ioutil.pushd(harness_root):
            ozip.write('greenland_calving/outputs/stability/greenland_calving.csv')
            ozip.write('greenland_calving/outputs/velterm/velterm.csv')
            ozip.write('greenland_calving/outputs/rapsheets_destabilize.pdf')
            ozip.write('greenland_calving/outputs/rapsheets_insignificant.pdf')
            ozip.write('greenland_calving/outputs/rapsheets_stabilize.pdf')


def zip_data():
    with zipfile.ZipFile(
        os.path.join(odir, '2_greenland_calving_data.zip'),
        mode='w') as ozip:


        # Add Data Files
        for arcdir in [
            'greenland_calving/data/upstream',
            'greenland_calving/data/stability_overrides',
            'greenland_calving/data/fj']:

            dir = os.path.join(harness_root, arcdir)
            for leaf in sorted(os.listdir(dir)):
                if leaf.endswith('~'):
                    continue
                ozip.write(
                    os.path.join(dir, leaf),
                    arcname=os.path.join(arcdir, leaf))

def zip_code():
    with zipfile.ZipFile(
        os.path.join(odir, '3_greenland_calving_code.zip'),
        mode='w') as ozip:

        # Add Source Files
        for repo in ('greenland_calving', 'uafgi'):
            repodir = os.path.join(harness_root, repo)
            cmd = ['git', 'ls-files']
            result = subprocess.run(cmd, cwd=repodir, stdout=subprocess.PIPE)
            files = result.stdout.decode('utf-8').split('\n')

            # ------------------- GIT_INFO.txt
            # Add info on the git remotes
            cmd = ['git', 'remote', '-v']
            result = subprocess.run(cmd, cwd=repodir, stdout=subprocess.PIPE)
            remotes = result.stdout.decode('utf-8').strip().split('\n')

            # Get info on the git version
            cmd = ['git', 'rev-parse', 'HEAD']
            result = subprocess.run(cmd, cwd=repodir, stdout=subprocess.PIPE)
            hash = result.stdout.decode('utf-8').split('\n')[0]

            # Construct GIT_INFO.txt
            lines = ['Details on the git checkout in this Zip archive',
                     '-----------------------------------------------', '']
            lines += remotes
            lines.append(f'git checkout -b {hash}')
            ozip.writestr(os.path.join(repo, 'GIT_INFO.txt'), '\n'.join(lines))

            # -----------------------------------
            # Add the files for one repo
            for file in files:
                arcname = os.path.join(repo, file)
                print(arcname)
                ozip.write(
                    os.path.join(repodir, file),
                    arcname=arcname)

def zip_sigmas():
    ofname = os.path.join(odir, '4_greenland_calving_sigmas.zip')
    if os.path.exists(ofname):
        print(f'Already exists: {ofname}')
        return

    with zipfile.ZipFile(ofname, mode='w') as ozip:

        paths = ['greenland_calving', 'outputs', 'itslive', 'sigma']
        dir = os.path.join(harness_root, *paths)
        arcdir = os.path.join(*paths)

        for file in sorted(os.listdir(dir)):
            if not file.endswith('_sigma.nc'):
                continue
            arcname = os.path.join(arcdir, file)
            print('Writing ',arcname)
            ozip.write(os.path.join(dir, file), arcname=arcname)

def main():
    zip_results()
    zip_code()
    zip_sigmas()

main()
