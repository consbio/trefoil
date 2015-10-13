# Clover's Command Line Interface

*Note: under active development.  Expect new commands and options.*

Use `--help` option on any command for more information about how to use that
command.

Nearly throughout, clover assumes that data have a 2 dimensional geospatial 
component (y, x) and an optional temporal component.


```
> clover --help

Usage: clover [OPTIONS] COMMAND [ARGS]...

  Command line interface for clover

Options:
  --help  Show this message and exit.

Commands:
  bin_ts         Bin time series data by interval
  delta          Calculate delta values into new datasets based on a baseline
  describe       Describe netCDF files
  extract        Extract variables from files into new datasets in a new
                 directory
  mask           Create a NetCDF mask from a shapefile
  render_netcdf  Render netcdf files to images
  render_tif     Render Single-Band GeoTIFF files to images
  stats          Display statistics for variables within netCDF files
  to_netcdf      Convert rasters to NetCDF
  variables      List variables in netCDF file
  warp           Warp NetCDF files to match a template
```

## Bin time series

*experimental, subject to change*

`bin_ts` will bin time series data by an interval, for example, to turn an 
annual time series into a decadal time series.

```
> clover bin_ts --help

Usage: clover bin_ts [OPTIONS] FILES VARIABLE

  Bin time series data by an interval, according to a statistic.

Options:
  --outdir TEXT           Output directory
  --statistic [mean|sum]  Statistic for aggregating data  [default: mean]
  --interval INTEGER      Interval in number of time steps for aggregating
                          data  [default: 1]
  --zip                   Use zlib compression of data and coordinate
                          variables
```

Example:
`> clover bin_ts input.nc in_var --interval 10`

Assuming input.nc has a 3rd dimension 50 steps long, this will create a new 
dataset called `input_bin.nc` in the same directory, with 5 steps, each of which
will have the average (by default) of the values for `in_var` for each 10 step 
interval of the input.


## Calculate delta

*experimental, subject to change*

`delta` will calculate the delta as either a difference or proportion for each
input file (for each time period, if they have a temporal dimension).

```
> clover delta --help

Usage: clover delta [OPTIONS] BASELINE FILES VARIABLE

Options:
  --bidx INTEGER  Index in baseline if 3D (default 0)
  --proportion    Use proportion instead of difference
  --outdir TEXT   Output directory
```


## Describe a NetCDF file

`describe` will produce a structured output describing attributes, dimensions, 
and variables in this dataset, along with information about spatial and temporal 
extents if they can be determined.

Example: 
`> clover describe input.nc`




## Extract variables into new files

*due for an overhaul, best to avoid using this for now*


## Create a mask from a shapefile

`mask` will create a NetCDF file with a binary mask created from features in a 
shapefile.  Currently uses a template NetCDF file to determine the geospatial
dimensions and projection against which to rasterize the shapefile.

This is typically used to mask in areas within an area of interest, and mask out
areas that are outside.

```
> clover mask --help

Usage: clover mask [OPTIONS] INPUT OUTPUT

  Create a NetCDF mask from a shapefile.

  Values are equivalent to a numpy mask: 0 for unmasked areas, and 1 for
  masked areas.

  Template NetCDF dataset must have a valid projection defined or be
  inferred from dimensions (e.g., lat / long)

Options:
  --variable TEXT  Name of output mask variable
  --like PATH      Template NetCDF dataset  [required]
  --netcdf3        Output in NetCDF3 version instead of NetCDF4
  --all-touched    Turn all touched pixels into mask (otherwise only pixels
                   with centroid in features)
  --zip            Use zlib compression of data and coordinate variables
```

Example:
`> clover mask my_shapefile.shp mask.nc --like template.nc --all-touched`

Will produce a mask that is `False` in all pixels covered by the shapefile's
features, and `True` everywhere else.


## Rendering a NetCDF variable to images

*options subject to change without notice*

`render_netcdf` renders a variable into PNG files.  Several options are available
to control the output.

One interesting usage is with the `--map` option, which opens a Leaflet-based
map viewer in your browser with the images from this file spatially anchored
over the map.

