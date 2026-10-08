cmake_minimum_required(VERSION 3.8)
project(showroom_core)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/showroom_monitor.py
    scripts/showroom_panel.py
    scripts/showroom_speed_profile.py
    scripts/showroom_task_manager.py
  DESTINATION lib/${PROJECT_NAME}
)

install(
  FILES
    scripts/showroom_action_policy.py
    scripts/showroom_business_logic.py
    scripts/showroom_plan.py
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

  foreach(test_name
      action_policy
      business_logic
      monitor_logic
      panel
      plan
      speed_profile
      task_action
      task_units)
    ament_add_test(
      showroom_core_${test_name}
      COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/test/test_${test_name}.py
      GENERATE_RESULT_FOR_RETURN_CODE_ZERO
      TIMEOUT 30
    )
  endforeach()
endif()

ament_package()
