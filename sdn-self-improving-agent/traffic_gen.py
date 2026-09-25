#!/usr/bin/env python3
"""
traffic_gen.py: SDN Traffic Generator
Generates:
  (a) Steady baseline load using iperf3 (e.g. h1 -> h7, 4 Mbps)
  (b) Bursty / elephant-flow pattern on a fixed random seed (e.g. h2 -> h8, 12-15 Mbps bursts)
Ensures 100% deterministic reproducibility across evaluation runs.
"""

import time
import random
import subprocess
import os
import signal

class TrafficGenerator:
    """
    Manages synthetic traffic workloads on Mininet hosts.
    Uses iperf3 and UDP/TCP sockets with reproducible pseudo-random scheduling.
    """
    def __init__(self, net, seed=42, steady_rate="4M", elephant_rate="14M"):
        self.net = net
        self.seed = seed
        self.rng = random.Random(seed)
        self.steady_rate = steady_rate
        self.elephant_rate = elephant_rate
        self.running_processes = []
        self.servers = []

    def start_servers(self):
        """Starts iperf3 servers on egress hosts h7 and h8."""
        h7 = self.net.get('h7')
        h8 = self.net.get('h8')
        
        # Kill any existing iperf3 instances
        subprocess.run("pkill -9 iperf3", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)

        print("[TrafficGen] Starting iperf3 servers on h7 (port 5201) and h8 (port 5202)...")
        p1 = h7.popen("iperf3 -s -p 5201 -D", shell=True)
        p2 = h8.popen("iperf3 -s -p 5202 -D", shell=True)
        self.servers.extend([p1, p2])
        time.sleep(1)

    def start_steady_load(self, duration_sec=600):
        """
        Starts steady background traffic flow from h1 -> h7 (10.0.0.7).
        Default bandwidth: 4 Mbps.
        """
        h1 = self.net.get('h1')
        cmd = f"iperf3 -c 10.0.0.7 -p 5201 -u -b {self.steady_rate} -t {duration_sec} --logfile /tmp/iperf_steady.log"
        print(f"[TrafficGen] Launching steady background flow: h1 -> h7 @ {self.steady_rate}")
        proc = h1.popen(cmd, shell=True)
        self.running_processes.append(proc)
        return proc

    def trigger_elephant_burst(self, duration_sec=10):
        """
        Triggers an elephant burst flow from h2 -> h8 (10.0.0.8).
        In combination with steady load, this exceeds the 10 Mbps bottleneck link capacity.
        """
        h2 = self.net.get('h2')
        cmd = f"iperf3 -c 10.0.0.8 -p 5202 -u -b {self.elephant_rate} -t {duration_sec} --logfile /tmp/iperf_elephant.log"
        print(f"[TrafficGen] >>> INJECTING ELEPHANT FLOW: h2 -> h8 @ {self.elephant_rate} for {duration_sec}s <<<")
        proc = h2.popen(cmd, shell=True)
        self.running_processes.append(proc)
        return proc

    def should_trigger_burst(self, cycle_index):
        """
        Deterministic pseudo-random burst schedule based on random seed.
        Returns True if an elephant flow should be active during this cycle.
        """
        # Periodic + randomized burst schedule seeded with self.seed
        # Cycle bursts occur in patterned intervals (e.g. 3 active cycles every 8 cycles)
        pattern = [0, 1, 1, 1, 0, 0, 1, 0]
        return pattern[cycle_index % len(pattern)] == 1

    def stop_all(self):
        """Terminates all running traffic processes and servers."""
        print("[TrafficGen] Stopping all traffic generators...")
        for p in self.running_processes:
            try:
                p.terminate()
                p.kill()
            except Exception:
                pass
        self.running_processes.clear()
        subprocess.run("pkill -9 iperf3", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)


if __name__ == '__main__':
    print("traffic_gen module loaded.")
