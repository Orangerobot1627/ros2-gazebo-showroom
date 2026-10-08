cmake_minimum_required(VERSION 3.8)
project(showroom_interaction)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/showroom_asr.py
    scripts/showroom_llm_bridge.py
    scripts/showroom_tts.py
  DESTINATION lib/${PROJECT_NAME}
)

install(
  FILES
    scripts/showroom_llm_contract.py
    scripts/showroom_llm_core.py
    scripts/showroom_llm_prompt.py
    scripts/showroom_ollama_client.py
    scripts/showroom_plan.py
    scripts/showroom_voice_core.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_test REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)

  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  foreach(test_name llm_bridge_logic voice_core interaction_launch intent_scenarios)
    ament_add_test(
      showroom_interaction_${test_name}
      COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/test/test_${test_name}.py
      GENERATE_RESULT_FOR_RETURN_CODE_ZERO
      TIMEOUT 30
    )
  endforeach()
endif()

ament_package()