```
> clover render_netcdf --help

Usage: clover render_netcdf [OPTIONS] FILENAME_PATTERN VARIABLE
                            OUTPUT_DIRECTORY

  Render netcdf files to images.

  colormap is ignored if renderer_file is provided

  --dst-crs is ignored if using --map option (always uses EPSG:3857

  If no colormap or palette is provided, a default palette may be chosen
  based on the name of the variable.

  If provided, mask must be 1 for areas to be masked out, and 0 otherwise.
  It must be in the same CRS as the input datasets, and have the same spatial
  dimensions.

Options:
  --renderer_file PATH            File containing renderer JSON
  --save PATH                     Save renderer to renderer_file
  --renderer_type [stretched|classified]
                                  Name of renderer.  [default: stretched]
  --colormap TEXT                 Provide colormap as comma-separated lookup
                                  of value to hex color code.  (Example:
                                  -1:#FF0000,1:#0000FF)
  --fill FLOAT                    Fill value (will be rendered as transparent)
  --colorspace [hsv|rgb]          Color interpolation colorspace
  --palette TEXT                  Palettable color palette (Example:
                                  colorbrewer.sequential.Blues_3)
  --palette_stretch TEXT          Value range over which to apply the palette
                                  when using stretched renderer (comma-
                                  separated)  [default: min,max]
  --scale FLOAT                   Scale factor for data pixel to screen pixel
                                  size
  --id_variable TEXT              ID variable used to provide IDs during image
                                  generation.  Must be of same dimensionality
                                  as first dimension of variable (example:
                                  time).  Guessed from the 3rd dimension
  --lh INTEGER                    Height of the legend in pixels [default:
                                  150]
  --legend_breaks INTEGER         Number of breaks to show on legend for
                                  stretched renderer
  --legend_ticks TEXT             Legend tick values for stretched renderer
  --legend_precision INTEGER      Number of decimal places of precision for
                                  legend labels  [default: 2]
  --format [png|jpg|webp]         [default: png]
  --src-crs, --src_crs TEXT       Source coordinate reference system (limited
                                  to EPSG codes, e.g., EPSG:4326).  Will be
                                  read from file if not provided.
  --dst-crs, --dst_crs TEXT       Destination coordinate reference system
  --res FLOAT                     Destination pixel resolution in destination
                                  coordinate system units
  --resampling [nearest|cubic|lanczos|mode]
                                  Resampling method for reprojection (default:
                                  nearest
  --anchors                       Print anchor coordinates for use in Leaflet
                                  ImageOverlay
  --map                           Open in interactive map
  --mask TEXT                     Mask dataset:variable (e.g., mask.nc:mask).
                                  Mask variable assumed to be named "mask"
                                  unless otherwise provided
```

Example:
`> clover render_netcdf inputs_*.nc in_var img --colormap min:#00F,max:#F00`

Will render each time slice of each of the inputs to an image, using a blue to
red stretched renderer (in HSV color space, by default), stretched from the
minimum to the maximum values across all datasets.


## Render a NetCDF-based EEMS model to a map

`map_eems` creates a Leaflet-based web map of a NetCDF-based EEMS model.  
It uses blue-yellow-red color ramp for data variables in fuzzy space, and a
black to white color ramp for input data variables.

Note: the same resampling method applies to all variables, and may not be
appropriate for all variables.  Use `nearest` if any variables are categorical.


```
> clover map_eems --help
Usage: clover map_eems [OPTIONS] EEMS_FILE

  Render a NetCDF EEMS model to a web map.

Options:
  --scale FLOAT                   Scale factor for data pixel to screen pixel
                                  size
  --format [png|jpg|webp]         [default: png]
  --src-crs, --src_crs TEXT       Source coordinate reference system (limited
                                  to EPSG codes, e.g., EPSG:4326).  Will be
                                  read from file if not provided.
  --resampling [nearest|cubic|lanczos|mode]
                                  Resampling method for reprojection (default:
                                  nearest
```


## Render a GeoTIFF

*likely to go away or be refactored in a major way*


## Display statistics for NetCDF variables

