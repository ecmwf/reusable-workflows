
cd ${TMPDIR}

chmod -R u+w "/usr/local/apps/ecflow/5.17.0" 2>/dev/null || chmod -R u+w "/usr/local/apps/ecflow/5.17.0" 2>/dev/null || true
mkdir -p "/usr/local/apps/ecflow/5.17.0"

echo "Build started: $(date -u)"
echo "Build name: ecflow-hpc-ag"
echo "Repository: ecflow"




echo "::group::Loading modules"
module reset
echo "Loading gcc/11.5.0"
module load gcc/11.5.0
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

INSTALL_PREFIX="/usr/local/apps/ecflow/5.17.0"
export INSTALL_PREFIX



echo "::group::Stage: python312"

module load boost/1.87.0
module load python3/3.12.9-01
module load cmake/new
module load ecbuild

echo "::STAGE_MARKER::python312"

ecbuild --prefix=/usr/local/apps/ecflow/5.17.0 .. -GNinja -DINSTALL_LIB_DIR=lib -DCMAKE_VERBOSE_MAKEFILE=ON -DENABLE_ALL_TESTS=ON -DENABLE_STATIC_BOOST_LIBS=ON -DENABLE_WARNINGS=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -DCMAKE_PYTHON_INSTALL_TYPE=local -DINSTALL_LIB_DIR=lib -DUI_SYSTEM_SERVERS_LIST=/ec/vol/ecflow_def/servers.list.all -DCMAKE_PREFIX_PATH=/usr/local/apps/python3/3.13.13-01/lib/python3.13/site-packages/pybind11/share/cmake/pybind11 -DENABLE_UI=OFF

cd ${TMPDIR}/ecflow/build
time cmake --build . -j64

echo "Running tests for stage: python312"
ctest --output-on-failure -j 8 -L nightly -E "s_foolproof|s_test|s_zombies"

cmake --install .



module unload ecbuild
module unload cmake/new
module unload python3/3.12.9-01
module unload boost/1.87.0

echo "::endgroup::"

cd ${TMPDIR}
export ecflow_DIR="/usr/local/apps/ecflow/5.17.0"
export ECFLOW_DIR="/usr/local/apps/ecflow/5.17.0"
export ECFLOW_PATH="/usr/local/apps/ecflow/5.17.0"
export PATH="/usr/local/apps/ecflow/5.17.0/bin:$PATH"
export BIN_PATH="/usr/local/apps/ecflow/5.17.0/bin:$BIN_PATH"
export INCLUDE_PATH="/usr/local/apps/ecflow/5.17.0/include:$INCLUDE_PATH"
export INSTALL_PATH="/usr/local/apps/ecflow/5.17.0:$INSTALL_PATH"
export LIB_PATH="/usr/local/apps/ecflow/5.17.0/lib:$LIB_PATH"
export LD_LIBRARY_PATH="/usr/local/apps/ecflow/5.17.0/lib:$LD_LIBRARY_PATH"








# Copy output file as build log to install prefix
OUTPUT_SRC="${__OUTPUT_FILE:-/proc/self/fd/1}"
cp "$OUTPUT_SRC" "/usr/local/apps/ecflow/5.17.0/build.log" 2>/dev/null || true

echo "::group::Redact build log"
if [ -f "/usr/local/apps/ecflow/5.17.0/build.log" ]; then
    sed -i \
        -e 's|{{ github_user }}|[REDACTED]|g' \
        -e 's|{{ github_token }}|[REDACTED]|g' \
        "/usr/local/apps/ecflow/5.17.0/build.log"
fi
echo "::endgroup::"

echo "::group::Generate README.txt"
INSTALL_PREFIX="/usr/local/apps/ecflow/5.17.0" BUILD_LOG="/usr/local/apps/ecflow/5.17.0/build.log" python3 << 'GENERATE_README'
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
echo "Locking permissions on /usr/local/apps/ecflow/5.17.0"
timeout 300 chmod -R a-w "/usr/local/apps/ecflow/5.17.0" || echo "Warning: chmod timed out or failed (continuing anyway)"
echo "::endgroup::"

echo "::group::Tag module"
echo "Tagging module ecflow version 5.17.0 as new on clusters ag"
module load modulemgr
modulemgr -m "ag" -f -v tag "ecflow" "5.17.0" "new"
echo "::endgroup::"
