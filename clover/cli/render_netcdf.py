"""
Render a set of NetCDF files to images.

Stretched renderers may have one of the following colormap values:
1.0 (absolute)
max (calculate max across datasets)
0.5*max (calculate max across datasets, and multiply by value)
"""


# import sys
# import logging
# logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

import os
import glob
from itertools import product
from collections import Iterable
import click
import json
from math import ceil
from netCDF4 import Dataset
import numpy
from PIL.Image import ANTIALIAS
from pyproj import Proj
from affine import Affine

import rasterio
from rasterio import crs
from rasterio.warp import reproject, RESAMPLING

from clover.utilities.color import Color
from clover.render.renderers.stretched import StretchedRenderer
from clover.render.renderers.utilities import renderer_from_dict
from clover.netcdf.utilities import collect_statistics
from clover.netcdf.variable import SpatialCoordinateVariables
from clover.netcdf.crs import get_crs
from clover.cli import cli



def render_image(renderer, data, filename, scale=1, reproject_kwargs=None):
    if reproject_kwargs is not None:

        with rasterio.drivers():
            out = numpy.empty(shape=reproject_kwargs['dst_shape'], dtype=data.dtype)
            out.fill(data.fill_value)
            reproject(data, out, **reproject_kwargs)
            # Reapply mask
            data = numpy.ma.masked_array(out, mask=out == data.fill_value)

    img = renderer.render_image(data)
    if scale != 1:
        img = img.resize((numpy.array(data.shape[::-1]) * scale).astype(numpy.uint), ANTIALIAS)
    img.save(filename)


