from setuptools import setup, find_packages

setup(name='GTFS-blocks-to-transfers',
      version='0.1.3',
      description='Convert GTFS blocks to trip-to-trip transfers',
      url='https://github.com/TransitApp/GTFS-blocks-to-transfers',
      author='Nicholas Paun',
      license='License :: OSI Approved :: MIT License',
      packages=find_packages(),
      zip_safe=False,
      install_requires=[])
