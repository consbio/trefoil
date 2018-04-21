import os
import re
import six
from collections import OrderedDict
import numpy
import math
from netCDF4 import Dataset, default_fillvals


NUMBER_REGEXP = re.compile('\d+')


def get_fill_value(dtype):
    if isinstance(dtype, six.string_types):
        dtype = numpy.dtype(dtype)
    return default_fillvals[dtype.str[1:]]


def get_fill_value_for_variable(variable):
    if hasattr(variable, 'fill_value'):
        return variable.fill_value
    elif hasattr(variable, '_FillValue'):
        return variable._FillValue
    elif hasattr(variable, 'missing_value'):
        return variable.missing_value
    return get_fill_value(variable.dtype)


def get_dtype_string(variable):
    dtype = str(variable.dtype)
    if "'" in dtype:
        dtype = dtype.split("'")[1]

    return dtype


def copy_dimension(source_dataset, target_dataset, name, overwrite=True, allow_unlimited=False):
    """
    Copies a dimension to a netCDF file, deleting it if it already exists (unless overwrite is false, in which case
    this raises an exception).
    Copies the size if the dimension is not unlimited.

    :param source_dataset: the source netCDF dataset
    :param target_dataset: the target netCDF to copy into.  Must be in edit / write mode.
    :param name: the name of the dimension
    :param overwrite: if true, overwrite the dimension if found in target.  May cause bad side effects if other variables
    :param allow_unlimited: if true, allow unlimited dimensions to remain unlimited
    depend on that dimension in the target.

    :return new dimension
    """

    if name in target_dataset.dimensions:
        if overwrite:
            del target_dataset.dimensions[name]
        else:
            raise Exception("Target dimension already exists, and overwrite is false")
    source_dimension = source_dataset.dimensions[name]
    if allow_unlimited and source_dimension.isunlimited():
        return target_dataset.createDimension(name, None)
    else:
        return target_dataset.createDimension(name, len(source_dimension))


def copy_variable(source_dataset, target_dataset, name, out_name=None, overwrite=True, **kwargs):
    """
    Copies a variable to a netCDF file, deleting it if it already exists (unless overwrite is false).
    Copies the required dimensions first, if they don't already exist.
    Copies the variable's attributes across.
    Raises exception if dimensions already exist and do not match the size required by this variable.

    :param source_dataset: the source netCDF dataset
    :param target_dataset: the target netCDF to copy into.  Must be in edit / write mode.
    :param name: the name of the variable
    :param out_name: the output name of the variable
    :param overwrite: if true, overwrite the variable if it exists in the target
    """

    if not out_name:
        out_name = name

    if out_name in target_dataset.variables:
        if overwrite:
            del target_dataset.variables[out_name]
        else:
            raise Exception("Target variable already exists, and overwrite is false")

    source_variable = source_dataset.variables[name]
    for dimension_name in source_variable.dimensions:
        if dimension_name in target_dataset.dimensions:
            source_dimension = source_dataset.dimensions[dimension_name]
            target_dimension = target_dataset.dimensions[dimension_name]
            if not (len(target_dimension) == len(source_dimension) or
                        target_dimension.isunlimited() == source_dimension.isunlimited()):
                raise Exception("Dimension already exists in target, but has different size")
        else:
            copy_dimension(source_dataset, target_dataset, dimension_name)
        if (dimension_name in source_dataset.variables and not dimension_name in target_dataset.variables
            and dimension_name != name):
            copy_variable(source_dataset, target_dataset, dimension_name)

    if 'fill_value' not in kwargs and source_variable.dtype != numpy.dtype('str'):
        kwargs['fill_value'] = get_fill_value_for_variable(source_variable)

    target_variable = target_dataset.createVariable(out_name, source_variable.dtype, source_variable.dimensions, **kwargs)
    target_variable[:] = source_variable[:]
    for attribute_name in source_variable.ncattrs():
        if not attribute_name in target_variable.ncattrs():
            target_variable.setncattr(attribute_name, source_variable.getncattr(attribute_name))


