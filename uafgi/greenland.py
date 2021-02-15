import re
import pandas as pd
import itertools
# https://www.datacamp.com/community/tutorials/fuzzy-string-python
import Levenshtein
import shapely
import pyproj
import os
from uafgi import ioutil,shputil,gicollections
import csv
import numpy as np

def sep_colnames(lst):
    """Process colnames and units into names list and units dict"""

    colnames = list()
    units = dict()
    for x in lst:
        if isinstance(x,tuple):
            colnames.append(x[0])
            units[x[0]] = x[1]
        else:
            colnames.append(x)
    return colnames, units

# https://stackoverflow.com/questions/6718196/determine-prefix-from-a-set-of-similar-strings
# Return the longest prefix of all list elements.
def commonprefix(m):
    "Given a list of pathnames, returns the longest common leading component"
    if not m: return ''
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1

def points_col(lon_col, lat_col, transform_wgs84):
    """Creates a Series with projected Shapely points
    lon_col:
        DataFrame column with longitude
    lat_col:
        DataFrame column with latitude
    transform_wgs84:
        pyproj transformer from lon/lat to x/y
    """
    return pd.Series(
        index=lon_col.index,
        data=[shapely.geometry.Point(x,y) for x,y in zip(
            *transform_wgs84.transform(lon_col.tolist(), lat_col.tolist()))]
        )

class ExtDf:
    """A dataframe with a unit dict attached"""

    def __repr__(self):
        return 'ExtDf({})'.format(self.prefix)

    #__slots__ = ('df', 'units', 'namecols')
    def __init__(self, df0, map_wkt, add_prefix=None, units=dict(), lonlat=None, namecols=None, keycols=None):

        # Save basic stuff
        self.units = units

        # ---------------------------------------------
        # Mess with projections
        self.map_wkt = map_wkt

        # wgs84: lon/lat from selections DataFrame (above)
        #        (ultimately from glacier location database files)
        wgs84 = pyproj.CRS.from_epsg("4326")

        # Assume all grids use the same projection (NSIDC Polar Stereographic)
        # Project everything to it
        map_crs = pyproj.CRS.from_string(map_wkt)

        # Transform from lat/lon into map projection
        transform_wgs84 = pyproj.Transformer.from_crs(wgs84,map_crs,always_xy=True)
        # -------------------------------------------------


        # Shallow copy
        self.df = df0.copy()

        
        # Figure out prefix stuff
        if add_prefix is None:
            self.prefix = commonprefix(list(df))
        else:
            self.prefix = add_prefix

            # Add prefix to existing column names
            self.df.columns = [add_prefix + str(x) for x in self.df.columns]
            if namecols is not None:
                namecols = [self.prefix+x for x in namecols]
            if keycols is not None:
                keycols = [self.prefix+x for x in keycols]
            if lonlat is not None:
                lonlat = [self.prefix+x for x in lonlat]
            self.units = {self.prefix+name:val for name,val in self.units.items()}
    

        # Create a 'loc' column based on projecting the lon/lat coordinates of two original cols
        if lonlat is not None:
            self.df[self.prefix+'loc'] = points_col(self.df[lonlat[0]], self.df[lonlat[1]], transform_wgs84)
            self.units[self.prefix+'loc'] = 'm'    # TODO: Fish this out of the projection

        # -------------------------------------------------
        dropme = set()

        # Create a 'key' column
        if keycols is not None:
            self.df[self.prefix+'key'] = list(zip(*[self.df[x] for x in keycols]))
            self.keycols = keycols
#            if drop_cols:
#                dropme.update(self.keycols)
                #self.df = self.df.drop(self.keycols, axis=1)
        else:
            self.keycols = list()

        # Make sure this is a proper unique key
        dups = self.df[self.prefix+'key'].duplicated(keep=False)
        dups = dups[dups]
        if len(dups) > 0:
            print('============================ Duplicate keys')
            print(self.df.loc[dups.index])

        # Create an 'allnames' column by zipping all columns indicating any kind of name
        if namecols is not None:
            self.df[self.prefix+'allnames'] = list(zip(*[self.df[x] for x in namecols]))
            self.namecols = namecols