@cli.command(short_help="Render netcdf files to images")
@click.argument('filename_pattern')
@click.argument('variable')
@click.argument('output_directory', type=click.Path())
@click.option('--renderer_file', help='File containing renderer JSON', type=click.File('r'))
@click.option('--renderer_type', default='stretched', help='Name of renderer [default: stretched].  (other types not yet implemented)')
@click.option('--colormap', default='min:#000000,max:#FFFFFF', help='Provide colormap as comma-separated lookup of value to hex color code.  (Example: -1:#FF0000,1:#0000FF) [default: min:#000000,max:#FFFFFF]')
@click.option('--colorspace', default='hsv', type=click.Choice(['hsv', 'rgb']), help='Color interpolation colorspace')
@click.option('--scale', default=1.0, help='Scale factor for data pixel to screen pixel size')
@click.option('--id_variable', help='ID variable used to provide IDs during image generation.  Must be of same dimensionality as first dimension of variable (example: time)')
@click.option('--lh', default=150, help='Height of the legend in pixels [default: 150]')
@click.option('--legend_breaks', default=None, type=click.INT, help='Number of breaks to show on legend for stretched renderer')
@click.option('--legend_ticks', default=None, type=click.STRING, help='Legend tick values for stretched renderer')
# Projection related options
@click.option('--src_crs', default=None, type=click.STRING, help='Source coordinate reference system (limited to EPSG codes, e.g., EPSG:4326).  Will be read from file if not provided.')
@click.option('--dst_crs', default=None, type=click.STRING, help='Destination coordinate reference system')
@click.option('--res', default=None, type=click.FLOAT, help='Destination pixel resolution in destination coordinate system units' )
@click.option('--resampling', default='nearest', type=click.Choice(('nearest', 'cubic', 'lanczos', 'mode')), help='Resampling method for reprojection (default: nearest')
# TODO: option with transform info if not a geo format
def render_netcdf(
        filename_pattern,
        variable,
        output_directory,
        renderer_file,
        renderer_type,
        colormap,
        colorspace,
        scale,
        id_variable,
        lh,
        legend_breaks,
        legend_ticks,
        src_crs,
        dst_crs,
        res,
        resampling):
    """Render netcdf files to images"""

    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='filename_pattern', param_hint='FILENAME_PATTERN')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if renderer_file is not None:
        # see https://bitbucket.org/databasin/ncdjango/wiki/Home for format
        renderer_dict = json.loads(renderer_file.read())

        if variable in renderer_dict and not 'colors' in renderer_dict:
            renderer_dict = renderer_dict[variable]

        if renderer_dict['type'] == 'stretched':
            colors = ','.join([str(c[0]) for c in renderer_dict['colors']])
            if 'min' in colors or 'max' in colors or 'mean' in colors:
                statistics = collect_statistics(filenames, (variable,))[variable]
                for entry in renderer_dict['colors']:
                    if isinstance(entry[0], basestring):
                        if entry[0] in ('min', 'max', 'mean'):
                            entry[0] = statistics[entry[0]]
                        elif '*' in entry[0]:
                            rel_value, statistic = entry[0].split('*')
                            entry[0] = float(rel_value) * statistics[statistic]

        renderer = renderer_from_dict(renderer_dict)

    else:
        if renderer_type == 'stretched':
            statistics = None
            if 'min:' in colormap or 'max:' in colormap or 'mean' in colormap:
                statistics = collect_statistics(filenames, (variable,))[variable]

            colors = []
            for entry in colormap.split(','):
                value, color = entry.split(':')
                # TODO: add proportions of statistics
                if value in ('min', 'max', 'mean'):
                    value = statistics[value]
                else:
                    value = float(value)
                colors.append((value, Color.from_hex(color)))
            renderer = StretchedRenderer(colors, colorspace=colorspace)

        else:
            raise NotImplementedError('other renderers not yet built')

    if legend_ticks is not None and not legend_breaks:
        legend_ticks = [float(v) for v in legend_ticks.split(',')]

    legend = renderer.get_legend(image_height=lh, breaks=legend_breaks, ticks=legend_ticks, max_precision=2)[0].to_image()
    legend.save(os.path.join(output_directory, 'legend.png'))


    for filename in filenames:
        with Dataset(filename) as ds:
            print 'Processing',filename
            filename_root = os.path.split(filename)[1].replace('.nc', '')

            if not variable in ds.variables:
                raise click.BadParameter('variable {0} was not found in file: {1}'.format(variable, filename), param='variable', param_hint='VARIABLE')

            data = ds.variables[variable][:]

            # get transforms, assume last 2 dimensions on variable are spatial in row, col order
            y_dim, x_dim = ds.variables[variable].dimensions[-2:]
            y_len, x_len = data.shape[-2:]
            coords = SpatialCoordinateVariables.from_dataset(ds, x_dim, y_dim)#, projection=Proj(src_crs))

            if coords.y.is_ascending_order():
                data = data[::-1]

            reproject_kwargs = None
            if dst_crs is not None:
                # TODO: extract this out into a general clover reprojection function
                ds_crs = get_crs(ds, variable)
                if not (src_crs or ds_crs):
                    raise click.BadParameter('must provide src_crs to reproject', param='src_crs', param_hint='src_crs')

                src_crs = crs.from_string(ds_crs) if ds_crs else {'init': src_crs}
                coords.projection = Proj(src_crs)

                dst_crs = {'init': dst_crs}

                proj_bbox = coords.bbox.project(Proj(dst_crs))

                x_dif = proj_bbox.xmax - proj_bbox.xmin
                y_dif = proj_bbox.ymax - proj_bbox.ymin

                total_len = float(x_len + y_len)
                # Cellsize is dimension weighted average of x and y dimensions per projected pixel, unless otherwise provided
                avg_cellsize = ((x_dif / float(x_len)) * (float(x_len) / total_len)) + ((y_dif / float(y_len)) * (float(y_len) / total_len))

                cellsize = res or avg_cellsize
                dst_affine = Affine(cellsize, 0, proj_bbox.xmin, 0, -cellsize, proj_bbox.ymax)
                dst_shape = (
                    max(int(ceil((y_dif) / cellsize)), 1),  # height
                    max(int(ceil(x_dif / cellsize)), 1)  # width
                )

                reproject_kwargs = {
                    'src_crs': src_crs,
                    'src_transform': coords.affine,
                    'dst_crs': dst_crs,
                    'dst_transform': dst_affine,
                    'resampling': getattr(RESAMPLING, resampling),
                    'dst_shape': dst_shape
                }

            num_dimensions = len(data.shape)
            if num_dimensions == 2:
                image_filename = os.path.join(output_directory,
                                              '{0}.png'.format(filename_root))
                render_image(renderer, data, image_filename, scale, reproject_kwargs=reproject_kwargs)

            elif num_dimensions == 3:
                if id_variable is not None:
                    assert data.shape[0] == ds.variables[id_variable][:].shape[0]

                for index in range(data.shape[0]):
                    id = ds.variables[id_variable][index] if id_variable is not None else index
                    image_filename = os.path.join(output_directory,
                                                  '{0}__{1}.png'.format(filename_root, id))
                    render_image(renderer, data[index], image_filename, scale, reproject_kwargs=reproject_kwargs)

            else:
                # Assume last 2 components of shape are lat & lon, rest are
                id_variables = None
                if id_variable is not None:
                    id_variables = id_variable.split(',')
                    for index, name in enumerate(id_variables):
                        if name:
                            assert data.shape[index] == ds.variables[name][:].shape[0]

                ranges = []
                for dim in data.shape[:-2]:
                    ranges.append(range(0, dim))
                for combined_index in product(*ranges):
                    id_parts = []
                    for index, dim_index in enumerate(combined_index):
                        if id_variables is not None and index < len(id_variables) and id_variables[index]:
                            id = ds.variables[id_variables[index]][dim_index]

                            if not isinstance(id, basestring):
                                if isinstance(id, Iterable):
                                    id = '_'.join((str(i) for i in id))
                                else:
                                    id = str(id)

                            id_parts.append(id)

                        else:
                            id_parts.append(str(dim_index))

                    combined_id = '_'.join(id_parts)
                    image_filename = os.path.join(output_directory,
                                                  '{0}__{1}.png'.format(filename_root, combined_id))
                    render_image(renderer, data[combined_index], image_filename, scale, reproject_kwargs=reproject_kwargs)