def copy_attributes(source, target, attribute_names, overwrite=True):
    """
    Copies attributes from source object to target object, overwriting if already exists.

    :param source: the source object (dataset, variable, etc)
    :param target: the target object
    :param attribute_names: tuple / list of attribute names to copy across
    """

    for attribute_name in attribute_names:
        # Skip protected attributes that must be set in other ways
        if attribute_name in ('_FillValue'):
            continue

        if hasattr(target, attribute_name) and not overwrite:
            raise Exception("Attribute already exists in target, but overwrite is false")
        setattr(target, attribute_name, getattr(source, attribute_name))


def copy_variable_dimensions(source_dataset, target_dataset, name, overwrite=True, **kwargs):
    """
    Copies the dimensions for a variable to target_dataset.

    :param source_dataset: the source netCDF dataset
    :param target_dataset: the target netCDF to copy into.  Must be in edit / write mode.
    :param name: the name of the variable whose dimensions we want to copy
    :param overwrite: if true, overwrite the dimensions if they exists in the target
    :param kwargs: kwargs passed to copy_dimensions for each dimension
    """

    for dimension_name in source_dataset.variables[name].dimensions:
        if dimension_name in source_dataset.variables:
            copy_variable(source_dataset, target_dataset, dimension_name, overwrite=overwrite, **kwargs)
        else:
            copy_dimension(source_dataset, target_dataset, dimension_name, overwrite=overwrite, **kwargs)


def create_variable_like(target_dataset, target_name, like_dataset, like_name, overwrite=True, **kwargs):
    """
    Creates a new variable like an existing variable

    :param target_dataset: the dataset in which to create the variable and associated dimensions.  Must be in write / edit mode.
    :param target_name: name of variable to create
     :param like_dataset: dataset that contains the variable used as a template
    :param like_name: template variable
    :param overwrite: if true, overwrite the variable if it exists in the target
    :param kwargs: passed to variable create and to copy dimensions
    :return: netCDF Variable object
    """

    if target_name in target_dataset.variables:
        if overwrite:
            del target_dataset.variables[target_name]
        else:
            raise Exception("Target variable already exists, and overwrite is false")

    copy_variable_dimensions(like_dataset, target_dataset, like_name, overwrite=overwrite, **kwargs)
    like_variable = like_dataset.variables[like_name]
    return target_dataset.createVariable(target_name, like_variable.dtype, like_variable.dimensions, **kwargs)


def concat_variable_along_dimension(source_datasets, target_dataset, variable_name, dimension_name, **kwargs):
    """
    Creates a new variable in target and concatenates values for that variable along a new dimension of size equal
    to the number of sources.

    :param sources: open source datasets to copy variable from.  Must all be of the same dimensionality.  The first
    source will be used as the template for the new variable created, and it is the only one used for any attributes
    copied from the source to the target.
    :param target: open target dataset (in write mode) to write concatenated values to
    :param variable_name: name of variable to concatenate from source into target
    :param dimension_name: name of new dimension; will be created with length equal to number of sources
    :param kwargs: additional kwargs for creation of variable in target dataset
    """


    assert len(source_datasets) > 1

    labels = None
    if isinstance(source_datasets, OrderedDict):
        labels = source_datasets.keys()
        source_datasets = source_datasets.values()

    # Initialize the variable using the first source as the template
    source_dataset = source_datasets[0]
    source_variable = source_dataset.variables[variable_name]
    for dim in source_variable.dimensions:
        copy_dimension(source_dataset, target_dataset, dim)
        if dim in source_dataset.variables:
            copy_variable(source_dataset, target_dataset, dim)

    target_dataset.createDimension(dimension_name, len(source_datasets))
    if labels is not None:
        label_variable = target_dataset.createVariable(dimension_name, "string", (dimension_name,))
        for index, label in enumerate(labels):
            label_variable[index] = label

    if not 'fill_value' in kwargs:
        kwargs['fill_value'] = get_fill_value_for_variable(source_variable)

    dimensions = list(source_variable.dimensions)
    dimensions.insert(0, dimension_name)
    target_variable = target_dataset.createVariable(variable_name, source_variable.dtype, dimensions, **kwargs)
    for attribute_name in source_variable.ncattrs():
        if not attribute_name in target_variable.ncattrs():
            target_variable.setncattr(attribute_name, source_variable.getncattr(attribute_name))

    for index, source_dataset in enumerate(source_datasets):
        target_variable[index,] = source_dataset.variables[variable_name][:]


