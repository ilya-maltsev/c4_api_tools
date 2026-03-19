from setuptools import setup
setup(name = 'c4_config_exporter',
    version = '1.2',
    py_modules = ['c4_config_exporter'],
    packages = ['c4_config_exporter'],
    install_requires = ['c4_lib'],
    include_package_data = True,
    entry_points = {
        'console_scripts': [
                'c4_config_exporter = c4_config_exporter.__main__:cli',
        ]
    }
)