#            if drop_cols:
#                dropme.update(self.namecols)
                #self.df = self.df.drop(self.namecols, axis=1)
        else:
            self.namecols = list()

        self.df = self.df.drop(list(dropme), axis=1)

# ================================================================
# ================================================================
# ================================================================
# ================================================================

# ================================================================
# ================================================================
# ================================================================

# Good article on Greenland place names
# https://forum.arctic-sea-ice.net/index.php?topic=277.20;wap2

# https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
class ReplaceMany:
    def __init__(self, replaces):
        # use these three lines to do the replacement
        self.rep = dict((re.escape(k), v) for k, v in replaces) 
        self.pattern = re.compile("|".join(self.rep.keys()))

    def __call__(self, text):
        return self.pattern.sub(lambda m: self.rep[re.escape(m.group(0))], text)

_replace_chars = ReplaceMany([
    ('.', ''),
    ('æ', 'ae'),
#    ('Æ', 'AE'),
    ('ø', 'o'),
#    ('Ø', 'O'),
    ('â', 'a'),
    ('â', 'a'),
    ('ù', 'u'),
])

class ReplaceWords:
    def __init__(self, replaces):
        self.replaces = dict(replaces)
    def __call__(self, word):
        try:
            return self.replaces[word]
        except KeyError:
            return word

_replace_words = ReplaceWords([
    # "Glacier"
    ('gletsjer', 'gl'),
    ('gletscher', 'gl'),
    ('glacier', 'gl'),

    # "Glacier"
    ('se', 'sermia'),
#    ('sermia', 'se'),
#    ('sermiat', 'se'),
#    ('sermeq', 'se'),
#    ('sermilik', 'se'),
])


_dirRE = re.compile(r'^(n|s|e|w|nw|ss|c|sss|cs|cn)$')

def fix_name(name):
    name = _replace_chars(name.lower())
    words = name.replace('_', ' ').split(' ')
    words = [_replace_words(w) for w in words]


    # See if the last word is a direction designator.  Eg:
    #     Upernavik Isstrom N
    #     Upernavik Isstrom C
    #     Upernavik Isstrom S
    #     Upernavik Isstrom SS	
    match = _dirRE.match(words[-1])
    if match is not None:
        ret = (' '.join(words[:-1]), words[-1])
    else:
        ret = (' '.join(words), '')
#    print(ret)
    return ret
 
def levenshtein(name0, name1):
    '''Determines if two names are the same or different'''
    n0,dir0 = fix_name(name0)
    n1,dir1 = fix_name(name1)

    return (dir0==dir1, Levenshtein.ratio(n0,n1))
    
def max_levenshtein(names0, names1):
    """Computes maximum Levenshtein ratio of one name in names0 vs. one name in names1."""
    dir_and_ratio = (False,-1.)

#    nm0 = [x for x in names0 if len(x)>0]
#    nm1 = [x for x in names1 if len(x)>0]
    for n0,n1 in itertools.product(
        (x for x in names0 if len(x)>0),
        (x for x in names1 if len(x)>0)):
        dir_and_ratio = max(dir_and_ratio, levenshtein(n0,n1))

        # OPTIMIZATION: If we already found a full match, we're done!
        if dir_and_ratio == (True,1.0):
            return dir_and_ratio
    return dir_and_ratio

def levenshtein_cols(allnames0, allnames1):

    """For each row in a bunch of columns, compute the maximum Levenshtein
    ratio between any column in df0 and any column in df1.  Thus, it is likely
    to find a match if *any* column of df0 matches *any* column of df1.

    df0, df1: Dframe
        DataFrames consisting of columns to be joined.
        NOTE: This should ONLY contain columns to be joined
    Returns: DataFrame

df0 and df1 are DataFrames, selecting out just the cols we want to join.
    cols0 all share an index; cols1 all share a different index

    """

    col_ix0 = list()
    col_ix1 = list()
    col_dir = list()
    col_lev = list()
    for ix0,an0 in allnames0.iteritems():
        for ix1,an1 in allnames1.iteritems():

            col_ix0.append(ix0)
            col_ix1.append(ix1)
            dir,lev = max_levenshtein(an0, an1)
            col_dir.append(dir)
            col_lev.append(lev)

