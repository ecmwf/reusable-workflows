
cd ${TMPDIR}

chmod -R u+w "$SCRATCH/test-install-ecflow" 2>/dev/null || chmod -R u+w "$SCRATCH/test-install-ecflow" 2>/dev/null || true
mkdir -p "$SCRATCH/test-install-ecflow"

echo "Build started: $(date -u)"
echo "Build name: ecflow-hpc"
echo "Repository: ecflow"




echo "::group::Loading modules"
module reset
echo "Loading gcc/8.5.0"
module load gcc/8.5.0
echo "Loading ninja"
module load ninja
module list
echo "::endgroup::"
echo "::group::Export environment variables"
echo "::endgroup::"

    echo "::group::Fetching main package: ecflow"
    cd ${TMPDIR}
    mkdir ${TMPDIR}/ecflow
    cd ${TMPDIR}/ecflow
    git init
    git remote add origin https://{{ github_user }}:{{ github_token }}@github.com/ecmwf/ecflow.git
    git fetch --depth 20 --tags origin 6b4cd3f2e3b85e13eb583130b20ae52d8ce3a0a1
    git checkout FETCH_HEAD
    echo "::endgroup::"
cd ${TMPDIR}/ecflow


    if [ -e VERSION ]; then
        export PACKAGE_VERSION=$(cat VERSION)
    elif [ -e CMakeLists.txt ]; then
        export PACKAGE_VERSION=$(grep -oP  'project\(.*VERSION\s+\K[0-9]+(\.[0-9]+){0,3}'  CMakeLists.txt)
    elif [ -e bundle.yml ];then
        export PACKAGE_VERSION=$(python3 -c "import yaml; print(yaml.safe_load(open('bundle.yml', 'r'))['version'])")
    else
        echo "Error: Could not find CMakeLists.txt, VERSION, or bundle.yml"
        error_trap
    fi

    if [ -z "$PACKAGE_VERSION" ]; then
        echo "Error: Could not parse package version."
        error_trap
    fi

    echo "ecflow detected version $PACKAGE_VERSION"

cd ${TMPDIR}/ecflow
mkdir -p build && cd build

INSTALL_PREFIX="$SCRATCH/test-install-ecflow"
export INSTALL_PREFIX

