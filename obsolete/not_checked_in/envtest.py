import os

for key in sorted(os.environ.keys()):
    print('{}={}'.format(key,os.environ[key]))
