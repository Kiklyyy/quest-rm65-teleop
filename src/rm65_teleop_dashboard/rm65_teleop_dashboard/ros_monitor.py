"""ROS acquisition only. No Qt imports and no robot output endpoints."""
import threading
import time

import rclpy
from geometry_msgs.msg import Pose, PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.context import Context
from rclpy.executors import ExternalShutdownException, ShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState
from std_msgs.msg import String


TOPICS = {
    **{f'{side}.quest': (f'/q2r_{side}_hand_pose', PoseStamped)
       for side in ('left', 'right')},
    **{f'{side}.inputs': (f'/q2r_{side}_hand_inputs', OVR2ROSInputs)
       for side in ('left', 'right')},
    **{f'{side}.target': (f'/quest_{side}_target_pose', PoseStamped)
       for side in ('left', 'right')},
    **{f'{side}.robot': (f'/{side}/rm_driver/udp_arm_position', Pose)
       for side in ('left', 'right')},
    **{f'{side}.joints': (f'/{side}/joint_states', JointState)
       for side in ('left', 'right')},
    **{f'{side}.status': (f'/{side}/rm65_teleop/status', String)
       for side in ('left', 'right')},
    'linkerhand': ('/right/linkerhand/status', String),
}


class RosMonitorNode(Node):
    def __init__(self, store, context):
        super().__init__('teleop_dashboard_monitor', context=context,
                         enable_rosout=False, start_parameter_services=False)
        # Humble creates a parameter-events publisher internally even when
        # parameter services are disabled. Remove this infrastructure endpoint
        # before monitoring; this application never declares/changes parameters.
        for publisher in tuple(self.publishers):
            self.destroy_publisher(publisher)
        self.store = store
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                         reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE)
        self._streams = [self.create_subscription(
            msg_type, topic, self._callback(key), qos)
            for key, (topic, msg_type) in TOPICS.items()]
        self._graph_timer = self.create_timer(1.0, self._read_graph)

    def _callback(self, key):
        def receive(message):
            now = time.monotonic()
            if key == 'linkerhand':
                self.store.update_linkerhand(message.data, now)
                return
            side, stream = key.split('.')
            if stream in ('quest', 'target', 'robot'):
                pose = message if stream == 'robot' else message.pose
                self.store.update_pose(side, stream,
                    (pose.position.x, pose.position.y, pose.position.z),
                    (pose.orientation.x, pose.orientation.y, pose.orientation.z,
                     pose.orientation.w), now)
            elif stream == 'inputs':
                self.store.update_inputs(side, message.press_middle, message.press_index,
                                         message.button_lower, message.button_upper, now)
            elif stream == 'joints':
                self.store.update_joints(side, message.name, message.position, now)
            else:
                self.store.update_adapter(side, message.data, now)
        return receive

    def _read_graph(self):
        self.store.set_node_count(len(self.get_node_names_and_namespaces()))


class RosMonitorRuntime:
    """Own a dedicated context and executor; callbacks never touch QWidget."""
    def __init__(self, store, ros_args=None):
        self.store = store
        self.context = Context()
        self.node = None
        self.executor = None
        self.thread = None
        self._closed = False
        self._stopping = False
        try:
            rclpy.init(args=ros_args or [], context=self.context)
            self.node = RosMonitorNode(store, self.context)
            self.executor = SingleThreadedExecutor(context=self.context)
            self.executor.add_node(self.node)
            self.thread = threading.Thread(target=self._spin, name='dashboard-ros', daemon=False)
        except Exception:
            self.stop()
            raise

    def start(self):
        if self._closed:
            raise RuntimeError('ROS monitor has been closed')
        if self.thread.ident is None:
            self.thread.start()

    def _spin(self):
        try:
            self.executor.spin()
        except (ExternalShutdownException, ShutdownException):
            if not self._stopping:
                self.store.set_monitor_error('ROS context stopped')
        except Exception as exc:
            self.store.set_monitor_error(f'ROS monitor: {exc}')

    def stop(self):
        if self._closed:
            return
        self._stopping = True
        if self.executor is not None:
            self.executor.shutdown(timeout_sec=5.0)
        if self.thread is not None and self.thread.ident is not None:
            self.thread.join(timeout=5.0)
            if self.thread.is_alive():
                # Wake a context-stopped executor too. Leave _closed false so
                # cleanup can be retried; never destroy a node under a callback.
                if self.context.ok():
                    rclpy.shutdown(context=self.context)
                self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                raise RuntimeError('ROS monitor thread did not stop')
        if self.node is not None:
            self.node.destroy_node()
        if self.context.ok():
            rclpy.shutdown(context=self.context)
        self._closed = True
