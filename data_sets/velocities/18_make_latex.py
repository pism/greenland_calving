import pandas as pd

slfit = pd.read_pickle('16_slfit.df')
groups = (
    ('Puisortoq N', 'Puisortoq S', 'Eqip Sermia'),
    ('Gyldenlove N', 'Kujalleq', 'Lille'),
    ('AP Bernstorff', 'Cornell N', 'Inngia', 'Hayes NN')
)

slfit = slfit.set_index('w21t_Glacier')
for group in groups:
    for name in group:
        row = slfit.loc[name]
        resid_lr = row.resid_lr
        R2 = resid_lr.rvalue * resid_lr.rvalue    # Coeff of Determination = (Pearsons r value)^2

        ostr = r'\glacierrow{%s}{%d}{%s}{%d}{%0.3f} \\' % (
            row['ns481_grid'].replace('.', ''),
            row.w21t_glacier_number,
            name,
            round(R2*100), resid_lr.pvalue)
        print(ostr)
    print()



