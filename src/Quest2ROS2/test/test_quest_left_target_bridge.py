from unittest.mock import Mock, patch

from geometry_msgs.msg import PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from visualization_msgs.msg import Marker

from q2r2_bringup.quest_right_target_bridge import QuestRightTargetBridge


def test_left_parameter_instance_wires_left_topics_without_robot_commands():
    values = {
        "pose_topic": "/q2r_left_hand_pose",
        "inputs_topic": "/q2r_left_hand_inputs",
        "target_topic": "/quest_left_target_pose",
        "marker_topic": "/quest_left_target_marker",
        "frame_id": "world",
        "marker_namespace": "quest_left_target",
    }
    with (
        patch.object(Node, "__init__", return_value=None),
        patch.object(Node, "declare_parameter", side_effect=lambda name, default: Mock(value=values[name])) as declare_parameter,
        patch.object(Node, "create_subscription") as subscribe,
        patch.object(Node, "create_publisher") as publish,
        patch.object(Node, "create_timer"),
    ):
        bridge = QuestRightTargetBridge()
    assert declare_parameter.call_count == 6
    assert [call.args[:2] for call in subscribe.call_args_list] == [
        (PoseStamped, values["pose_topic"]),
        (OVR2ROSInputs, values["inputs_topic"]),
    ]
    assert [call.args[:2] for call in publish.call_args_list] == [
        (PoseStamped, values["target_topic"]),
        (Marker, values["marker_topic"]),
    ]
    assert bridge._frame_id == "world"
    assert bridge._marker_namespace == "quest_left_target"
