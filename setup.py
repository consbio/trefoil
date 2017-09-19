from setuptools import setup

setup(
    name='clover',
    version='0.2.1',
    packages=['clover',
              'clover.analysis', 'clover.cli',
              'clover.geometry', 'clover.geometry.tests',
              'clover.netcdf', 'clover.render',
              'clover.render.renderers', 'clover.render.renderers.tests',
              'clover.utilities', 'clover.utilities.tests'],
    url='https://github.com/databasin/clover',
    license='see LICENSE',
    author='databasin',
    author_email='databasinadmin@consbio.org',
    description='Useful tools for spatial analysis using numpy and NetCDF',
    install_requires=[
        'affine>=1.0',
        'click',
        'jinja2',
        'palettable',
        'pytz',
        'six',
        'fiona>=1.6.0',
        'netCDF4>=1.1.1',
        'Numpy',
        'Pillow>=2.9.0',
        'pyproj',
        'rasterio==1.0a9',
    ],
    entry_points='''
        [console_scripts]
        clover=clover.cli.main:cli
    '''
)
