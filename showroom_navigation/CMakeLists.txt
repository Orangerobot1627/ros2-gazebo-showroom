cmake_minimum_required(VERSION 3.8)
project(showroom_navigation)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/showroom_default_mission.py
    scripts/showroom_navigation_gateway.py
    scripts/showroom_nav2_adapter.py
    scripts/showroom_route_visualizer.py
  DESTINATION lib/${PROJECT_NAME}
)

install(
  FILES
    scripts/showroom_navigation.py
    scripts/showroom_nav2_health.py
    scripts/showroom_task_units.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_test REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)

  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  ament_add_test(
    showroom_navigation_graph
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/test/test_navigation.py
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    TIMEOUT 30
  )

  ament_add_test(
    showroom_nav2_health
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/test/test_nav2_health.py
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    TIMEOUT 30
  )

  ament_add_test(
    showroom_route_migration
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/test/test_route_migration.py
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    TIMEOUT 30
  )

  ament_add_test(
    showroom_route_visualization
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/test/test_route_visualizer.py
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    TIMEOUT 30
  )
endif()

ament_package()
