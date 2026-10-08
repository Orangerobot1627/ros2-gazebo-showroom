#!/usr/bin/env bash
# One-command test runner for the Gazebo showroom.
#
#   ./run_tests.sh            run every functional test script
#   ./run_tests.sh --lint     also run the ament style/lint checks
#   ./run_tests.sh --build    colcon build first, then run the tests
#
# Functional tests are the standalone test/test_*.py scripts installed by each
# package (they are plain assertions, not pytest cases). The --lint pass runs
# the ament flake8 / pep257 / copyright / xmllint hooks so CI parity is local.
set -o pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd -- "${script_dir}/../.." && pwd)"
ros_setup="/opt/ros/jazzy/setup.bash"
workspace_setup="${workspace_dir}/install/setup.bash"

with_lint=0
do_build=0
timeout_sec=180
for arg in "$@"; do
  case "${arg}" in
    --lint) with_lint=1 ;;
    --build) do_build=1 ;;
    --timeout=*) timeout_sec="${arg#*=}" ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Unknown option: ${arg}" >&2; exit 2 ;;
  esac
done

if [[ ! -r "${ros_setup}" ]]; then
  echo "ROS 2 Jazzy not found: ${ros_setup}" >&2
  exit 1
fi

source "${ros_setup}"

if [[ "${do_build}" -eq 1 ]]; then
  echo ">> colcon build --symlink-install"
  ( cd "${workspace_dir}" && colcon build --symlink-install ) || exit 1
fi

if [[ ! -r "${workspace_setup}" ]]; then
  echo "Workspace not built: ${workspace_setup}" >&2
  echo "Run ${script_dir}/run_tests.sh --build first." >&2
  exit 1
fi
source "${workspace_setup}"

# Keep ROS logs writable even when $HOME is read-only (sandbox / CI runners).
export ROS_LOG_DIR="${ROS_LOG_DIR:-$(mktemp -d -t showroom_ros_log_XXXXXX)}"

pass=0
fail=0
failed_tests=()

echo "=============================================================="
echo " Functional test scripts"
echo "=============================================================="
while IFS= read -r test_file; do
  rel="${test_file#"${workspace_dir}"/src/showroom_gz/}"
  printf '  %-58s ' "${rel}"
  output="$(timeout "${timeout_sec}" python3 "${test_file}" 2>&1)"
  status=$?
  if [[ ${status} -eq 0 ]]; then
    echo "PASS"
    pass=$((pass + 1))
  else
    echo "FAIL (exit ${status})"
    fail=$((fail + 1))
    failed_tests+=("${rel}")
    echo "${output}" | tail -n 6 | sed 's/^/      /'
  fi
done < <(find "${script_dir}" -path '*/test/test_*.py' | sort)

if [[ "${with_lint}" -eq 1 ]]; then
  echo
  echo "=============================================================="
  echo " ament style / lint checks"
  echo "=============================================================="
  packages=(showroom_bringup showroom_core showroom_description showroom_gz_sim
            showroom_interaction showroom_interfaces showroom_navigation)
  ( cd "${workspace_dir}" && \
    timeout 400 colcon test --packages-select "${packages[@]}" \
      --ctest-args -R 'flake8|copyright|pep257|cpplint|uncrustify|xmllint' \
      >/dev/null 2>&1 )
  lint_fail=0
  for pkg in "${packages[@]}"; do
    dir="${workspace_dir}/build/${pkg}/test_results/${pkg}"
    count=$(grep -l 'failures="[1-9]\|errors="[1-9]' \
      "${dir}/flake8.xunit.xml" "${dir}/pep257.xunit.xml" \
      "${dir}"/copyright*.xml "${dir}"/cpplint*.xml \
      "${dir}"/uncrustify*.xml "${dir}/xmllint.xunit.xml" 2>/dev/null | wc -l)
    printf '  %-24s ' "${pkg}"
    if [[ "${count}" -eq 0 ]]; then
      echo "PASS"
    else
      echo "FAIL (${count} report file(s))"
      lint_fail=$((lint_fail + 1))
    fi
  done
  if [[ "${lint_fail}" -gt 0 ]]; then
    fail=$((fail + lint_fail))
    failed_tests+=("ament lint")
  else
    pass=$((pass + ${#packages[@]}))
  fi
fi

echo
echo "=============================================================="
echo " Summary: ${pass} passed, ${fail} failed"
[[ ${fail} -eq 0 ]] || { printf ' Failed: %s\n' "${failed_tests[@]}"; }
echo "=============================================================="
[[ ${fail} -eq 0 ]]
