from setuptools import setup
setup(name = 'c4_backup_tool',
    version = '1.3',
    py_modules = ['c4_backup_tool'],
    packages = ['c4_backup_tool'],
    install_requires = ['c4_lib'],
    include_package_data = True,
    entry_points = {
        'console_scripts': [
                'c4_backup_tool = c4_backup_tool.__main__:cli',
        ]
    }
)
