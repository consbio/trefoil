# Clover
Because today might be your lucky day.

Geospatial operations with NetCDF files and numpy arrays.


## Why?
We needed a library to consolidate a series of utility scripts and general
geospatial operations on NetCDF and numpy arrays.  We found we were creating
a lot of purpose built scripts for other projects involving lots of processing
of NetCDF climate and model outputs.  Where possible, we have been pulling out
general patterns and placing them here.  When we looked for existing work, we 
didn't find anything that quite met our needs, with a clean API and no strong 
assertions about data model or compliance with CF-conventions 
(we aspire to conventions, but not all data meet them).  

Specifically, we want to provide:

* simple and fast API for rendering numpy arrays to images
* simple API to provide utility functions that make working with NetCDF data
easier
* simple command line interface to make common operations easy and portable
* analysis operations to simplify using geometries alongside raster data
* analysis operations to summarize across various dimensions of spatial and 
temporal-spatial datasets (anything more than 3 dimensions makes our heads hurt!)

We are trying to avoid reimplementing anything well-handled elsewhere.  Where 
possible, we contribute functionality to other libraries (e.g., [rasterio](https://github.com/mapbox/rasterio))
where we think that the functionality is general enough not to depend on
living within clover.


## Where is it being used?
This is a core dependency for ncdjango (public repo coming soon), our 
Django-based NetCDF map server.


## Work in progress
This is still under active development, as we have time and need.  All APIs are
subject to change until we hit version 1.0.

Specifically, we need to work on:

* standardizing API patterns
* documentation
* test coverage and correctness
* roadmap


## Contributors:

* [Brendan C. Ward](https://github.com/brendan-ward)
* [Nik Stevenson-Molnar](https://github.com/nikmolnar)

With inspiration from [Tim Sheehan](http://consbio.org/people/staff/tim-sheehan) 
and [Ken Ferschweiler](http://consbio.org/people/staff/ken-ferschweiler).


## See Also:

* [rasterio](https://github.com/mapbox/rasterio): Geospatial I/O and operations on rasters, done right.
* [OCGIS](https://github.com/NCPP/ocgis): Geoprocessing on CF compatible climate datasets.
* [scikit-image](http://scikit-image.org/): Python image processing
* [python-raster-stats](https://github.com/perrygeo/python-raster-stats): Summary statistics of rasters using geometries