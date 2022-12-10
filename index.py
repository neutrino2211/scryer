import warnings
warnings.simplefilter("ignore", category=DeprecationWarning)
import scapy.config
from scapy.all import ICMP, UDP, TCP, IP, sniff
import time

from banner import print_banner

from record import IDSRecord
from report import IDSReport

from flood_detection import FloodDetection, SYNFloodDetection, ACKFloodDetection, FINFloodDetection, HTTPFloodDetection
from malicious_communication import MaliciousComms
from restricted_resources import RestrictedResources
from data_transfer import DataTransfer

import yaml
from yaml.loader import SafeLoader

import atexit

registered_handlers = []

def malicious_comms(pkt):
    # check if the packet has a TCP layer
    if TCP in pkt:
        # get the TCP header
        tcp_hdr = pkt[TCP]

        # check if the TCP header is valid
        if not tcp_hdr.flags & 2:
            # the TCP header is invalid, print a message
            report.add_record(IDSRecord(pkt, "Suspicious Packet", pkt[IP].src, pkt[IP].dst, "A packet with an invalid TCP header detected. Potential stealth scan attempt by {}".format(pkt[IP].src)))
        
def sniffer(packet):
    malicious_comms(packet)
    
    for handler in registered_handlers:
        handler(packet)


# TODO: Persistent threats
def parse_iplist(name: str) -> dict[str, int]:
    r = {}
    f = open(name, 'r')

    for line in f.readlines():
        if line.startswith("#"):
            continue

        (ip, threat_level) = line[:-1].split("\t")
        r[ip] = threat_level

    return r

def get_interfaces() -> list[(str, str)]:
    r = []
    for network, netmask, _, interface, address, _ in scapy.config.conf.route.routes:
        if network == 0 or interface == 'lo' or address == '127.0.0.1' or address == '0.0.0.0':
            continue

        if netmask <= 0 or netmask == 0xFFFFFFFF:
            continue

        r.append((interface, address))

    return r


def exit_handler():
    print('Exiting...')
    report_txt = report.generate()

    with open("ids-report" + str(int(time.time())), 'w') as f:
        f.write(report_txt)
        

atexit.register(exit_handler)

ip_list = parse_iplist("ipsum.txt")
interfaces = get_interfaces()
report = IDSReport()
mal_comms = MaliciousComms(report, ip_list)
registered_handlers.append(mal_comms.handler)

# Open the file and load the file
with open('conf.yml') as f:
    data = yaml.load(f, Loader=SafeLoader)

    conf = data['scryer']

    if 'traffic' in conf:
        if 'UDP' in conf['traffic']:
            udp = FloodDetection(report, UDP, conf['traffic']['UDP'].get('max_count', 0))
            registered_handlers.append(udp.handler)
            udp.start(conf['traffic']['UDP'].get('interval', 1000) / 1000)
        
        if 'TCP' in conf['traffic']:
            tcp = FloodDetection(report, TCP, conf['traffic']['TCP'].get('max_count', 0))
            registered_handlers.append(tcp.handler)
            tcp.start(conf['traffic']['ICMP'].get('interval', 1000) / 1000)
        
        if 'ICMP' in conf['traffic']:
            icmp = FloodDetection(report, ICMP, conf['traffic']['ICMP'].get('max_count', 0))
            registered_handlers.append(icmp.handler)
            icmp.start(conf['traffic']['ICMP'].get('interval', 1000) / 1000)
        
        if 'HTTP' in conf['traffic']:
            http = FloodDetection(report, TCP, conf['traffic']['HTTP'].get('max_count', 0))
            registered_handlers.append(http.handler)
            http.start(conf['traffic']['HTTP'].get('interval', 1000) / 1000)
        
        if 'SYN' in conf['traffic']:
            syn = SYNFloodDetection(report, TCP, conf['traffic']['SYN'].get('max_count', 0))
            registered_handlers.append(syn.handler)
            syn.start(conf['traffic']['SYN'].get('interval', 1000) / 1000)
        
        if 'ACK' in conf['traffic']:
            ack = ACKFloodDetection(report, TCP, conf['traffic']['ACK'].get('max_count', 0))
            registered_handlers.append(ack.handler)
            ack.start(conf['traffic']['ACK'].get('interval', 1000) / 1000)
        
        if 'FIN' in conf['traffic']:
            fin = FINFloodDetection(report, TCP, conf['traffic']['FIN'].get('max_count', 0))
            registered_handlers.append(fin.handler)
            fin.start(conf['traffic']['FIN'].get('interval', 1000) / 1000)

    if 'restricted_resources' in conf:
        restricted_resources = RestrictedResources(
            report,
            conf['restricted_resources']['network'],
            conf['restricted_resources']['internal'],
            conf['restricted_resources'].get("external", ""),
            conf['restricted_resources'].get('internal_allow_list', "")
        )
        registered_handlers.append(restricted_resources.handler)

    if 'data_transfer' in conf:
        size = conf['data_transfer']['limit']


        dt = DataTransfer(report, size)
        registered_handlers.append(dt.handler)
        dt.start(conf['data_transfer']['interval'] / 1000)
    
    print_banner()
    sniff(iface=conf.get('interface', 'wlo1'), prn=sniffer)


