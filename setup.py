from setuptools import setup

setup(
    name='trefoil',
    version='0.3.2',
    packages=['trefoil',
              'trefoil.analysis', 'trefoil.cli',
              'trefoil.geometry', 'trefoil.geometry.tests',
              'trefoil.netcdf', 'trefoil.render',
              'trefoil.render.renderers', 'trefoil.render.renderers.tests',
              'trefoil.utilities', 'trefoil.utilities.tests',
              # for temporary backward compatibility only!  Will be removed in near future
              'clover'],
    url='https://github.com/consbio/trefoil',
    license='see LICENSE',
    author='databasin',
    author_email='databasinadmin@consbio.org',
    description='Useful tools for spatial analysis using numpy and NetCDF',
    long_description_content_type='text/markdown',
    long_description=open('README.md').read(),
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
        'rasterio>=1.0a12',
    ],
    entry_points='''
        [console_scripts]
        trefoil=trefoil.cli.main:cli
    '''
)
