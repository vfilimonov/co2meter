from distutils.core import setup

GITHUB_URL = 'http://github.com/vfilimonov/co2meter'

exec(open('co2meter/_version.py').read())

# Long description to be published in PyPi
LONG_DESCRIPTION = """
**CO2meter** is a Python library for the USB CO2 meter.
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
      install_requires=['hidapi']
      )
