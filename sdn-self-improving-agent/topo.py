#!/usr/bin/env python3
"""
topo.py: Linear SDN Mininet Topology with OpenFlow 1.3
4 switches (s1, s2, s3, s4) and 8 hosts (h1..h8).
Includes primary and secondary paths between intermediate switches to enable
realistic flow rerouting and congestion mitigation.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.clean import cleanup
import sys
import time

class LinearSDNTopo(Topo):
    """
    Linear SDN Topology:
    4 switches: s1, s2, s3, s4
    8 hosts: 2 per switch
      s1: h1 (10.0.0.1), h2 (10.0.0.2)
      s2: h3 (10.0.0.3), h4 (10.0.0.4)
      s3: h5 (10.0.0.5), h6 (10.0.0.6)
      s4: h7 (10.0.0.7), h8 (10.0.0.8)

    Switch Interconnects:
      s1 <-> s2: Primary Link (10 Mbps, 3ms delay)
      s2 <-> s3: Primary Link (10 Mbps, 5ms delay, max_queue=40)
                 Secondary / Alternate Link (10 Mbps, 12ms delay, max_queue=40)
      s3 <-> s4: Primary Link (10 Mbps, 3ms delay)
    """
    def build(self):
        # 1. Add 4 Switches (OpenFlow 1.3)
        switches = []
        for i in range(1, 5):
            sw = self.addSwitch(f's{i}', protocols='OpenFlow13', dpid=f'{i:016x}')
            switches.append(sw)

        s1, s2, s3, s4 = switches

        # 2. Add 8 Hosts (2 per switch)
        hosts = []
        for i in range(1, 9):
            ip = f'10.0.0.{i}/24'
            mac = f'00:00:00:00:00:{i:02x}'
            h = self.addHost(f'h{i}', ip=ip, mac=mac)
            hosts.append(h)

        # Connect hosts to respective switches
        # s1: h1, h2 (port 1, 2)
        self.addLink(hosts[0], s1, bw=100, delay='1ms')
        self.addLink(hosts[1], s1, bw=100, delay='1ms')

        # s2: h3, h4
        self.addLink(hosts[2], s2, bw=100, delay='1ms')
        self.addLink(hosts[3], s2, bw=100, delay='1ms')

        # s3: h5, h6
        self.addLink(hosts[4], s3, bw=100, delay='1ms')
        self.addLink(hosts[5], s3, bw=100, delay='1ms')

        # s4: h7, h8
        self.addLink(hosts[6], s4, bw=100, delay='1ms')
        self.addLink(hosts[7], s4, bw=100, delay='1ms')

        # 3. Inter-switch Links
        # s1 <-> s2 (Trunk)
        self.addLink(s1, s2, bw=20, delay='2ms')

        # s2 <-> s3 Core Bottleneck Links:
        # Link A (Primary): port index mapped during link creation
        self.addLink(s2, s3, bw=10, delay='5ms', max_queue_size=40)
        # Link B (Secondary / Alternate path for rerouting):
        self.addLink(s2, s3, bw=10, delay='12ms', max_queue_size=40)

        # s3 <-> s4 (Trunk)
        self.addLink(s3, s4, bw=20, delay='2ms')


def create_network(controller_ip='127.0.0.1', controller_port=6653):
    """Initializes and returns the Mininet network instance."""
    topo = LinearSDNTopo()
    net = Mininet(
        topo=topo,
        switch=OVSSwitch,
        link=TCLink,
        controller=None,
        autoSetMacs=True
    )
    for sw in net.switches:
        sw.protocols = 'OpenFlow13'

    c0 = net.addController('c0', controller=RemoteController, ip=controller_ip, port=controller_port)
    return net


if __name__ == '__main__':
    cleanup()
    print("Starting Linear SDN 4-Switch 8-Host Topology...")
    net = create_network()
    net.start()
    print("*** Network is online. Testing reachability...")
    net.pingAll()
    CLI(net)
    net.stop()
    cleanup()
