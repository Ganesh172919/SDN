"""
Phase 1 — Testbed topology.

Linear topology, OpenFlow 1.3, 4 switches / 8 hosts (2 hosts per switch):

    h1,h2 - s1 - s2 - s3 - s4 - h7,h8
                 |         |
              h3,h4      h5,h6

Run directly for an interactive Mininet CLI:

    sudo python3 topo.py

or import `build_net()` from traffic_gen.py / eval/run_ablation.py to drive
a scripted run.

Requires: a real Linux host with Open vSwitch + Mininet installed and a Ryu
controller (see ryu_client.py / README.md) listening on RYU_REST_PORT for
the ofctl_rest REST API. This will NOT run inside a restricted / rootless
container — Mininet needs to create real network namespaces and OVS
bridges.
"""

import sys

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

import config


def build_net(controller_ip="127.0.0.1", controller_port=6653):
    """Build (but do not start) the linear 4-switch / 8-host testbed."""
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        build=False,
    )

    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip=controller_ip,
        port=controller_port,
    )

    switches = []
    for i in range(1, config.NUM_SWITCHES + 1):
        sw = net.addSwitch(f"s{i}", protocols="OpenFlow13")
        switches.append(sw)

    # chain the switches: s1-s2-s3-s4
    for i in range(len(switches) - 1):
        net.addLink(
            switches[i],
            switches[i + 1],
            bw=config.LINK_BW_MBPS,
            delay=config.LINK_DELAY_MS,
            loss=config.LINK_LOSS_PCT,
        )

    # HOSTS_PER_SWITCH hosts hang off every switch
    host_num = 1
    for sw in switches:
        for _ in range(config.HOSTS_PER_SWITCH):
            h = net.addHost(
                f"h{host_num}",
                ip=f"10.0.0.{host_num}/24",
            )
            net.addLink(h, sw, bw=config.LINK_BW_MBPS)
            host_num += 1

    net.build()
    c0.start()
    for sw in switches:
        sw.start([c0])

    return net


def main():
    setLogLevel("info")
    net = build_net()
    info("*** Testbed up: 4 switches (s1..s4), 8 hosts (h1..h8), OpenFlow13\n")
    info("*** Ryu should already be running: \n")
    info(
        "***   ryu-manager --ofp-tcp-listen-port 6653 "
        "ryu.app.ofctl_rest ryu.app.simple_switch_13\n"
    )
    CLI(net)
    net.stop()


if __name__ == "__main__":
    sys.exit(main())
