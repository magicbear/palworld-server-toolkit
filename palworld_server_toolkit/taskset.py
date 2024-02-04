#!/usr/bin/env python3

import psutil
import pprint

def main():
    cpu_cores = []
    phy_cores = []
    phy_core_id = {}
    core_info = {}
    pp = pprint.PrettyPrinter(width=80, compact=True, depth=4)
    with open("/proc/cpuinfo") as fp:
        for line in fp:
            info = line.strip().split(": ")
            if line.strip() == '':
                if int(core_info['core id']) not in phy_cores:
                    phy_cores.append(int(core_info['core id']))
                if int(core_info['core id']) not in phy_core_id:
                    phy_core_id[int(core_info['core id'])] = []
                phy_core_id[int(core_info['core id'])].append(int(core_info['processor']))
                cpu_cores.append(core_info)
                core_info = {}
            else:
                core_info[info[0].strip()] = ''.join(info[1:])
    
    performance_cores = []
    effective_cores = []
    for core_id in phy_core_id:
        if len(phy_core_id[core_id]) > 1:
            performance_cores.append(phy_core_id[core_id][0])
        else:
            effective_cores.append(phy_core_id[core_id][0])
    
    pal_srv = None
    for p in psutil.process_iter():
        if 'PalServer-Linux-Test' in p.name():
            if len(performance_cores) > 0:
                p.cpu_affinity(performance_cores)
            print("PID: %d  %s  RSS: %.2f MB  VMS: %.2f MB  CPU: %s" % (p.pid, p.name(), p.memory_info().rss / 1048576, p.memory_info().vms / 1048576,
                                                                        p.cpu_affinity()))
    
            thread_lists = {}
            for th in p.threads():
                p_th = psutil.Process(th.id)
                thread_lists[p_th.name()] = p_th
                print("  Thread %d: %s  CPU: %s" % (th.id, p_th.name(), p.cpu_affinity()))
            pal_srv = p
            n = 0
            for th_k in sorted(thread_lists.keys()):
                if 'gro-rker' in th_k:
                    thread_lists[th_k].cpu_affinity(performance_cores[n::4])
                    print("  Set Thread %s -> %s" % (th_k, performance_cores[n::4]))
                    n+=1

if __name__ == "__main__":
    main()
