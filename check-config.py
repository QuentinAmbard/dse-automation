#from subprocess import call
#print call(["ulimit"]).read()
import subprocess
import re

user = "root"
hosts = ["146.148.118.87"]

commands = {
    #Network checks
    "network": {"commands": [
        {"name": "net.core.rmem_max", "command": "sysctl net.core.rmem_max","contains": "=\s?16777216$"},
        {"name": "net.core.wmem_max", "command": "sysctl net.core.wmem_max","contains": "=\s?16777216$"},
        {"name": "net.core.rmem_default" ,"command": "sysctl net.core.rmem_default","contains": "=\s?16777216$"},
        {"name": "net.core.wmem_default", "command": "sysctl net.core.wmem_default","contains": "=\s?16777216$"},
        {"name": "net.core.optmem_max", "command": "sysctl net.core.optmem_max","contains": "=\s?40960$"},
        {"name": "net.ipv4.tcp_rmem", "command": "sysctl net.ipv4.tcp_rmem","contains": "=\s?4096\s87380\s16777216$"},
        {"name": "net.ipv4.tcp_wmem", "command": "sysctl net.ipv4.tcp_wmem","contains": "=\s?4096\s87380\s16777216$"},
        {"name": "vm.max_map_count", "command": "sysctl vm.max_map_count","contains": "=\s?1048575$"},
        {"name": "net.ipv4.tcp_moderate_rcvbuf", "command": "sysctl net.ipv4.tcp_moderate_rcvbuf","contains": "=\s?1$"},
        {"name": "net.ipv4.tcp_no_metrics_save", "command": "sysctl net.ipv4.tcp_no_metrics_save","contains": "=\s?1$"},
        {"name": "net.ipv4.tcp_mtu_probing", "command": "sysctl net.ipv4.tcp_mtu_probing","contains": "=\s?1$"},
        {"name": "net.core.default_qdisc", "command": "sysctl net.core.default_qdisc","contains": "=\s?fq$"}
    ]},
    #Memory checks
    "memory": {"commands": [
        {"name": "vm.min_free_kbytes", "command": "sysctl vm.min_free_kbytes","contains": "=\s?1048576$"},
        {"name": "vm.dirty_background_ratio", "command": "sysctl vm.dirty_background_ratio","contains": "=\s?5$"},
        {"name": "vm.dirty_ratio", "command": "sysctl vm.dirty_ratio","contains": "=\s?10$"},
        {"name": "vm.zone_reclaim_mode", "command": "sysctl vm.zone_reclaim_mode","contains": "=\s?0$"},
        {"name": "vm.swappiness", "command": "sysctl vm.swappiness","contains": "=\s1$"},
        {"name": "swap off", "command": "free", "contains": "Swap:\s*0\s*0\s*0"},
        {"name": "transparent_hugepage defrag", "command": "cat /sys/kernel/mm/transparent_hugepage/defrag", "contains": "\[never\]"},
        {"name": "transparent_hugepage disabled", "command": "cat /sys/kernel/mm/transparent_hugepage/enabled", "contains": "\[never\]"}
    ]},
    #SSD checks
   "ssd": {
       "vars": [{"disk": "sda1"}], #"vars": [{"disk": "sda1"}, {"disk": "sda2"}],
       "commands": [
        {"name": "disks 4k blocks", "command": "fdisk -l /dev/{disk}","contains": "I/O size (minimum/optimal): 4096 bytes / 4096 bytes"},
        {"name": "scheduler deadline", "command": "cat /sys/block/{disk}/queue/scheduler","contains": "\[deadline\]"},
        {"name": "rotational 0", "command": "cat /sys/class/block/{disk}/queue/rotational","equals": "0"},
        {"name": "read ahead 8k", "command": "cat /sys/class/block/{disk}/queue/read_ahead_kb","equals": "8"}
    ]},
    #limits checks
    "ulimits": {"commands": [
        {"name": "Max Locked Memory", "command": 'cat /proc/$(pgrep -f cassandra | head -n 1)/limits',"contains": "Max locked memory\s*unlimited\s*unlimited"},
        {"name": "Max file locks", "command": 'cat /proc/$(pgrep -f cassandra | head -n 1)/limits',"contains": "Max file locks\s*(unlimited|100000)\s*(unlimited|100000)"},
        {"name": "Max processes", "command": 'cat /proc/$(pgrep -f cassandra | head -n 1)/limits',"contains": "Max processes\s*(unlimited|32768)\s*(unlimited|32768)"},
        {"name": "Max resident", "command": 'cat /proc/$(pgrep -f cassandra | head -n 1)/limits',"contains": "Max resident set\s*unlimited\s*unlimited"}
    ]}}

def clean(line):
    if line.endswith('\n'):
        return line[:-1]
    return line

results = {}

for host in hosts:
    print 'Checking host '+user+'@'+host+'...'
    for group_name, config  in commands.items():
        vars = [{}] if "vars" not in config else config["vars"]
        results[group_name] = []
        for var in vars:
            for command in config["commands"]:
                command_name = command["command"].format(**var)
                print 'ssh -o "StrictHostKeyChecking no" '+user+'@'+host+' "'+command_name+'"'
                p = subprocess.Popen('ssh -o "StrictHostKeyChecking no" '+user+'@'+host+' "'+command_name+'"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                lines = p.stdout.readlines()
                command_return = clean("".join(lines))
                result = {"command": command_name, "value": command_return, "name": command["name"]}
                if "equals" in command:
                    result.update({"type": "equals", "expected": command["equals"]})
                    result["state"] = "error" if command_return != command["equals"] else "success"
                elif "contains" in command:
                    result.update({"type": "contains", "expected": command["contains"]})
                    regexp = re.compile(r''+command["contains"])
                    result["state"] = "error" if regexp.search(command_return) is None else "success"
                results[group_name].append(result)

    print "--------------------------------------------"
    print "RESULT FOR "+user+"@"+host+":"
    print "   "+"configuration".ljust(40, " ")+"\t "+"command".ljust(50, " ")+" \t\t"+"expectation".ljust(50, " ")+"\t\t "+"current value"
    for k, values in results.items():
        print k+" checks"
        error = 0
        for v in values:
            if v["state"] != "success":
                print "   "+(v["state"]+" "+v["name"]+":").ljust(40, " ")+"\t "+v["command"].ljust(50, " ")+" \t\t"+v["expected"].ljust(50, " ")+"\t\t "+v["value"].replace("\n", ' ')
                error = error +1
        if error == 0:
            print "Ok"