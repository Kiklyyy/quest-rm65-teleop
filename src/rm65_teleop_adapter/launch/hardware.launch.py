from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory("rm65_teleop_adapter")) / "config" / "hardware.yaml"
    return LaunchDescription([Node(package="rm65_teleop_adapter", executable="rm65_teleop_adapter_node", name="rm65_teleop_adapter", output="screen", parameters=[str(config)])])