#            if len(col_ix0) > 10:
#                break
#        if len(col_ix0) > 1:
#            break

    return pd.DataFrame({
        'ix0' : col_ix0,
        'ix1' : col_ix1,
        'dir' : col_dir,
        'lev' : col_lev,
    })

# ============================================================
class Match(gicollections.MutableNamedTuple):
    __slots__ = (
        'xfs',     # (left, right): ExtDfs being joined
        'cols',    # Columns being joined in left and right
        'df')      # The match dataframe

    def __repr__(self):
        return 'Match({}, len={})'.format(
            str(list(zip(self.xfs, self.cols))),
            len(self.df))

    def left_join(self, overrides=None, ignore_dups=False, right_cols=None):

        """Given a raw Match, returns a DataFrame that can be used for a left
        outer join.  It will have (assuming ExtDfs named 
          1. No more than copy of each row of the left ExtDf
          2. Columns: [<left>_ix, <left>_key, <right>_ix, <right>_key]

        Raises a ValueError if the (1) cannot be satisfied.

        match: Match
            Raw result of a match
        overrides: DataFrame
            Manual overrides for the join.
            Contains columns: [<left>_key, <right>_key]
        ignore_dups:
            Remove any duplicate rows (on the left key) from the join.
            Otherwise, raise a ValueError on any duplicate rows.
        right_cols: [str, ...]
            Names of columns from right DataFrame to keep.
            If None, keep all columns.
        """

        # Column names / shortcuts
        left = self.xfs[0]
        left_ix = left.prefix + 'ix'
        left_key = left.prefix + 'key'
        right = self.xfs[1]
        right_ix = right.prefix + 'ix'
        right_key = right.prefix + 'key'

        # Make dummy overrides
        if overrides is None:
            overrides = pd.DataFrame(columns=[left_ix, left_key, right_ix, right_key])

        # Add index columns to overrides (for convenient joining w/ other tables)
        for xf in self.xfs:
            print('xf={}'.format(xf))
            df = xf.df
            key = xf.prefix+'key'

            print('key ',key)
            print('over ',overrides.columns)
            print('df ',df.columns)

            overrides = pd.merge(overrides, df[[key]].reset_index(), how='left', on=key) \
                .rename(columns={'index':xf.prefix+'ix'})

        # Remove extraneous columns
        df = self.df[[left_ix, left_key, right_ix, right_key]]

        # Remove overridden rows (from left) from our match DataFrame
        df = pd.merge(df, overrides[[left_key]], how='left', on=left_key, indicator=True)
        df = df[df['_merge'] != 'both'].drop(['_merge'], axis=1)

        # Add in (manual) overrides
        if len(overrides) > 0:
            df = pd.concat([overrides,df], ignore_index=True)

        # Check for duplicate left keys
        dups0 = df[left_key].duplicated(keep=False)
        dups = dups0[dups0]
        # df.loc[dups.index].sort_values(xf0.prefix+'key')

        # Remove all dups for testing...
        if ignore_dups:
            df = df[~dups0]
            #df.sort_values(xf0.prefix+'key')
        else:
            #print(self.df.columns)
            print(self.df.index)
            print(dups.index)

            ddf = pd.merge(self.df, df[[left_key]].loc[dups.index], how='inner', left_index=True, right_index=True, suffixes=(None,'_DELETEME'))
            drops = {x for x in ddf.columns if x.endswith('_DELETEME')}
            ddf = ddf.drop(list(drops), axis=1)
            ddf = ddf.sort_values([left_key, right_key])

            print(len(dups), len(ddf))
            if len(dups) > 0:
                raise ValueError('\n'.join([
                    'Duplicate right values found in left outer join.',
                    ddf.to_string()]))
        matchdf = df

        # -------------------------------------------
        # Do the join!
        # https://stackoverflow.com/questions/11976503/how-to-keep-index-when-using-pandas-merge

        # Join left -- matchdf
        df = pd.merge(
            left.df.reset_index(), matchdf, how='left',
            left_index=True, right_on=left_ix,
            suffixes=(None,'_DELETEME')).set_index('index')

        # Join (left -- matchdf) -- right
        df = pd.merge(df.reset_index(),
            right.df if right_cols is None else right.df[right_cols],
            how='left', left_on=right_ix, right_index=True,
            suffixes=(None,'_DELETEME')).set_index('index')

        # Remove extra columns that accumulated in the join
        drops = {x for x in df.columns if x.endswith('_DELETEME')}
        drops.update([left_ix, right_ix])
        if (right_cols is not None) and (right_key not in right_cols):
            drops.add(right_key)
        df = df.drop(drops, axis=1)
        print(df.columns)
        return df

