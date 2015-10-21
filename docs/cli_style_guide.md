# Command Line Style Guide

In-progress work to standardize use of arguments and options across the command
line tools.


## Arguments
TODO


## Options

Multi-word options should be joined with a hyphen, not an underscore:
`--src-crs`

Any operation that produces a new NetCDF dataset as output shall support NetCDF3
format (required for use in ArcGIS, etc) using a flag:
`--netcdf3`


TODO: decide how to handle filename and variable inputs: either separate options
or consolidated into a single option using shorthand notation: `filename:variable`

TODO: develop consistent approach to precision: number of decimal places or 
significant digits.

TODO: standardize use of  `--zip` and `--pack` options.
