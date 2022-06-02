import matplotlib
#matplotlib.use('TkAgg')
#matplotlib.rcParams['interactive'] = True

import numpy as np
from scipy import signal

sig = np.repeat([0., 1., 0.], 100)
#win = signal.hann(50)
win = np.repeat([0.,1.,0.], 10)
filtered = signal.convolve(sig, win, mode='same') / sum(win)

import matplotlib.pyplot as plt
fig, (ax_orig, ax_win, ax_filt) = plt.subplots(3, 1, sharex=True)
ax_orig.plot(sig)
ax_orig.set_title('Original pulse')
ax_orig.margins(0, 0.1)
ax_win.plot(win)
ax_win.set_title('Filter impulse response')
ax_win.margins(0, 0.1)
ax_filt.plot(filtered)
ax_filt.set_title('Filtered signal')
ax_filt.margins(0, 0.1)
fig.tight_layout()
fig.show()

plt.pause(10000)