echo "::group::Cleaning before install: ecflow"
if cd $SCRATCH/test-install-ecflow 2>/dev/null; then
  # Resolve symlinks and '..' then validate the path is safe to clean.
  if ! CLEAN_PATH="$(realpath -e "$SCRATCH/test-install-ecflow")"; then
      echo "SAFETY ERROR: Refusing to clean $SCRATCH/test-install-ecflow - could not resolve target path"
      exit 1
  fi
  # Automatic dry-run cleaning: only ever permitted under $SCRATCH.
  if [[ -z "${SCRATCH:-}" ]]; then
      echo "SAFETY ERROR: Refusing automatic dry-run clean of $CLEAN_PATH - \$SCRATCH is not set. Set clean_before_install: true to clean other locations."
      exit 1
  fi
  if ! SCRATCH_PATH="$(realpath -e "$SCRATCH")"; then
      echo "SAFETY ERROR: Refusing automatic dry-run clean of $CLEAN_PATH - could not resolve \$SCRATCH"
      exit 1
  fi
  if [[ "$CLEAN_PATH" != "$SCRATCH_PATH"/* ]]; then
      echo "SAFETY ERROR: Refusing automatic dry-run clean of $CLEAN_PATH - not under \$SCRATCH. Set clean_before_install: true to clean other locations."
      exit 1
  fi
  echo "Removing the previous install: $SCRATCH/test-install-ecflow"
  find . -type f -or -type d -exec chmod u+w {} \;
  find . -mindepth 1 -maxdepth 1 -exec rm -rfv -- {} +
  cd -
else
  echo "Nothing to clean up."
fi
echo "::endgroup::"


echo "::group::Stage: python313"

module load boost/1.87.0
module load python3/3.13.13-01
module load qt/6.6.1
module load cmake/new
module load ecbuild/new

echo "::STAGE_MARKER::python313"

ecbuild --prefix=$SCRATCH/test-install-ecflow .. -GNinja -DINSTALL_LIB_DIR=lib -DCMAKE_VERBOSE_MAKEFILE=ON -DENABLE_ALL_TESTS=ON -DENABLE_STATIC_BOOST_LIBS=ON -DENABLE_WARNINGS=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -DCMAKE_PYTHON_INSTALL_TYPE=local -DINSTALL_LIB_DIR=lib -DUI_SYSTEM_SERVERS_LIST=/ec/vol/ecflow_def/servers.list.all -DCMAKE_PREFIX_PATH=/usr/local/apps/python3/3.13.13-01/lib/python3.13/site-packages/pybind11/share/cmake/pybind11

cd ${TMPDIR}/ecflow/build
time cmake --build . -j64

echo "Running tests for stage: python313"
ctest --output-on-failure -j 8 -L nightly

cd ${TMPDIR}/ecflow/build
time cmake --install . > /dev/null


module unload ecbuild/new
module unload cmake/new
module unload qt/6.6.1
module unload python3/3.13.13-01
module unload boost/1.87.0

echo "::endgroup::"
echo "::group::Stage: python312"

module load boost/1.87.0
module load python3/3.12.9-01
module load cmake/new
module load ecbuild/new

echo "::STAGE_MARKER::python312"

cd ${TMPDIR}/ecflow
rm -rf build && mkdir build && cd build
ecbuild --prefix=$SCRATCH/test-install-ecflow .. -GNinja -DINSTALL_LIB_DIR=lib -DCMAKE_VERBOSE_MAKEFILE=ON -DENABLE_ALL_TESTS=ON -DENABLE_STATIC_BOOST_LIBS=ON -DENABLE_WARNINGS=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -DCMAKE_PYTHON_INSTALL_TYPE=local -DINSTALL_LIB_DIR=lib -DUI_SYSTEM_SERVERS_LIST=/ec/vol/ecflow_def/servers.list.all -DCMAKE_PREFIX_PATH=/usr/local/apps/python3/3.12.9-01/lib/python3.12/site-packages/pybind11/share/cmake/pybind11 -DENABLE_UI=OFF

cd ${TMPDIR}/ecflow/build
time cmake --build . -j64

echo "Running tests for stage: python312"
ctest --output-on-failure -j 8 -L nightly

cmake --install . --component python



module unload ecbuild/new
module unload cmake/new
module unload python3/3.12.9-01
module unload boost/1.87.0

echo "::endgroup::"
echo "::group::Stage: python311"

module load boost/1.87.0
module load python3/3.11.8-01
module load cmake/new
module load ecbuild/new

echo "::STAGE_MARKER::python311"

cd ${TMPDIR}/ecflow
rm -rf build && mkdir build && cd build
ecbuild --prefix=$SCRATCH/test-install-ecflow .. -GNinja -DINSTALL_LIB_DIR=lib -DCMAKE_VERBOSE_MAKEFILE=ON -DENABLE_ALL_TESTS=ON -DENABLE_STATIC_BOOST_LIBS=ON -DENABLE_WARNINGS=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -DCMAKE_PYTHON_INSTALL_TYPE=local -DINSTALL_LIB_DIR=lib -DUI_SYSTEM_SERVERS_LIST=/ec/vol/ecflow_def/servers.list.all -DCMAKE_PREFIX_PATH=/usr/local/apps/python3/3.11.8-01/lib/python3.11/site-packages/pybind11/share/cmake/pybind11 -DBoost_ROOT=/usr/local/apps/boost/1.87.0/GNU/8.5 -DBoost_INCLUDE_DIR=/usr/local/apps/boost/1.87.0/GNU/8.5/include -DPython3_ROOT_DIR=/usr/local/apps/python3/3.11.8-01 -DPython3_EXECUTABLE=/usr/local/apps/python3/3.11.8-01/bin/python3 -DPython3_INCLUDE_DIRS=/usr/local/apps/python3/3.11.8-01/include/python3.11 -DPython3_LIBRARIES=/usr/local/apps/python3/3.11.8-01/lib64/libpython3.11.so -DPython3_LIBRARY_DIRS=/usr/local/apps/python3/3.11.8-01/lib64 -DENABLE_UI=OFF

cd ${TMPDIR}/ecflow/build
time cmake --build . -j64

echo "Running tests for stage: python311"
ctest --output-on-failure -j 8 -L nightly

cmake --install . --component python



module unload ecbuild/new
module unload cmake/new
module unload python3/3.11.8-01
module unload boost/1.87.0

echo "::endgroup::"
echo "::group::Stage: python310"

module load boost/1.87.0
module load python3/3.10.10-01
module load cmake/new
module load ecbuild/new

echo "::STAGE_MARKER::python310"

cd ${TMPDIR}/ecflow
rm -rf build && mkdir build && cd build
ecbuild --prefix=$SCRATCH/test-install-ecflow .. -GNinja -DINSTALL_LIB_DIR=lib -DCMAKE_VERBOSE_MAKEFILE=ON -DENABLE_ALL_TESTS=ON -DENABLE_STATIC_BOOST_LIBS=ON -DENABLE_WARNINGS=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -DCMAKE_PYTHON_INSTALL_TYPE=local -DINSTALL_LIB_DIR=lib -DUI_SYSTEM_SERVERS_LIST=/ec/vol/ecflow_def/servers.list.all -DCMAKE_PREFIX_PATH=/usr/local/apps/python3/3.10.10-01/lib/python3.10/site-packages/pybind11/share/cmake/pybind11 -DENABLE_UI=OFF -DBoost_ROOT=/usr/local/apps/boost/1.87.0/GNU/8.5 -DBoost_INCLUDE_DIR=/usr/local/apps/boost/1.87.0/GNU/12.2/include -DPython3_ROOT_DIR=/usr/local/apps/python3/3.10.10-01 -DPython3_EXECUTABLE=/usr/local/apps/python3/3.10.10-01/bin/python3 -DPython3_INCLUDE_DIRS=/usr/local/apps/python3/3.10.10-01/include/python3.10 -DPython3_LIBRARIES=/usr/local/apps/python3/3.10.10-01/lib64/libpython3.10.so -DPython3_LIBRARY_DIRS=/usr/local/apps/python3/3.10.10-01/lib64

cd ${TMPDIR}/ecflow/build
time cmake --build . -j64

echo "Running tests for stage: python310"
ctest --output-on-failure -j 8 -L nightly

cmake --install . --component python



module unload ecbuild/new
module unload cmake/new
module unload python3/3.10.10-01
module unload boost/1.87.0

echo "::endgroup::"
echo "::group::Stage: python38"

module load boost/1.87.0
module load python3/3.8.8-01
module load cmake/new
module load ecbuild/new

echo "::STAGE_MARKER::python38"

cd ${TMPDIR}/ecflow
rm -rf build && mkdir build && cd build
ecbuild --prefix=$SCRATCH/test-install-ecflow .. -GNinja -DINSTALL_LIB_DIR=lib -DCMAKE_VERBOSE_MAKEFILE=ON -DENABLE_ALL_TESTS=ON -DENABLE_STATIC_BOOST_LIBS=ON -DENABLE_WARNINGS=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -DCMAKE_PYTHON_INSTALL_TYPE=local -DINSTALL_LIB_DIR=lib -DUI_SYSTEM_SERVERS_LIST=/ec/vol/ecflow_def/servers.list.all -DCMAKE_PREFIX_PATH=/usr/local/apps/python3/3.8.8-01/lib/python3.8/site-packages/pybind11/share/cmake/ -DENABLE_UI=OFF -DBoost_ROOT=/usr/local/apps/boost/1.87.0/GNU/8.5 -DBoost_INCLUDE_DIR=/usr/local/apps/boost/1.87.0/GNU/8.5/include -DPython3_ROOT_DIR=/usr/local/apps/python3/3.8.8-01 -DPython3_EXECUTABLE=/usr/local/apps/python3/3.8.8-01/bin/python3 -DPython3_INCLUDE_DIRS=/usr/local/apps/python3/3.8.8-01/include/python3.8 -DPython3_LIBRARIES=/usr/local/apps/python3/3.8.8-01/lib64/libpython3.8.so -DPython3_LIBRARY_DIRS=/usr/local/apps/python3/3.8.8-01/lib64

cd ${TMPDIR}/ecflow/build
time cmake --build . -j64

echo "Running tests for stage: python38"
ctest --output-on-failure -j 8 -L nightly

cmake --install . --component python



module unload ecbuild/new
module unload cmake/new
module unload python3/3.8.8-01
module unload boost/1.87.0

echo "::endgroup::"

cd ${TMPDIR}
export ecflow_DIR="$SCRATCH/test-install-ecflow"
export ECFLOW_DIR="$SCRATCH/test-install-ecflow"
export ECFLOW_PATH="$SCRATCH/test-install-ecflow"
export PATH="$SCRATCH/test-install-ecflow/bin:$PATH"
export BIN_PATH="$SCRATCH/test-install-ecflow/bin:$BIN_PATH"
export INCLUDE_PATH="$SCRATCH/test-install-ecflow/include:$INCLUDE_PATH"
export INSTALL_PATH="$SCRATCH/test-install-ecflow:$INSTALL_PATH"
export LIB_PATH="$SCRATCH/test-install-ecflow/lib:$LIB_PATH"
export LD_LIBRARY_PATH="$SCRATCH/test-install-ecflow/lib:$LD_LIBRARY_PATH"








# Copy output file as build log to install prefix
OUTPUT_SRC="${__OUTPUT_FILE:-/proc/self/fd/1}"
cp "$OUTPUT_SRC" "$SCRATCH/test-install-ecflow/build.log" 2>/dev/null || true

echo "::group::Redact build log"
if [ -f "$SCRATCH/test-install-ecflow/build.log" ]; then
    sed -i \
        -e 's|{{ github_user }}|[REDACTED]|g' \
        -e 's|{{ github_token }}|[REDACTED]|g' \
        "$SCRATCH/test-install-ecflow/build.log"
fi
echo "::endgroup::"

echo "::group::Generate README.txt"
INSTALL_PREFIX="$SCRATCH/test-install-ecflow" BUILD_LOG="$SCRATCH/test-install-ecflow/build.log" python3 << 'GENERATE_README'
import os
import re

install_prefix = os.environ["INSTALL_PREFIX"]
build_log = os.environ["BUILD_LOG"]
readme_file = os.path.join(install_prefix, "README.txt")

if not os.path.isdir(install_prefix):
    print(f"Install prefix {install_prefix} not found, skipping README generation")
    exit(0)

if not os.path.exists(build_log):
    print(f"Build log not found at {build_log}, skipping README generation")
    exit(0)

with open(build_log, "r", errors="replace") as f:
    log_content = f.read()

# Remove ANSI color codes
log_content = re.sub(r'\x1b\[[0-9;]*m', '', log_content)

# Extract package version lines (deduplicated)
seen = set()
readme_lines = []
current_stage = None

for line in log_content.splitlines():
    # Track stage markers for staged builds
    if "::STAGE_MARKER::" in line:
        stage_match = re.search(r'::STAGE_MARKER::(\S+)', line)
        if stage_match:
            current_stage = stage_match.group(1)
        continue

    if re.match(r'^--\s+\[', line):
        match = re.search(r'\[([^\]]+)\]', line)
        if match:
            pkg = match.group(1)
            if pkg not in seen:
                seen.add(pkg)
                readme_lines.append(line.strip())
    elif line.startswith("-- system"):
        system_line = line.strip()
        if current_stage:
            system_line += f" [stage: {current_stage}]"
        readme_lines.append(system_line)

if readme_lines:
    with open(readme_file, "w") as f:
        f.write("\n".join(readme_lines) + "\n")
    print(f"Generated README.txt with {len(readme_lines)} entries:")
    print("\n".join(readme_lines[:10]))
    if len(readme_lines) > 10:
        print(f"... and {len(readme_lines) - 10} more entries")
else:
    print("No package version info found in build log")
GENERATE_README
echo "::endgroup::"

echo "::group::Lock permissions"
echo "Locking permissions on $SCRATCH/test-install-ecflow"
timeout 300 chmod -R a-w "$SCRATCH/test-install-ecflow" || echo "Warning: chmod timed out or failed (continuing anyway)"
echo "::endgroup::"

