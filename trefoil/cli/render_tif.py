"""
Render a set of GeoTIFF files to images.

Stretched renderers may have one of the following colormap values:
1.0 (absolute)
max (calculate max across datasets)
0.5*max (calculate max across datasets, and multiply by value)
"""


import importlib
import os
import glob
import click
import json
import numpy
from PIL.Image import ANTIALIAS, NEAREST
from pyproj import Proj

import rasterio
from rasterio.warp import reproject, calculate_default_transform
from rasterio.enums import Resampling

from trefoil.utilities.color import Color
from trefoil.render.renderers.stretched import StretchedRenderer
from trefoil.render.renderers.unique import UniqueValuesRenderer
from trefoil.render.renderers.utilities import renderer_from_dict
from trefoil.netcdf.utilities import collect_statistics
from trefoil.geometry.bbox import BBox
from trefoil.cli import cli


def _colormap_to_stretched_renderer(colormap, colorspace='hsv', filenames=None, variable=None):
    statistics = None
    if 'min:' in colormap or 'max:' in colormap or 'mean' in colormap:
        if not filenames and variable:
            raise ValueError('filenames and variable are required inputs to use colormap with statistics')
        statistics = collect_statistics(filenames, (variable,))[variable]

        for value in ('min', 'max', 'mean'):
            colormap = colormap.replace(value, statistics[value])

    return StretchedRenderer(_parse_colormap(colormap), colorspace=colorspace)


def _parse_colormap(colormap_str):
    colormap = []
    for entry in colormap_str.split(','):
        value, color = entry.split(':')
        colormap.append((float(value), Color.from_hex(color)))
    return colormap


def _palette_to_stretched_renderer(palette_path, values, filenames=None, variable=None):
    index = palette_path.rindex('.')
    palette = getattr(importlib.import_module('palettable.' + palette_path[:index]), palette_path[index+1:])

    values = values.split(',')
    if not len(values) > 1:
        raise ValueError('Must provide at least 2 values for palette-based stretched renderer')

    statistics = None
    if 'min' in values or 'max' in values:
        if not filenames and variable:
            raise ValueError('filenames and variable are required inputs to use palette with statistics')
        statistics = collect_statistics(filenames, (variable,))[variable]

        for statistic in ('min', 'max'):
            if statistic in values:
                values[values.index(statistic)] = statistics[statistic]

    hex_colors = palette.hex_colors

    # TODO: this only works cleanly for min:max or 2 endpoint values.  Otherwise require that the number of palette colors match the number of values

    colors = [(values[0], Color.from_hex(hex_colors[0]))]

    intermediate_colors = hex_colors[1:-1]
    if intermediate_colors:
        interval = (values[-1] - values[0]) / (len(intermediate_colors) + 1)
        for i, color in enumerate(intermediate_colors):
            colors.append((values[0] + (i + 1) * interval, Color.from_hex(color)))

    colors.append((values[-1], Color.from_hex(hex_colors[-1])))

    return StretchedRenderer(colors, colorspace='rgb')  # I think all palettable palettes are in RGB ramps


def render_image(renderer, data, filename, scale=1, reproject_kwargs=None):
    if reproject_kwargs is not None:

        with rasterio.Env():
            out = numpy.empty(shape=reproject_kwargs['dst_shape'], dtype=data.dtype)
            out.fill(data.fill_value)
            reproject(data, out, **reproject_kwargs)
            # Reapply mask
            data = numpy.ma.masked_array(out, mask=out == data.fill_value)


    resampling = ANTIALIAS
    if renderer.name == 'unique':
        resampling = NEAREST

    img = renderer.render_image(data)
    if scale != 1:
        img = img.resize((numpy.array(data.shape[::-1]) * scale).astype(numpy.uint), resampling)
    img.save(filename)


