from setuptools import setup

setup(name='GTFS-blocks-to-transfers',
      version='1.0.0',
      description='Convert GTFS blocks to trip-to-trip transfers',
      url='https://github.com/TransitApp/block2transfers',
      author='Nicholas Paun',
      license='License :: OSI Approved :: MIT License',
      packages=['blocks_to_transfers'],
      zip_safe=False,
      install_requires=[])