def match_allnames(xf0, xf1):

    """Finds candidate Matches between two DataFrames based on the
    *allnames* field.

    xf0, xf1: ExtDf
    """

    lcols = levenshtein_cols(
        xf0.df[xf0.prefix+'allnames'],
        xf1.df[xf1.prefix+'allnames']) \
        .rename(columns={'ix0':xf0.prefix+'ix', 'ix1':xf1.prefix+'ix'})

    # Only keep exact matches.  Problem is... inexact matches are fooled by
    # "XGlacier N", "XGlacier E", etc.
    lcols = lcols[lcols['lev']==1.0]

    dfx0 = xf0.df.loc[lcols[xf0.prefix+'ix']]
    dfx0.index = lcols.index

    dfx1 = xf1.df.loc[lcols[xf1.prefix+'ix']]
    dfx1.index = lcols.index

    xcols = lcols.copy()
    xcols[xf0.prefix+'key'] = dfx0[xf0.prefix+'key']
    xcols[xf1.prefix+'key'] = dfx1[xf1.prefix+'key']
    xcols[xf0.prefix+'allnames'] = dfx0[xf0.prefix+'allnames']
    xcols[xf1.prefix+'allnames'] = dfx1[xf1.prefix+'allnames']

    return Match((xf0,xf1), (xf0.prefix+'allnames', xf1.prefix+'allnames'), xcols)

def polys_overlapping_points(points_s, polys, poly_outs, poly_label='poly'):

    """Given a list of points and polygons... finds which polygons overlap
    each point.

    points_s: pd.Series(shapely.geometry.Point)
        Pandas Series containing the Points (with index)
    polys: [poly, ...]
        List of shapely.geometry.Polygon
    poly_outs: [x, ...]
        Item to place in resulting DataFrame in place of the Polygon.
        Could be the same as the polygon.

    """

    # Load the grids 
    out_s = list()
    for poly,poly_out in zip(polys,poly_outs):

        # Find intersections between terminus locations and this grid
        # NOTE: intersects includes selections.index
        intersects = points_s[points_s.map(lambda p: poly.intersects(p))]

        out_s.append(pd.Series(index=intersects.index, data=[poly_out] * len(intersects),name=poly_label))

    grids = pd.concat(out_s, axis=0)
    return grids

def match_point_poly(left, left_point, right, right_poly, left_cols=None, right_cols=None):
    """Creates a Match object, looking for points in <left> contained in polygon in <right>
    left, right: ExtDf
        Datasets to match
    left_point: str
        Column in left to join.  Must be of type POINT
    right_poly: str
        Column in right to join.  Must be of type POLYGON
    left_cols, right_cols:
        Additional columns from left and right to include in the match dataframe
    """

    keyseries = polys_overlapping_points(left.df[left_point], right.df[right_poly], right.df.index)#mwb.df['mwb_key'])
    keyseries.name = right.prefix+'ix'
    matchdf = keyseries.reset_index().rename(columns={'index':left.prefix+'ix'})
    # Add in extra cols
    for xcols,xf in zip((left_cols,right_cols), (left,right)):
        key = xf.prefix+'key'
        if xcols is None:
            xcols = [key]
        elif key not in xcols:
            xcols = [key] + xcols

        matchdf = pd.merge(matchdf, xf.df[xcols],
            how='left', left_on=xf.prefix+'ix', right_index=True)

    return Match((left,right), (left_point, right_poly), matchdf)


