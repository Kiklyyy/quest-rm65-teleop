import struct
import time
import math

from geometry_msgs.msg import Twist, Vector3, PoseStamped, Pose, Point, Quaternion
from quest2ros.msg import OVR2ROSInputs, OVR2ROSHapticFeedback
from geometry_msgs.msg import PoseStamped, Quaternion

def bytes_to_twist(data: bytes) -> Twist:
    # 6 doubles, little-endian
    values = [struct.unpack('<d', data[i:i+8])[0] for i in range(0, 48, 8)]
    return Twist(
        linear=Vector3(x=values[0], y=values[1], z=values[2]),
        angular=Vector3(x=values[3], y=values[4], z=values[5])
    )

def bytes_to_pose_stamped(data: bytes) -> PoseStamped:
    if len(data) < 16:
        raise ValueError(
            f"PoseStamped data too short: {len(data)} bytes"
        )

    # ROS1-style Header:
    # uint32 seq
    # uint32 stamp.sec
    # uint32 stamp.nsec
    # uint32 frame_id length
    seq, stamp_sec, stamp_nsec, frame_len = struct.unpack_from(
        '<IIII', data, 0
    )

    if frame_len > len(data) - 16:
        raise ValueError(
            f"Invalid frame_id length: {frame_len}, total data={len(data)}"
        )

    frame_start = 16
    frame_end = frame_start + frame_len

    frame_id = data[frame_start:frame_end].decode(
        'utf-8',
        errors='replace'
    ).rstrip('\x00')

    # Pose starts immediately after frame_id
    pose_offset = frame_end

    if len(data) < pose_offset + 56:
        raise ValueError(
            f"Expected at least {pose_offset + 56} bytes, "
            f"got {len(data)}"
        )

    x, y, z, qx, qy, qz, qw = struct.unpack_from(
        '<7d', data, pose_offset
    )

    print(
        f"[DEBUG POSE] len={len(data)}, "
        f"seq={seq}, frame_len={frame_len}, "
        f"frame_id={repr(frame_id)}, "
        f"pose_offset={pose_offset}, "
        f"pos=({x:.3f}, {y:.3f}, {z:.3f}), "
        f"quat=({qx:.3f}, {qy:.3f}, {qz:.3f}, {qw:.3f})"
    )

    pose_msg = PoseStamped()

    # 暂时继续使用当前系统时间，与原项目当前实现保持一致
    t = time.time()
    pose_msg.header.stamp.sec = int(t)
    pose_msg.header.stamp.nanosec = int((t % 1) * 1e9)

    # 可以暂时保持原项目的行为
    pose_msg.header.frame_id = "base_link"

    pose_msg.pose.position = Point(
        x=x,
        y=y,
        z=z
    )

    pose_msg.pose.orientation = Quaternion(
        x=qx,
        y=qy,
        z=qz,
        w=qw
    )

    return pose_msg


def bytes_to_ovr2ros_inputs(data: bytes) -> OVR2ROSInputs:

    if len(data) < 18:
        raise ValueError(f"Expected 18 bytes, got {len(data)}")

    # 2 x bool (<??) + 4 x float32 (<ffff)
    button_upper, button_lower, x, y, index, middle = struct.unpack('<??ffff', data[0:18])

    msg = OVR2ROSInputs()
    msg.button_upper = button_upper
    msg.button_lower = button_lower
    msg.thumb_stick_horizontal = x
    msg.thumb_stick_vertical = y
    msg.press_index = index
    msg.press_middle = middle

    return msg

def bytes_to_ovr2ros_haptic_feedback(data: bytes) -> OVR2ROSHapticFeedback:
    freq, amp = struct.unpack('<dd', data[0:16])
    msg = OVR2ROSHapticFeedback()
    msg.frequency = freq
    msg.amplitude = amp
    return msg

def convert_data(topic: str, data: bytes):
    if topic in ["q2r_right_hand_twist", "q2r_left_hand_twist", "dice_twist", "q2r_twist"]:
        return bytes_to_twist(data)
    elif topic in ["q2r_right_hand_pose", "q2r_left_hand_pose"]:
        return bytes_to_pose_stamped(data)
    elif topic in ["q2r_right_hand_inputs", "q2r_left_hand_inputs"]:
        return bytes_to_ovr2ros_inputs(data)
    elif topic in ["q2r_right_hand_haptic_feedback", "q2r_left_hand_haptic_feedback"]:
        return bytes_to_ovr2ros_haptic_feedback(data)
    else:
        print(f"[WARNING] Unknown topic '{topic}', cannot convert.")
        return None
