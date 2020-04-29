from netCDF4 import Dataset as NC
from cdo import Cdo
cdo = Cdo()
from datetime import datetime, timedelta
from osgeo import gdal
from glob import glob
import os.path
import time
import collections,re,sys
import gc
import netCDF4
import numpy as np
import csv
from giss import ioutil,iopfile,nsidc,cdoutil
import inspect
import collections

# https://lerner.co.il/2014/01/03/making-init-methods-magical-with-autoinit/
def autoinit():
    frame = inspect.currentframe(1)
    params = frame.f_locals
    self = params['self']
    paramnames = frame.f_code.co_varnames[1:] # ignore self
    for name in paramnames:
        setattr(self, name, params[name])

# ---------------------------------------------------
# https://codereview.stackexchange.com/questions/173045/mutable-named-tuple-or-slotted-data-structure
class MutableNamedTuple(collections.abc.Sequence): 
    """Abstract Base Class for objects as efficient as mutable
    namedtuples. 
    Subclass and define your named fields with __slots__.
    """
    __slots__ = ()
    def __init__(self, *args):
        for slot, arg in zip(self.__slots__, args):
            setattr(self, slot, arg)
    def __repr__(self):
        return type(self).__name__ + repr(tuple(self))
    # more direct __iter__ than Sequence's
    def __iter__(self): 
        for name in self.__slots__:
            yield getattr(self, name)
    # Sequence requires __getitem__ & __len__:
    def __getitem__(self, index):
        return getattr(self, self.__slots__[index])
    def __len__(self):
        return len(self.__slots__)
# ---------------------------------------------------
def mod_date(path):
    if os.path.exists(path):
        return os.path.getmtime(path)
    else:
        return None

class Rule(MutableNamedTuple):
    __slots__ = ('inputs', 'outputs', 'action', 'precious')

#Rule = collections.namedtuple('Rule', ('inputs', 'outputs', 'action', 'precious'))

class Makefile(object):

    def __init__(self):
        self.rules = dict()    # {target : rule}

    def add(self, action, inputs, outputs):
        rule = Rule(inputs, outputs, action, False)
        if action is not None:
            # Dummy rules aren't added to the dependency DAG
            for output in outputs:
                self.rules[output] = rule
        print('AAAAAAAding ',rule)
        return rule

class MakeRun(object):
    def __init__(self, makefile):
        self.makefile = makefile
        self.dates = dict()
        self.made = set()

    def get_dates(self, targets):
        """
        dates: {target : (date, max_sub)}
        """
        print('get_dates ',targets)

        target_dates = list()
        for target in targets:
            # Cut off repeated searching of a DAG
            if target in self.dates:
                target_dates.append(dates[target])
                continue

            # Slightly different logic for leaves (which must be there)
            if target in self.makefile.rules:
                rule = self.makefile.rules[target]
                input_dates = self.get_dates(rule.inputs)  # [(date,max_sub), ...]
                max_input_date = max(max(date, max_sub) for date,max_sub in input_dates)
            else:
                max_input_date = None

            dt = (mod_date(target), max_input_date)
            self.dates[target] = dt
            target_dates.append(dt)

        return target_dates

    def make(self, targets):
        for target in targets:
            # Maybe we made it on a previous iteration around this loop
            if target in self.made:
                continue

            # Decide whether this needs to be made
            date,max_sub = self.dates[target]
            if (date is None) or (date < max_sub):
                # This needs to be remade
                rule = self.makefile.rules[target]
                self.make(rule.inputs)
                rule.action()

                # Add to the set of things we've made
                self.made.update(rule.outputs)
            
        
# ---------------------------------------------------
class tiff_to_netcdf0(object):
    def __init__(self, makefile, pfile, odir):
        self.ipath = pfile.format()
        self.opath = os.path.join(odir, pfile.format(
            dir=odir,
            ext='.tiff_to_netcdf_0.nc'))
        self.rule = makefile.add(self.run,
            (self.ipath,),
            (self.opath,))

    def run(self):
        os.makedirs(self.opath.split()[0], exist_ok=True)

        print("Converting {} to {}".format(pfile.path, opfile.path))
        # use gdal's python binging to convert GeoTiff to netCDF
        # advantage of GDAL: it gets the projection information right
        # disadvantage: the variable is named "Band1", lacks metadata
        ds = gdal.Open(self.ipath)
        ds = gdal.Translate(self.opath, ds)
        ds = None