# ============================================================
# Readers fro specific datasets

def read_bkm15(map_wkt):
    ##### Brief communication: Getting Greenland’s glaciers right – a new data set of all official Greenlandic glacier names
    # Bjørk, Kruse, Michaelsen, 2015 [BKM15]
    # RGI_ID = Randolph Glacier Inventory: not on GrIS
    # GLIMS_ID = Global Land Ice Measurements from Space: not on GrIS

    df = pd.read_csv('data/GreenlandGlacierNames/tc-9-2215-2015-supplement.csv')

    # Keep only glaciers on the ice sheet (285 of them)
    df = df[df['Type'] == 'GrIS']
    #assert(len(df) == 285)

    # Drop columns not useful for GrIS glaciers
    df = df.drop(['RGI_ID', 'GLIMS_ID', 'RGI_LON', 'RGI_LAT', 'Type'], axis=1) \
        .rename(columns={'ID' : 'id', 'LAT' : 'lat', 'LON' : 'lon',
        'New_Greenl' : 'new_greenl_name', 'Old_Greenl' : 'old_greenl_name', 'Foreign_na' : 'foreign_name',
        'Official_n' : 'official_name', 'Alternativ' : 'alt'})

    return ExtDf(df, map_wkt,
        add_prefix='bkm15_',
        keycols=['id'],
        lonlat=('lon','lat'),
        namecols=['official_name', 'new_greenl_name', 'old_greenl_name', 'foreign_name', 'alt'])


def read_m17(map_wkt):
    # Morlighem et al, 2017
    # BedMachine v3 paper

    colnames,units = sep_colnames(
        ['id', 'name', 'lat', 'lon', ('speed', 'm a-1'), ('drainage', 'km^2'),
        'mc', 'bathy',
        ('ice_front_depth_b2013','m'), ('ice_front_depth_rtopo2','m'), ('ice_front_depth','m'),
        'contconn300_b2013', 'contcon300_rtopo2', 'contcon300',
        'contconn200_b2013', 'contcon200_rtopo2', 'contcon200',
        'bathy_coverage'])
    df = pd.read_csv('data/morlighem2017/TableS1.csv', skiprows=3,
        usecols=list(range(len(colnames))), names=colnames) \
        .drop('id', axis=1)
    df = df[df.name != 'TOTAL']

    return ExtDf(df, map_wkt,
        add_prefix='m17_',
        units=units,
        keycols=['name','lon','lat'],
        lonlat=('lon','lat'),
        namecols=['name'])

