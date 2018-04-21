import importlib

import click
import os
import numpy
from PIL.Image import ANTIALIAS
from pyproj import Proj
from netCDF4 import Dataset

from trefoil.utilities.color import Color
from trefoil.netcdf.utilities import collect_statistics, resolve_dataset_variable
from trefoil.render.renderers.stretched import StretchedRenderer
from trefoil.render.renderers.classified import ClassifiedRenderer


def render_image(renderer, data, filename, scale=1, flip_y=False, format='png'):
    if flip_y:
        data = data[::-1]

    img = renderer.render_image(data)
    if scale != 1:
        img = img.resize((numpy.array(data.shape[::-1]) * scale).astype(numpy.uint), ANTIALIAS)

    kwargs = {}
    if format == 'png':
        kwargs['optimize'] = True
    elif format == 'jpg':
        img = img.convert('RGB')
        kwargs['progressive'] = True
    elif format == 'webp':
        img = img.convert('RGBA')
        kwargs['lossless'] = True

    img.save(filename, **kwargs)


def colormap_to_stretched_renderer(colormap, colorspace='hsv', filenames=None, variable=None, fill_value=None, mask=None):
    statistics = None
    if 'min:' in colormap or 'max:' in colormap or 'mean' in colormap:
        if not filenames and variable:
            raise ValueError('filenames and variable are required inputs to use colormap with statistics')
        statistics = collect_statistics(filenames, (variable,), mask=mask)[variable]

    colors = []
    for entry in colormap.split(','):
        value, color = entry.split(':')
        # TODO: add proportions of statistics
        if value in ('min', 'max', 'mean'):
            value = statistics[value]
        else:
            value = float(value)
        colors.append((value, Color.from_hex(color)))

    return StretchedRenderer(colors, colorspace=colorspace, fill_value=fill_value)


def get_palette(palette_path):
    index = palette_path.rindex('.')
    return getattr(importlib.import_module('palettable.' + palette_path[:index]), palette_path[index+1:])


def palette_to_stretched_renderer(palette_path, values, filenames=None, variable=None, fill_value=None, mask=None):
    palette = get_palette(palette_path)

    values = values.split(',')
    if not len(values) > 1:
        raise ValueError('Must provide at least 2 values for palette-based stretched renderer')

    if 'min' in values or 'max' in values:
        if not filenames and variable:
            raise ValueError('filenames and variable are required inputs to use palette with statistics')
        statistics = collect_statistics(filenames, (variable,), mask=mask)[variable]

        for statistic in ('min', 'max'):
            if statistic in values:
                values[values.index(statistic)] = statistics[statistic]

    values = [float(v) for v in values]  # in case any are still strings

    hex_colors = palette.hex_colors

    # TODO: this only works cleanly for min:max or 2 endpoint values.  Otherwise require that the number of palette colors match the number of values

    colors = [(values[0], Color.from_hex(hex_colors[0]))]

    intermediate_colors = hex_colors[1:-1]
    if intermediate_colors:
        interval = (values[-1] - values[0]) / (len(intermediate_colors) + 1)
        for i, color in enumerate(intermediate_colors):
            colors.append((values[0] + (i + 1) * interval, Color.from_hex(color)))

    colors.append((values[-1], Color.from_hex(hex_colors[-1])))

    return StretchedRenderer(colors, colorspace='rgb', fill_value=fill_value)  # I think all palettable palettes are in RGB ramps


def palette_to_classified_renderer(palette_path, filenames, variable, method='equal', fill_value=None, mask=None):
    palette = get_palette(palette_path)
    num_breaks = palette.number
    colors = [Color(r, g, b) for (r, g, b) in palette.colors]

    if method == 'equal':
        statistics = collect_statistics(filenames, (variable,), mask=mask)[variable]
        step = (statistics['max'] - statistics['min']) / num_breaks
        breaks = numpy.linspace(statistics['min'] + step, statistics['max'], num_breaks)

    return ClassifiedRenderer(zip(breaks, colors), fill_value=fill_value)


def get_leaflet_anchors(bbox):
    """
    Returns Leaflet anchor coordinates for creating an ImageOverlay layer.
    """

    wgs84_bbox = bbox.project(Proj(init='EPSG:4326'))
    return [[wgs84_bbox.ymin, wgs84_bbox.xmin], [wgs84_bbox.ymax, wgs84_bbox.xmax]]

def get_mask(mask_path):
    """
    Returns a numpy style mask from a netCDF file.

    Parameters
    ----------
    mask_path: string, a compound path of dataset:variable

    Returns
    -------
    boolean mask  (True where mask will be applied)
    """

    mask_path, mask_variable = resolve_dataset_variable(mask_path)
    if not mask_variable:
        mask_variable = 'mask'

    with Dataset(mask_path) as mask_ds:
        if not mask_variable in mask_ds.variables:
            raise click.BadParameter(
                'mask variable not found: {0}'.format(mask_variable),
                 param='--mask', param_hint='--mask'
            )

        return mask_ds.variables[mask_variable][:].astype('bool')