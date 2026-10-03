"""Start only the monitoring application; never include hardware bringup."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _dashboard(context):
    demo = LaunchConfiguration('demo').perform(context).lower()
    if demo not in ('true', 'false'):
        raise ValueError('demo must be true or false')
    return [Node(
        package='rm65_teleop_dashboard', executable='teleop_dashboard',
        arguments=['--demo'] if demo == 'true' else [], output='screen',
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('demo', default_value='false'),
        OpaqueFunction(function=_dashboard),
    ])
