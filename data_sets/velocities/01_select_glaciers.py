import os
import pickle
import uafgi.data
from uafgi import stability

select = stability.select_glaciers()

select.to_pickle(uafgi.data.join_outputs('stability/01_select.dfx'))

# Save to file (don't worry about make for now...)
#os.makedirs(uafgi.data.join_outputs('stability'), exist_ok=True)
#with open(uafgi.data.join_outputs('stability/01_select.dfx'), 'wb') as out:
#    pickle.dump(select, out)
#select.df.to_pickle(uafgi.data.join_outputs('stability/01_select.df'))
#seldf = select.df.drop(['cf20_locs', 'ns642_points', 'ns481_poly'], axis=1)
#seldf.to_csv(uafgi.data.join_outputs('stability/01_select.csv'))