def extract_subset(source_dataset, target_dataset, name, slices, target_name=None, blocksize=100000000, **kwargs):
    """
    Extracts a subset of this variable along time and / or spatial coordinates into a new dataset, copying along
    all dimensions and attributes associated with it from the original.

    :param source_dataset: open source datasets to copy variable from
    :param target_dataset: open target dataset (in write mode)
    :param name: name of the variable to subset
    :param slices: tuple of slice objects or None; one for each dimension.  Example: (slice(0, 2), None, slice(100, 200))
    :param target_name: if None, will default to name
    :param kwargs: additional parameters to pass to createVariable function

    :return: the new variable in the target dataset
    """

    if six.PY2:
        blocksize = long(blocksize)

    source_variable = source_dataset.variables[name]
    assert len(slices) == len(source_variable.dimensions)

    slices = list(slices)

    if name in target_dataset.variables:
        raise ValueError('Variable with name {0} is already present in target dataset'.format(name))

    target_shape = []
    for index, dimension in enumerate(source_variable.dimensions):
        if dimension == name:  # current variable; break or we get infinite loop
            break

        # Calculate slices based on dimensions, if not provided
        if slices[index] is None or slices[index].start is None:
            slices[index] = slice(0, len(source_dataset.dimensions[dimension]))

        cur_slice = slices[index]
        dimension_length = cur_slice.stop - cur_slice.start
        target_shape.append(dimension_length)

        if dimension in target_dataset.dimensions:
            if not len(target_dataset.dimensions[dimension]) == dimension_length:
                raise ValueError('Target dimension already in target dataset, but with different length')
        else:
            target_dataset.createDimension(dimension, dimension_length)

        if dimension in source_dataset.variables and not dimension in target_dataset.variables:
            extract_subset(source_dataset, target_dataset, dimension, (cur_slice,))

    if not 'fill_value' in kwargs:
        kwargs['fill_value'] = get_fill_value_for_variable(source_variable)

    target_variable = target_dataset.createVariable(
        target_name or name,
        source_variable.dtype,
        source_variable.dimensions,
        **kwargs
    )

    target_size = numpy.product(target_shape)
    if target_size < blocksize:
        target_variable[:] = source_variable[slices]
    else:
        # Have to copy in blocks to avoid memory errors
        # Assume that we can do this in increments of the first dimension
        if numpy.product(target_shape[1:]) >= blocksize:
            raise NotImplementedError('blocksize must be greater than the product of the shape for all secondary dimensions')

        increment = int(math.floor(float(target_shape[0] * blocksize) / float(target_size)))
        num_increments = int(math.ceil(float(target_shape[0]) / increment))

        for i in range(0, num_increments):
            first_slice = slice(slices[0].start + (i * increment), min(slices[0].start + ((i + 1) * increment), slices[0].stop))
            updated_slices = [first_slice] + slices[1:]
            target_variable[(i*increment):min((i*increment) + increment, target_shape[0])] = source_variable[updated_slices]

    # Copy source variable attributes
    for attribute_name in source_variable.ncattrs():
        if not attribute_name in target_variable.ncattrs():
            target_variable.setncattr(attribute_name, source_variable.getncattr(attribute_name))

    return target_variable


