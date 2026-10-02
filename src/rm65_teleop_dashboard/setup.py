from glob import glob
from setuptools import setup

package_name = 'rm65_teleop_dashboard'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name, package_name + '.pages'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Quest RM65 maintainers',
    maintainer_email='lh@todo.todo',
    description='Read-only Dual-Arm VR Teleoperation Dashboard',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'teleop_dashboard = rm65_teleop_dashboard.app:main',
        'teleop-dashboard = rm65_teleop_dashboard.app:main',
    ]},
)
