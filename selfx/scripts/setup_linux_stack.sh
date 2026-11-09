#!/usr/bin/env bash
# ==============================================================================
# SELF-X Linux SDN Stack Setup & Environment Verification
# Traceability: Task T01 | Deliverables D1, D3 | EC466 Team SDN_07
#
# Pinned Components:
#   - Mininet: 2.3.0+
#   - Open vSwitch: 2.13.0+
#   - Ryu SDN Framework: 4.34 (OpenFlow 1.3)
#   - Python: 3.9+ / 3.10+ / 3.11+
#   - iperf3: 3.7+
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo "SELF-X Live SDN Stack Setup & Verification"
echo "======================================================================"

# 1. Verify OS
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "[WARN] Not running directly on Linux (detected $(uname -s))."
    echo "       Mininet requires Linux network namespaces and OVS kernel modules."
    echo "       On macOS / Windows, use WSL2 Ubuntu 22.04 LTS or a Linux VM."
fi

# 2. Check Root Privileges (for network namespace creation)
if [[ $EUID -ne 0 ]]; then
    echo "[INFO] Running without root. Root privileges ('sudo') are needed"
    echo "       to instantiate OVS switches, network namespaces, and TCLink."
fi

# 3. Pinned Dependency Versions & Install Commands
echo ""
echo "[1/4] Checking Pinned Dependencies..."

check_cmd() {
    local cmd="$1"
    local desc="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "  [OK] $desc ($cmd) is installed: $($cmd --version 2>&1 | head -n 1)"
    else
        echo "  [MISSING] $desc ($cmd) is NOT installed."
    fi
}

check_cmd "python3" "Python 3 Interpreter"
check_cmd "ovs-vsctl" "Open vSwitch"
check_cmd "mn" "Mininet Network Emulator"
check_cmd "iperf3" "iperf3 Traffic Generator"
check_cmd "ryu-manager" "Ryu SDN Controller"

# 4. Debian / Ubuntu Installation Instructions
echo ""
echo "[2/4] Recommended Ubuntu 22.04 LTS Stack Installation Commands:"
cat << 'EOF'
sudo apt-get update && sudo apt-get install -y \
    openvswitch-switch \
    openvswitch-common \
    mininet \
    iperf3 \
    iproute2 \
    python3-pip \
    python3-dev \
    build-essential

# Install pinned Ryu Controller (4.34)
# Note: Ryu requires eventlet < 0.31.0 and greenlet
pip3 install eventlet==0.30.2 greenlet==1.1.2 ryu==4.34
EOF

# 5. Service Launch Commands
echo ""
echo "[3/4] Service Startup Instructions:"
cat << 'EOF'
# Step A: Start Open vSwitch daemon
sudo service openvswitch-switch start
sudo ovs-vsctl show

# Step B: Launch Ryu REST ofctl_rest + simple_switch_13 on TCP port 6653
ryu-manager --ofp-tcp-listen-port 6653 \
    ryu.app.ofctl_rest \
    ryu.app.simple_switch_13 &

# Step C: Launch the SELF-X Mininet Topology
sudo python3 selfx/topo.py --topology linear
EOF

# 6. Connectivity Smoke Test Command
echo ""
echo "[4/4] Automated Smoke Test:"
echo "  Run: python3 selfx/scripts/smoke_test_connectivity.py"
echo "======================================================================"

