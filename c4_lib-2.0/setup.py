from setuptools import setup
setup(name = 'c4_lib',
    version = '2.0',
    py_modules = ['c4_lib'],
    packages = ['c4_lib'],
    install_requires = ['urllib3', 'requests'],
    include_package_data = True,
    package_data = {'': ['openssl.cnf', 'gost.so']}
)
