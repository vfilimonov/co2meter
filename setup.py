from setuptools import setup

GITHUB_URL = 'http://github.com/vfilimonov/co2meter'

exec(open('co2meter/_version.py').read())

# Long description to be published in PyPi
LONG_DESCRIPTION = """
**CO2meter** is a Python interface to the USB CO2 monitor with monitoring and
logging tools, flask web-server for visualization and Apple HomeKit compatibility.
"""

setup(name='CO2meter',
      version=__version__,
      description='Python interface to the USB CO2 monitor',
      long_description=LONG_DESCRIPTION,
      url=GITHUB_URL,
      download_url=GITHUB_URL + '/archive/v%s.zip' % (__version__),
      author='Vladimir Filimonov',
      author_email='vladimir.a.filimonov@gmail.com',
      license='MIT License',
      packages=['co2meter'],
      install_requires=['hidapi', 'future'],
      include_package_data=True,
      zip_safe=False,
      entry_points={
          'console_scripts': ['co2meter_server = co2meter:start_server',
                              'co2meter_homekit = co2meter:start_homekit',
                              'co2meter_server_homekit = co2meter:start_server_homekit',
                              ],
      },
      classifiers=['Programming Language :: Python :: 3', ]
      )
