#  Copyright 2020 Unity Technologies
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import rclpy
import re

from rclpy.serialization import deserialize_message

from .communication import RosSender
from ros_tcp_endpoint.ros_msg_converter import convert_data


class RosPublisher(RosSender):
    """
    Class to publish messages to a ROS topic
    """

    # TODO: surface latch functionality
    def __init__(self, topic, message_class, queue_size=10, latch=False):
        """

        Args:
            topic:         Topic name to publish messages to
            message_class: The message class in catkin workspace
            queue_size:    Max number of entries to maintain in an outgoing queue
        """
        strippedTopic = re.sub("[^A-Za-z0-9_]+", "", topic)
        node_name = f"{strippedTopic}_RosPublisher"
        RosSender.__init__(self, node_name)
        self.topic = topic  
        self.msg = message_class()
        self.pub = self.create_publisher(message_class, topic, queue_size)

    def send(self, data):
        """
        Deserialize incoming ROS2 CDR data and publish it.
        Fall back to the custom converter for legacy Quest data.
        """

        try:
            # ROS2 CDR messages normally begin with the 4-byte
            # encapsulation header 00 01 00 00.
            if len(data) >= 4 and data[:4] == b'\x00\x01\x00\x00':
                message_type = type(self.msg)
                message = deserialize_message(data, message_type)

                print(
                    f"[ROS2 CDR] {self.topic}: "
                    f"{message}",
                    flush=True
                )

                self.pub.publish(message)

            else:
                # Fallback for the older Quest/ROS1-style serialization
                message = convert_data(self.topic, data)

                if message is not None:
                    self.pub.publish(message)
                else:
                    print(
                        f"[WARNING] Could not convert data for {self.topic}",
                        flush=True
                    )

        except Exception as e:
            print(
                f"[ERROR] Failed to process {self.topic}: {e}",
                flush=True
            )

        return None

    def unregister(self):
        """

        Returns:

        """
        self.destroy_publisher(self.pub)
        self.destroy_node()