`stats` displays simple statistics (min, max, average) for variables across
a series of files.

Variables can be input as a comma-delimited list.

Can be optionally masked.


```
> clover stats --help

Usage: clover stats [OPTIONS] FILES VARIABLES

  Calculate statistics for each variable across all files

Options:
  --mask TEXT  Mask dataset:variable (e.g., mask.nc:mask).  Mask variable
               assumed to be named "mask" unless otherwise provided
```

Example:
`> clover stats input.nc in_var1,in_var2`


## Convert rasters to NetCDF

`to_netcdf` will convert from any raster that can be read with `rasterio`
into a NetCDF file with appropriate geospatial dimensions, and optional
temporal dimension.  It will automatically infer data type and coordinate
reference system, if possible.  It currently uses the Python
[strptime](https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior)
format for parsing dates, but limited to 2 and 4 digit years only (`%Y` and `%y`).

A common use case is to convert a series of ArcASCII files into a NetCDF
file with geospatial and temporal dimensions.


```
> clover to_netcdf --help

Usage: clover to_netcdf [OPTIONS] FILES OUTPUT VARIABLE

  Convert rasters to NetCDF and stack them according to a dimension.

  X and Y dimension names will be named according to the source projection
  (lon, lat if geographic projection, x, y otherwise) unless specified.

  Will overwrite an existing NetCDF file.

Options:
  --dtype [float32|float64|int8|int16|int32|uint8|uint16|uint32]
                                  Data type of output variable.  Will be
                                  inferred from input raster if not provided.
  --src-crs TEXT                  Source coordinate reference system (limited
                                  to EPSG codes, e.g., EPSG:4326).  Will be
                                  read from file if not provided.
  --x TEXT                        Name of x dimension and variable (default:
                                  lon or x)
  --y TEXT                        Name of y dimension and variable (default:
                                  lat or y)
  --z TEXT                        Name of z dimension and variable  [default:
                                  time]
  --netcdf3                       Output in NetCDF3 version instead of NetCDF4
  --zip                           Use zlib compression of data and coordinate
                                  variables
  --packed                        Pack floating point values into an integer
                                  (will lose precision)
  --xy-dtype [float32|float64]    Data type of spatial coordinate variables.
                                  [default: float32]
  --calendar TEXT                 Calendar to use if z dimension is a date
                                  type  [default: standard]
```

Example:
`> clover to_netcdf inputs_*.asc my_var --dtype uint8 --src-crs EPSG:4326`

Will produce a NetCDF file with longitude and latitude dimensions, and a Z
dimension that is of the same size as the number of files that meet the filename
pattern.  Files are stacked in the order they are listed in the directory
(alphabetically).  The data variable `my_var` will contain the data read from
the ArcASCII files, converted to unsigned 8 bit integers.

`> clover to_netcdf inputs_%Y.asc my_var --dtype uint8 --src-crs EPSG:4326`

Will produce a similar output, but will use the `%Y` expression to match 4 digit
years and add those to a temporal dimension and coordinate variable, stored
according to CF conventions (in days since the first year of the series, based
on the input calendar).


## List variables in a NetCDF file

`variables` lists the data and coordinate variables within the NetCDF dataset.

Example:
`> clover variables input.nc`


## Reproject a variable in a NetCDF file

`warp` will reproject one or more data variables in a NetCDF file to a new
coordinate reference system, using a template dataset to establish the 
geospatial domain for output.  Files will be given the same name as the inputs
in the output directory.


```
> clover warp --help

Usage: clover warp [OPTIONS] FILENAME_PATTERN OUTPUT_DIRECTORY

Options:
  --variables TEXT                comma-delimited list of variables to warp.
                                  Default: all data variables
  --src-crs TEXT                  Source Coordinate Reference System (only
                                  used if none found in source dataset)
                                  [default: EPSG:4326]
  --like PATH                     Template dataset  [required]
  --resampling [nearest|cubic|lanczos|mode]
                                  Resampling method for reprojection
                                  [default: nearest]
```

Example:
`> clover warp input_geographic.nc output --like template_mercator.nc`