def read_w21(map_wkt):
    # w21: Reads the dataset:
    # data/GreenlandGlacierStats/
    # 
    # From the paper:
    #
    # Ocean forcing drives glacier retreat in Greenland
    # Copyright © 2021
    #   Michael Wood1,2*, Eric Rignot1,2, Ian Fenty2, Lu An1, Anders Bjørk3,
    #   Michiel van den Broeke4, 11251 Cilan Cai , Emily Kane , Dimitris
    #   Menemenlis , Romain Millan , Mathieu Morlighem , Jeremie
    #   Mouginot1,5, Brice Noël4, Bernd Scheuchl1, Isabella Velicogna1,2,
    #   Josh K. Willis2, Hong Zhang2

    ddir = os.path.join('data', 'GreenlandGlacierStats')

    keepcols = [
        ('Glacier (Popular Name)', 'popular_name'),
        ('Glacier (Greenlandic Name)', 'greenlandic_name'),
        ('Coast', 'coast'),
        ('Categorization', 'category'),
        ('Qr (km)', ('Qr','km', 'float')),
        ('Qf (km)', ('Qf', 'km', 'float')),
        ('Qm (km)', ('Qm', 'km', 'float')),
        ('Qs (km)', ('Qs', 'km', 'float')),
        ('Qc (Inferred) (km)', ('Qc_inferred', 'km', 'float')),
        ('qm (m/d)', ('qm', 'm d-1', 'float')),
        ('qf (m/d)', ('qf', 'm d-1', 'float')),
        ('qc (m/d)', ('qc', 'm d-1', 'float')),
        ('Mean Depth (m)', ('mean_depth', 'm', 'float')),
        ('Min Depth (m)', ('min_depth', 'm', 'float')),
        ('Quality', 'quality_str'),
        ('1992-2017 (Grounded, km2)', ('area_grounded_1992_2017', 'km^2', 'float')),
        ('1992-1997 (Grounded, km2)', ('area_grounded_1992_1997', 'km^2', 'float')),
        ('1998-2007 (Grounded, km2)', ('area_grounded_1998_2007', 'km^2', 'float')),
        ('2008-2017 (Grounded, km2)', ('area_grounded_2008_2017', 'km^2', 'float')),
        ('Mean Fjord Width (km)', ('mean_fjord_width', 'km', 'float')),
        ('1992-2017 (Grounded, km)', ('length_grounded_1992_2017', 'km', 'float')),
        ('1992-1997 (Grounded, km)', ('length_grounded_1992_1997', 'km', 'float')),
        ('1998-2007 (Grounded, km)', ('length_grounded_1998_2007', 'km', 'float')),
        ('2008-2017 (Grounded, km)', ('length_grounded_2008_2017', 'km', 'float')),
        ('Ocean Model Sample Area (See Figure 1)', 'ocean_model_sample_area'),
        ('1992-2017 (degrees C)', ('mean_TF_1992-2017', 'degC', 'float')),
        ('1992-1997 (degrees C)', ('mean_TF_1992-1997', 'degC', 'float')),
        ('1998-2007 (degrees C)', ('mean_TF_1998-2007', 'degC', 'float')),
        ('2008-2017 (degrees C)', ('mean_TF_2008-2017', 'degC', 'float')),
        ('1992-2017 (10^6 m^3/day)', ('subglacial_discharge_1992_2017', 'hm^3 d-1', 'float')),
        ('1992-1997 (10^6 m^3/day)', ('subglacial_discharge_1992_1997', 'hm^3 d-1', 'float')),
        ('1998-2007 (10^6 m^3/day)', ('subglacial_discharge_1998_2007', 'hm^3 d-1', 'float')),
        ('2008-2017 (10^6 m^3/day)', ('subglacial_discharge_2008_2017', 'hm^3 d-1', 'float')),
        ('Mean Cross-sectional Area (km^2)', ('mean_xsection_area', 'km^2', 'float')),
        ('1992-2017 (m/d)', ('mean_undercuttong_1992_2017', 'm d-1', 'float')),
        ('1992-1997 (m/d)', ('mean_undercuttong_1992_1997', 'm d-1', 'float')),
        ('1998-2007 (m/d)', ('mean_undercuttong_1998_2007', 'm d-1', 'float')),
        ('2008-2017 (m/d)', ('mean_undercuttong_2008_2017', 'm d-1', 'float')),
        ('Mean Undercutting Rate Uncertainty (%)', ('mean_undercutting_uncertainty', '%', 'float')),
        ('Flux Basin Mouginot et al 2019 (1)', 'flux_basin_mouginot_2019'),
        ('Mean Discharge (Gt/yr, 1992-2017)', ('mean_discharge', 'Gt a-1', 'float')),
        ('Mean Mass Balance (Gt/yr, 1992-2017)', ('mean_mass_balance', 'Gt a-1', 'float')),
        ('Reference SMB 1961-1990 (Gt/yr, 1961-1990)', ('reference_smb_1961_1990', 'Gt a-1', 'float')),
    ]


    dfs = list()
    for iroot in ('CW', 'SW', 'SE', 'CE', 'NE', 'N', 'NW'):
        ifname = os.path.join(ddir, '{}.csv'.format(iroot))
        # https://stackoverflow.com/questions/4869189/how-to-transpose-a-dataset-in-a-csv-file
        rows = list(zip(*csv.reader(open(ifname, "r"))))

        # Split up file
        columns = ['{} {}'.format(a,b).replace(':','').strip() for a,b in zip(rows[0], rows[1])]
