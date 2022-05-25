# Simple description of how to do certain common tasks

# Download data into the data/ directory.
# Or, just manually symlink the data/ directory from somewhere else.
download:
	cd data; python ../nsidc-download_NSIDC_W69.10N.py

clean:
	rm -rf outputs
