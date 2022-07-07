from uafgi.util import gitutil,ioutil
import os,subprocess,zipfile
import uafgi.data
import re
import subprocess
import sys

import yaml


# =====================================================================

# https://gist.githubusercontent.com/gwerbin/dab3cf5f8db07611c6e0aeec177916d8/raw/63c7191731b530aceaf887e9f33478fcad33d351/conda_env_export.py
"""
Export a Conda environment with --from-history, but also append
Pip-installed dependencies

Exports only manually-installed dependencies, excluding build versions, but
including Pip-installed dependencies.

Lots of issues requesting this functionality in the Conda issue tracker, no
sign of progress (as of March 2020).

TODO (?): support command-line flags -n and -p
"""


def export_env(history_only=False, include_builds=False):
    """ Capture `conda env export` output """
    cmd = ['conda', 'env', 'export']
    if history_only:
        cmd.append('--from-history')
        if include_builds:
            raise ValueError('Cannot include build versions with "from history" mode')
    if not include_builds:
        cmd.append('--no-builds')
    cp = subprocess.run(cmd, stdout=subprocess.PIPE)
    try:
        cp.check_returncode()
    except:
        raise
    else:
        return yaml.safe_load(cp.stdout)


def _is_history_dep(d, history_deps):
    if not isinstance(d, str):
        return False
    d_prefix = re.sub(r'=.*', '', d)
    return d_prefix in history_deps


def _get_pip_deps(full_deps):
    for dep in full_deps:
        if isinstance(dep, dict) and 'pip' in dep:
            return dep


def _combine_env_data(env_data_full, env_data_hist):
    deps_full = env_data_full['dependencies']
    deps_hist = env_data_hist['dependencies']
    deps = [dep for dep in deps_full if _is_history_dep(dep, deps_hist)]

    pip_deps = _get_pip_deps(deps_full)

    env_data = {}
    env_data['channels'] = env_data_full['channels']
    env_data['dependencies'] = deps
    env_data['dependencies'].append(pip_deps)

    return env_data
# =====================================================================

harness_root = gitutil.harness_root('.')
odir = uafgi.data.join_outputs('zips')
os.makedirs(odir, exist_ok=True)


def zip_results():
    with zipfile.ZipFile(
        os.path.join(odir, '1_greenland_calving_results.zip'),
        mode='w') as ozip:

        ozip.write('README.md')

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


        ozip.write('README.md')

        # Include just one sigma file, used for plot
        # The rest come in 4_greenland_calving_sigma.zip
        ozip.write('outputs/itslive/sigma/GRE_G0240_W70.90N_1985_2018_sigma.nc')

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

        ozip.write('README.md')

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

        ozip.write('README.md')

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
    zip_data()
    zip_code()
    zip_sigmas()

main()
