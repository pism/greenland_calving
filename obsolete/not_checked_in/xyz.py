# apply linear regresion using numpy
def linReg(x, y):
    '''linear regression using numpy starting from two one dimensional numpy arrays'''
    A = np.vstack([x, np.ones(len(x))]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    return pd.Series({'slope':slope, 'intercept': intercept})

def lrr(row):
    """Linear regression on a row"""
    seconds0 = np.array(list(x.timestamp() for x in row.stab_time))
    ice0 = np.array(row.stab_ice) / (row.w21_mean_fjord_width * 1000.)
    
    seconds = seconds0 - seconds0[0]
    days = seconds / 86400.
    years = days / 365.
    ice = ice0 - ice0[0]    
    keep = (seconds > 30*86400)

    return linReg(years, ice)[['slope']]

def advret_rate(df1):
    """Interpolates timeseries during each (year,glacier) run to
    produce an experimental advance/retreat rate over the course of the run.
    
    df1: (year, ns642_GlacierID, sigma_max)
        The original experiment dataframe
    Returns:
        Series of the rate of advance / retreat for each model run in df1
        
    NOTE: To graph per-glacier, do:
        df['advret_rate'] = advret_rate(df)
        df.pivot(index='sigma_max', columns='year', values='advret_rate').plot(figsize=(10,6))
    """    
    return df1.apply(lrr, axis=1)

def sigma_eq(df1):
    """Determines the slope and y-intercept of different values of sigma_max for each year.

    df1: (year, ns642_GlacierID, sigma_max)
        The original experiment dataframe, with advret_rate column added (see above)
    Returns: DatFrame(year, ns642_GlacierID)
        sigma_eq:
            sigma_max value that results in no advance/retreat
        dadv_dsigma:
            Change in advret_rate vs. change in sigma_max
    """
    
    dfg = df1.groupby(['ns642_GlacierID', 'year'])
    rows = list()
    for (glacier_id, year), dfx in dfg:
        row = {'ns642_GlacierID' : glacier_id, 'year' : year}
        row['poly_abc'] = abc = np.polyfit(dfx['sigma_max'], dfx['advret_rate'], 3)
        ab = np.polyder(abc)     # Derivative of abc
        rootsx = [np.real(x) for x in np.roots(abc) if ~np.iscomplex(x) and x >= 100000 and x <= 500000]
        if len(rootsx) > 0:
            row['sigma_eq'] = root = rootsx[0]
            row['dadv_dsigma'] = np.poly1d(ab)(root)
        rows.append(row)

    return pd.DataFrame(rows)

def glacier_stats(df):
    df['advret_rate'] = advret_rate(df)
    rs = sigma_eq(df)

    # Compute the plot (Actually plot each group of this separatley)
    plotdf = df.pivot(index=['ns642_GlacierID', 'sigma_max'], columns='year', values='advret_rate')

    # Compute stats on a (glacier_id) basis
    stats=rs.groupby(['ns642_GlacierID']).agg({'sigma_eq': ['mean','std'], 'dadv_dsigma': ['mean','std']})
    print(stats.columns)
    # https://stackoverflow.com/questions/14507794/pandas-how-to-flatten-a-hierarchical-index-in-columns
    stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
    #stats = xx.reset_index()

    return plotdf,stats