# -------------------------------------------------------------------------
class tiff_to_netcdf(object):

    def __init__(self, makefile, pfile, odir, oext='.nc', reftime='2008-01-01'):
        sub = tiff_to_netcdf0(makefile, pfile, odir)

        self.reftime = reftime        
        self.parameter = pfile['parameter']
        self.ipath = sub.opath
        self.opath = os.path.join(odir, pfile.format(
            dir=odir,
            ext='.nc'))

        self.rule = makefile.add(self.run, (self.ipath,), (self.opath,))

    def run(self):
        # Set the time axis
        parameter = self.parameter
        reftime = self.reftime
        inputs = [
            '-setreftime,{}'.format(self.reftime),
            '-setattribute,{}@units="m year-1"'.format(self.parmaeter),
            '-chname,Band1,{}'.format(self.parameter),
            '{}'.format(self.ipath)]
        cdo.settaxis(
            nominal_date.isoformat(),
            input=' '.join(inputs),
            output=self.opath,
            options="-f nc4 -z zip_2")
# -------------------------------------------------------------------------
class tiffs_to_netcdfs(object):
    def __init__(self, makefile, idir, odir, parameter, reftime='2008-01-01', blacklist=set(), max_files=10000000, filter_attrs=dict()):
        self.blacklist = blacklist

        # Get list of .tif files
        attrs = dict(filter_attrs.items())
        attrs['parameter'] = parameter
        attrs['ext'] = '.tif'
        filter_fn = iopfile.filter_attrs(attrs)
        self.pfiles_tif = iopfile.listdir(idir, nsidc.parse_0481, filter_fn)

        # Go through each file
        inputs = list()
        outputs = list()
        for ix,pf in enumerate(self.pfiles_tif):

            # Don't iterate over blacklisted items
            if pf.leaf in self.blacklist:
                continue

            # Cut it off early
            if ix >= max_files:
                break

            rule = tiff_to_netcdf(makefile, pf, odir, reftime=reftime).rule
            inputs += rule.inputs
            outputs += rule.outputs

        self.rule = makefile.add(None, inputs, outputs)
# -------------------------------------------------------------------------
class merge_glacier_component(object):
    def __init__(self, makefile, idir, odir, parameter, filter_attrs=dict(), **kwargs):
        """attrs should contain soure, grid
        ofpattern:
            Eg: '{source}_{grid}_2008_2020.nc'
        """

        rule = tiffs_to_netcdfs(makefile, idir, odir, parameter, **kwargs).rule

        # Start a new mergefile
        inputs = rule.outputs
        output = os.path.join(
            odir, '{source}_{grid}_{parameter}_merged.nc'.format(**attrs))

        self.rule = makefile.add(self.run, inputs, (output,))


    def run(self):

        # Merge into the mergefile
        cdoutil.large_merge(
            cdo.mergetime,
            input=self.rule.inputs,
            output=self.rule.outputs[0],
            options="-f nc4 -z zip_2",
            max_merge=50)
# -------------------------------------------------------------------------
class merge_glacier(object):
    def __init__(self, makefile, idir, odir, ofpattern, parameters, filter_attrs=dict(), **kwargs):
        self.inputs = list()
        for parameter in parameters:
            rule = merge_glacier_component(makefile, idir, odir, parameter, filter_attrs=filter_attrs, **kwargs).rule
            self.inputs += rule.outputs

        self.rule = makefile.add(self.run, inputs, (ofpattern.format(**filter_attrs),))

    def run(self):
        print('Merging to {}'.format(ofile))
        cdo.merge(
            input=self.rule.inputs,
            output=self.rule.outputs[0],
            options="-f nc4 -z zip_2")





def main():
    makefile = Makefile()
    rule = tiffs_to_netcdfs(makefile, 'data', 'outputs', 'vx', max_files=3).rule

    print(len(rule.inputs),len(rule.outputs))

#    for rule in makefile.rules.values():
#        print(rule)

    mr = MakeRun(makefile)
    for x in mr.get_dates(rule.outputs):
        print(x)

#    mr.make(rule.outputs)

#    print(makefile.rules)

main()