#        for x in columns:
#            print("'{}'".format(x))
#        units = rows[1]
        data = rows[2:]

        # Create dataframe
        df0 = pd.DataFrame(data, columns = columns)

        col_units = dict()
        df1_cols = dict()
        for col0,xx in keepcols:
            # Interpret convention for keepcols array
            if isinstance(xx,tuple):
                col1,units,dtype = xx
                col1 = col1
                col_units['w21_' + col1] = units
            else:
                col1 = xx
                units = None
                dtype = 'object'

            # Fish out old column
            col = df0[col0]
            if dtype == 'object':
                col.replace('N/A', '', inplace=True)
                col.replace('--', np.nan, inplace=True)
            elif dtype == 'float':
                col.replace('--', np.nan, inplace=True)
                col.replace('#DIV/0!', np.nan, inplace=True)
                col.replace('', np.nan, inplace=True)
            #print(col)

            # Construct new set of columns
            df1_cols[col1] = col.astype(dtype)#.rename(col1)

        df = pd.DataFrame(df1_cols)

        # Remove wrong rows
        df = df[~df.popular_name.str.contains('Total')]
        df = df[~df.popular_name.str.contains('Mean')]

        #print(df.columns.values.tolist())
        dfs.append(df)

    df = pd.concat(dfs).reset_index(drop=True)


    #df.columns = ['w21_' + str(x) for x in df.columns]


    return ExtDf(df, map_wkt, add_prefix='w21_', units=col_units,
        keycols=['popular_name', 'flux_basin_mouginot_2019'],
        namecols=['popular_name', 'greenlandic_name'])

def read_mwb(map_wkt):

    # mwb: Greenland Basins
    #If you want to use the basins in a publication, we will need to contact Micheal Wood
    # Name_AC is from Micheal, Name is from Eric Rignot, gl_type is the glacier type: TW: tide-water, LT: land terminating. UGID is a unique identifier that I use to identify glaciers in my scripts.
    # NOTE: mwb_basin == w21_coast

    df = pd.DataFrame(shputil.read('data/GreenlandBasins/Greenland_Basins_PS_v1.4.2c.shp', map_wkt)) \
        .drop('_shape0', axis=1) \
        .rename(columns={'basin':'basin', 'Name_AC':'name_ac', 'gl_type':'gl_type',
        'id':'id', 'id2':'id2', 'UGID':'ugid', 'Name':'name', '_shape':'basin_poly'})
#    print(df.columns)

    # Remove the "ICE_CAPS_NW" polygon
    df = df[df['name_ac'] != 'ICE_CAPS_NW']

    return ExtDf(df, map_wkt, add_prefix='mwb_',
        units={'basin_poly': 'm'},
        keycols=['name_ac'],
        namecols=['name_ac', 'name'])

# =====================================================================

# Standard Greenland Stereographic Projection
map_wkt = "PROJCS[\"WGS 84 / NSIDC Sea Ice Polar Stereographic North\",GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563,AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",0.0174532925199433,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4326\"]],PROJECTION[\"Polar_Stereographic\"],PARAMETER[\"latitude_of_origin\",70],PARAMETER[\"central_meridian\",-45],PARAMETER[\"false_easting\",0],PARAMETER[\"false_northing\",0],UNIT[\"metre\",1,AUTHORITY[\"EPSG\",\"9001\"]],AXIS[\"Easting\",SOUTH],AXIS[\"Northing\",SOUTH],AUTHORITY[\"EPSG\",\"3413\"]]"

    