def get_ncattrs(obj):
    """
    Returns ncattrs of a netcdf object as a dictionary
    :param obj: Object to collect ncattrs from
    :return: dictionary representation of those ncattrs
    """

    out = {}
    for key in obj.ncattrs():
        value = obj.getncattr(key)
        if hasattr(value, 'tolist'):
            # Convert numpy dtypes to native python types
            value = value.tolist()

        out[key] = value

    return out


def set_ncattrs(obj, atts):
    """
    Sets attribute dictionary as ncattrs
    :param obj: object against which to set ncattrs
    :param atts: attributes dictionary
    """

    for key in atts:
        obj.setncattr(key, atts[key])


def collect_statistics(filenames, variables, mask=None):
    """
    Collects basic statistics for each variable across all files
    :param filenames: files to collect statistics from
    :param variable: variables to collect statistics from
    :param mask: numpy mask: True = areas to mask out.  Must be broadcastable to data variable arrays
    :return: dictionary of {"<variable>": {"min": <min> ...} }
    """

    statistics = {v: {s: [] for s in ('min', 'mean', 'max')} for v in variables}

    for filename in filenames:
        with Dataset(filename) as ds:
            for variable in variables:
                if not variable in ds.variables:
                    raise ValueError('Variable {0} is not present in dataset {1}'.format(variable, filename))

                data = numpy.ma.masked_array(ds.variables[variable][:], mask=mask)
                stats = statistics[variable]
                stats['min'].append(data.min())
                stats['mean'].append(data.mean())
                stats['max'].append(data.max())

    for variable in variables:
        stats = statistics[variable]
        stats['min'] = numpy.min(stats['min']).item()
        stats['mean'] = numpy.mean(stats['mean']).item()
        stats['max'] = numpy.max(stats['max']).item()

    return statistics


def data_variables(ds):
    """
    Returns subset of ds.variables that are data rather than dimension variables
    """

    exclude_vars = set()
    exclude_atts = ('bounds', 'grid_mapping')  # exclude variables referenced from these attributes
    for v in ds.variables.values():
        atts = get_ncattrs(v)
        for att in exclude_atts:
            if att in atts:
                exclude_vars.add(atts[att])

    return OrderedDict([(k, v) for k, v in six.iteritems(ds.variables)
                        if k not in ds.dimensions and k not in exclude_vars])


def get_pack_atts(dtype, min_value, max_value):
    """
    Get attributes based on the data type and value range.  Assumes that default fill values are used (top of data type
    range for unsigned integer types).

    scale_factor and add_offset attributes will be set on variable according to formula described here:
    http://nco.sourceforge.net/nco.html#Packed-data

    scale_factor = (max_value - min_value) / (2**bits - 2)        where bits are the number of bits from data type
    add_offset = min_value

    Parameters
    ----------
    dtype: a numpy dtype object or string (must be one of: int8, int16, int32, uint8, uint16, uint32)
    min_value: number, minimum value of data to pack
    max_value: number, maximum value of data to pack

    Returns
    -------
    (scale_factor, add_offset)
    """

    if hasattr(dtype, 'name'):
        dtype = dtype.name

    if not dtype in ('uint8', 'uint16', 'uint32'):
        raise ValueError('data type for variable must be one of: uint8, uint16, uint32')

    nbits = int(NUMBER_REGEXP.search(dtype).group())

    scale = (max_value - min_value) / (2**nbits - 2)
    return scale, min_value


def resolve_dataset_variable(path):
    """
    Resolves a dataset plus variable path into a dataset path and
    variable name.

    example: "/tmp/foo.nc:bar" -> ("/tmp/foo.nc", "bar")

    Parameters
    ----------
    path: string, a compound path of dataset:variable

    Returns
    -------
    tuple of dataset and variable
    """

    path, dataset = os.path.split(path)
    variable = None
    if ':' in dataset:
        dataset, variable = dataset.split(':')

    return os.path.join(path, dataset), variable
