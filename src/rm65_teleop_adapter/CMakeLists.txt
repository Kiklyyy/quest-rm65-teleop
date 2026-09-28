cmake_minimum_required(VERSION 3.8)
project(rm65_teleop_adapter)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(quest2ros REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(control_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(trajectory_msgs REQUIRED)
find_package(rm_ros_interfaces REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
add_library(adapter_logic src/adapter_logic.cpp)
target_sources(adapter_logic PRIVATE src/home_config.cpp)
target_sources(adapter_logic PRIVATE src/home_trajectory.cpp)
target_sources(adapter_logic PRIVATE src/quaternion_math.cpp)
target_sources(adapter_logic PRIVATE src/quest_orientation_tracker.cpp)
target_include_directories(adapter_logic PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include> $<INSTALL_INTERFACE:include>)
add_library(home_action_client src/home_action_client.cpp)
target_include_directories(home_action_client PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include> $<INSTALL_INTERFACE:include>)
ament_target_dependencies(home_action_client rclcpp rclcpp_action control_msgs trajectory_msgs)
add_executable(rm65_teleop_adapter_node src/adapter_node.cpp)
target_link_libraries(rm65_teleop_adapter_node adapter_logic home_action_client)
ament_target_dependencies(rm65_teleop_adapter_node geometry_msgs quest2ros rclcpp rclcpp_action control_msgs sensor_msgs trajectory_msgs rm_ros_interfaces std_msgs std_srvs)
install(TARGETS adapter_logic home_action_client rm65_teleop_adapter_node ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION lib/${PROJECT_NAME})
install(PROGRAMS scripts/teleop_status_monitor.py DESTINATION lib/${PROJECT_NAME} RENAME teleop_status_monitor)
install(FILES scripts/teleop_status_logic.py DESTINATION lib/${PROJECT_NAME})
install(PROGRAMS scripts/right_linkerhand_node.py DESTINATION lib/${PROJECT_NAME} RENAME right_linkerhand_node)
install(FILES scripts/right_linkerhand_logic.py DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})
install(FILES README.md DESTINATION share/${PROJECT_NAME})
if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_gtest(test_quaternion_math test/test_quaternion_math.cpp)
  target_link_libraries(test_quaternion_math adapter_logic)
  target_include_directories(test_quaternion_math PRIVATE include)
  ament_add_gtest(test_quest_orientation_tracker test/test_quest_orientation_tracker.cpp)
  target_link_libraries(test_quest_orientation_tracker adapter_logic)
  target_include_directories(test_quest_orientation_tracker PRIVATE include)
  ament_add_gtest(test_adapter_logic test/test_adapter_logic.cpp)
  target_link_libraries(test_adapter_logic adapter_logic)
  target_include_directories(test_adapter_logic PRIVATE include)
  ament_add_gtest(test_adapter_config test/test_adapter_config.cpp)
  target_link_libraries(test_adapter_config adapter_logic)
  target_include_directories(test_adapter_config PRIVATE include)
  ament_add_gtest(test_home_action_client test/test_home_action_client.cpp)
  ament_target_dependencies(test_home_action_client rclcpp rclcpp_action control_msgs trajectory_msgs)
  target_link_libraries(test_home_action_client home_action_client adapter_logic)
  target_include_directories(test_home_action_client PRIVATE include)
  set_tests_properties(test_home_action_client PROPERTIES ENVIRONMENT "ROS_DOMAIN_ID=143;ROS_LOCALHOST_ONLY=1")
  ament_add_gtest(test_home_trajectory test/test_home_trajectory.cpp)
  target_link_libraries(test_home_trajectory adapter_logic)
  target_include_directories(test_home_trajectory PRIVATE include)
  ament_add_gtest(test_quest_face_button test/test_quest_face_button.cpp)
  target_include_directories(test_quest_face_button PRIVATE include)
  ament_add_gtest(test_input_deadman test/test_input_deadman.cpp)
  target_link_libraries(test_input_deadman adapter_logic)
  target_include_directories(test_input_deadman PRIVATE include)
  # Ignore incompatible user-site pytest plugins on the ROS 2 Humble host.
  set(ENV{PYTEST_DISABLE_PLUGIN_AUTOLOAD} "1")
  ament_add_pytest_test(
    test_teleop_status_logic
    test/test_teleop_status_logic.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1)
  ament_add_pytest_test(
    test_home_synthetic_probe
    test/home_synthetic_probe.py
    PYTHON_EXECUTABLE /usr/bin/python3
    TIMEOUT 90
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_motion_profiles
    test/test_motion_profiles.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1)
  ament_add_pytest_test(
    test_left_interface
    test/test_left_interface.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_left_dry_run_probe
    test/left_dry_run_probe.py
    PYTHON_EXECUTABLE /usr/bin/python3
    TIMEOUT 45
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_left_endpoint_isolation_probe
    test/left_endpoint_isolation_probe.py
    PYTHON_EXECUTABLE /usr/bin/python3
    TIMEOUT 45
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_right_linkerhand_logic
    test/test_right_linkerhand_logic.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1)
  ament_add_pytest_test(
    test_right_linkerhand_node
    test/test_right_linkerhand_node.py
    PYTHON_EXECUTABLE /usr/bin/python3
    TIMEOUT 45
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_right_linkerhand_launch
    test/test_right_linkerhand_launch.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_dual_quest_bringup_launch
    test/test_dual_quest_bringup_launch.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1)
  ament_add_pytest_test(
    test_right_linkerhand_transport
    test/test_right_linkerhand_transport.py
    PYTHON_EXECUTABLE /usr/bin/python3
    ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1)
endif()
ament_export_include_directories(include)
ament_export_libraries(adapter_logic)
ament_package()