@cli.command(short_help="Render Single-Band GeoTIFF files to images")
@click.argument('filename_pattern')
@click.argument('output_directory', type=click.Path())
@click.option('--renderer_file', help='File containing renderer JSON', type=click.Path())
@click.option('--save', default=False, is_flag=True, help='Save renderer to renderer_file')
@click.option('--renderer_type', default='stretched', type=click.Choice(['stretched', 'unique']), help='Name of renderer [default: stretched].  (other types not yet implemented)')
@click.option('--colormap', default='min:#000000,max:#FFFFFF', help='Provide colormap as comma-separated lookup of value to hex color code.  (Example: -1:#FF0000,1:#0000FF) [default: min:#000000,max:#FFFFFF]')
@click.option('--colorspace', default='hsv', type=click.Choice(['hsv', 'rgb']), help='Color interpolation colorspace')
@click.option('--palette', default=None, help='Palettable color palette (Example: colorbrewer.sequential.Blues_3)')
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
@click.option('--anchors', default=False, is_flag=True, help='Print anchor coordinates for use in Leaflet ImageOverlay')
# TODO: option with transform info if not a geo format
def render_tif(
        filename_pattern,
        output_directory,
        renderer_file,
        save,
        renderer_type,
        colormap,
        colorspace,
        palette,
        scale,
        id_variable,
        lh,
        legend_breaks,
        legend_ticks,
        src_crs,
        dst_crs,
        res,
        resampling,
        anchors):
    """
    Render single-band GeoTIFF files to images.

    colormap is ignored if renderer_file is provided
    """

    filenames = glob.glob(filename_pattern)
    if not filenames:
        raise click.BadParameter('No files found matching that pattern', param='filename_pattern', param_hint='FILENAME_PATTERN')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if renderer_file is not None and not save:
        if not os.path.exists(renderer_file):
            raise click.BadParameter('does not exist', param='renderer_file', param_hint='renderer_file')

        # see https://bitbucket.org/databasin/ncdjango/wiki/Home for format
        renderer_dict = json.loads(open(renderer_file).read())

        # if renderer_dict['type'] == 'stretched':
        #     colors = ','.join([str(c[0]) for c in renderer_dict['colors']])
        #     if 'min' in colors or 'max' in colors or 'mean' in colors:
        #         statistics = collect_statistics(filenames, (variable,))[variable]
        #         for entry in renderer_dict['colors']:
        #             if isinstance(entry[0], basestring):
        #                 if entry[0] in ('min', 'max', 'mean'):
        #                     entry[0] = statistics[entry[0]]
        #                 elif '*' in entry[0]:
        #                     rel_value, statistic = entry[0].split('*')
        #                     entry[0] = float(rel_value) * statistics[statistic]

        renderer = renderer_from_dict(renderer_dict)

    else:

        if renderer_type == 'stretched':
            # if palette is not None:
            #     renderer = _palette_to_stretched_renderer(palette, 'min,max', filenames, variable)
            #
            # else:
            renderer = _colormap_to_stretched_renderer(colormap, colorspace, filenames)
        elif renderer_type == 'unique':
            renderer = UniqueValuesRenderer(_parse_colormap(colormap), colorspace)

        else:
            raise NotImplementedError('other renderers not yet built')

    # if save:
    #     if not renderer_file:
    #         raise click.BadParameter('must be provided to save', param='renderer_file', param_hint='renderer_file')
    #
    #     if os.path.exists(renderer_file):
    #         with open(renderer_file, 'r+') as output_file:
    #             data = json.loads(output_file.read())
    #             output_file.seek(0)
    #             output_file.truncate()
    #             data[variable] = renderer.serialize()
    #             output_file.write(json.dumps(data, indent=4))
    #     else:
    #         with open(renderer_file, 'w') as output_file:
    #             output_file.write(json.dumps({variable: renderer.serialize()}))


    if renderer_type == 'streteched':
        if legend_ticks is not None and not legend_breaks:
            legend_ticks = [float(v) for v in legend_ticks.split(',')]

        legend = renderer.get_legend(image_height=lh, breaks=legend_breaks, ticks=legend_ticks, max_precision=2)[0].to_image()

    elif renderer_type == 'unique':
        legend = renderer.get_legend(image_height=lh)[0].to_image()

    legend.save(os.path.join(output_directory, 'legend.png'))


    for filename in filenames:
        with rasterio.open(filename) as ds:
            print('Processing',filename)
            filename_root = os.path.split(filename)[1].replace('.nc', '')

            data = ds.read(1, masked=True)

            # # get transforms, assume last 2 dimensions on variable are spatial in row, col order
            # y_dim, x_dim = ds.variables[variable].dimensions[-2:]
            # y_len, x_len = data.shape[-2:]
            # coords = SpatialCoordinateVariables.from_dataset(ds, x_dim, y_dim)#, projection=Proj(src_crs))
            #
            # if coords.y.is_ascending_order():
            #     data = data[::-1]
            #
            reproject_kwargs = None
            if dst_crs is not None:
                # TODO: extract this out into a general trefoil reprojection function
                ds_crs = ds.crs
                if not (src_crs or ds_crs):
                    raise click.BadParameter('must provide src_crs to reproject', param='src_crs', param_hint='src_crs')

                dst_crs = {'init': dst_crs}
                src_crs = ds_crs if ds_crs else {'init': src_crs}

                left, bottom, top, right = ds.bounds
                dst_affine, dst_width, dst_height = calculate_default_transform(left, bottom, right, top, ds.width, ds.height, src_crs, dst_crs)
                dst_shape = (dst_height, dst_width)


                # proj_bbox = coords.bbox.project(Proj(dst_crs))
                #
                # x_dif = proj_bbox.xmax - proj_bbox.xmin
                # y_dif = proj_bbox.ymax - proj_bbox.ymin
                #
                # total_len = float(x_len + y_len)
                # # Cellsize is dimension weighted average of x and y dimensions per projected pixel, unless otherwise provided
                # avg_cellsize = ((x_dif / float(x_len)) * (float(x_len) / total_len)) + ((y_dif / float(y_len)) * (float(y_len) / total_len))
                #
                # cellsize = res or avg_cellsize
                # dst_affine = Affine(cellsize, 0, proj_bbox.xmin, 0, -cellsize, proj_bbox.ymax)
                # dst_shape = (
                #     max(int(ceil((y_dif) / cellsize)), 1),  # height
                #     max(int(ceil(x_dif / cellsize)), 1)  # width
                # )

                # TODO: replace with method in rasterio
                reproject_kwargs = {
                    'src_crs': src_crs,
                    'src_transform': ds.affine,
                    'dst_crs': dst_crs,
                    'dst_transform': dst_affine,
                    'resampling': getattr(Resampling, resampling),
                    'dst_shape': dst_shape
                }

                if anchors:
                    # Reproject the bbox of the output to WGS84
                    full_bbox = BBox((dst_affine.c, dst_affine.f + dst_affine.e * dst_shape[0],
                                     dst_affine.c + dst_affine.a * dst_shape[1], dst_affine.f),
                                     projection=Proj(dst_crs))
                    wgs84_bbox = full_bbox.project(Proj(init='EPSG:4326'))
                    print('WGS84 Anchors: {0}'.format([[wgs84_bbox.ymin, wgs84_bbox.xmin], [wgs84_bbox.ymax, wgs84_bbox.xmax]]))

            elif anchors:
                # Reproject the bbox of the output to WGS84
                    full_bbox = BBox(ds.bounds, projection=Proj(ds.crs))
                    wgs84_bbox = full_bbox.project(Proj(init='EPSG:4326'))
                    print('WGS84 Anchors: {0}'.format([[wgs84_bbox.ymin, wgs84_bbox.xmin], [wgs84_bbox.ymax, wgs84_bbox.xmax]]))

            image_filename = os.path.join(output_directory,
                                          '{0}.png'.format(filename_root))
            render_image(renderer, data, image_filename, scale, reproject_kwargs=reproject_kwargs)
