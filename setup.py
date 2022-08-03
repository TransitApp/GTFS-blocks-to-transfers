from setuptools import setup, find_packages
import dependency_info

setup(name='GTFS-blocks-to-transfers',
      version='1.4.1',
      description='Convert GTFS blocks to trip-to-trip transfers',
      url='https://github.com/TransitApp/GTFS-blocks-to-transfers',
      author='Nicholas Paun',
      license='License :: OSI Approved :: MIT License',
      packages=find_packages(),
      zip_safe=False,
      install_requires=[
          f'py-gtfs-loader @ git+https://github.com/transitapp/py-gtfs-loader@v{dependency_info.py_gtfs_loader}'
      ]
)
