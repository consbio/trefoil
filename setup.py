from setuptools import setup

setup(
    name='clover',
    version='0.2.0',
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
    entry_points='''
        [console_scripts]
        clover=clover.cli.main:cli
    '''
)
