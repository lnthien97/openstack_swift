#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
import subprocess
import re
import time
import json
import requests
import sys
import time
import os, re, netifaces
import configparser
from swift.common.ring import RingData, RingBuilder

######################
### CONFIG DEFAULT ###
######################
SRV_ADDRESSES        = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface) and re.match(r'^(172|10|192)\.', netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'])]
SRV_REPLICATION_ADDR = None
SWIFT_DIR            = "/etc/swift"
SWIFT_CONFIG         = os.path.join(SWIFT_DIR, "swift.conf")
SWIFT_OBJECT_RINGS   = [f for f in os.listdir(SWIFT_DIR) if re.match(r'object(|\-[0-9])\.ring\.gz', f)]
SWIFT_RECON_DISK     = 'http://%s:6200/recon/diskusage'

swconfig = configparser.ConfigParser()
swconfig.read(SWIFT_CONFIG)
######################

# Get device list of the ring in the local host
def get_ringdevicelist(ringfile):
    global SRV_REPLICATION_ADDR
    global SRV_ADDRESSES
    device_list=[]
    ring = RingData.load(ringfile)
    for entry in ring.devs:
        if entry is not None and entry['replication_ip'] in SRV_ADDRESSES:
            SRV_REPLICATION_ADDR = entry['replication_ip']
            device_list.append(entry['device'])
    return device_list

def get_ring_disk_usage():
    r = requests.get(url=SWIFT_RECON_DISK % SRV_REPLICATION_ADDR, timeout=0.01)
    result = []
    for entry in r.json():
        ## ACCOUNT RING
        if entry['device'] in account_devices:
            status = "YES" if entry['mounted'] == True else "NO"

            for i in inode_list:
                if i.__contains__(entry['device']):
                    i_dev      = i.get(entry['device'])
                    i_dev_used = int(i_dev.get('iused'))
                    i_dev_free = int(i_dev.get('ifree'))
                    temp_dict  = {  'policy_id':0,
                                    'policy_name':'-',
                                    'ring':'account',
                                    'device':entry['device'],
                                    'used': entry['used'],
                                    'avail': entry['avail'],
                                    'iused': i_dev_used,
                                    'ifree': i_dev_free,
                                    'mounted': status,
                                    'total_size': (entry['used'] + entry['avail'])
                                }
                    result.append(temp_dict)

        ## CONTAINER RING
        if entry['device'] in container_devices:
            status = "YES" if entry['mounted'] == True else "NO"

            for i in inode_list:
                if i.__contains__(entry['device']):
                    i_dev      = i.get(entry['device'])
                    i_dev_used = int(i_dev.get('iused'))
                    i_dev_free = int(i_dev.get('ifree'))
                    temp_dict  = {  'policy_id':0,
                                    'policy_name':'-',
                                    'ring':'container',
                                    'device':entry['device'],
                                    'used': entry['used'],
                                    'avail': entry['avail'],
                                    'iused': i_dev_used,
                                    'ifree': i_dev_free,
                                    'mounted': status,
                                    'total_size': (entry['used'] + entry['avail'])
                                }
                    result.append(temp_dict)


        for tier in object_devices:
            if entry['device'] in object_devices[tier]:
                status = "YES" if entry['mounted'] == True else "NO"

                for i in inode_list:
                    if i.__contains__(entry['device']):
                        i_dev      = i.get(entry['device'])
                        i_dev_used = int(i_dev.get('iused'))
                        i_dev_free = int(i_dev.get('ifree'))
                        temp_dict  = {  'policy_id': TIERS[tier]['id'],
                                        'policy_name': tier,
                                        'ring':'object',
                                        'device':entry['device'],
                                        'used': entry['used'],
                                        'avail': entry['avail'],
                                        'iused': i_dev_used,
                                        'ifree': i_dev_free,
                                        'mounted': status,
                                        'total_size': (entry['used'] + entry['avail'])
                                    }
                        result.append(temp_dict)

    print(json.dumps(result))


if __name__ == '__main__':

    ## Get tier active on this node
    TIERS = {}
    for section in swconfig:
        if "storage-policy" in section:
            policy_id   = int(section.split(':')[1])
            policy_name = swconfig[section]['name']
            if policy_id == 0:
                ring_file = 'object.ring.gz'
            else:
                ring_file = 'object-{}.ring.gz'.format(policy_id)

            if ring_file in SWIFT_OBJECT_RINGS:
                TIERS[policy_name] = {  "id": policy_id,
                                        "name": policy_name,
                                        "ring_file": os.path.join(SWIFT_DIR, ring_file)
                                    }
    # Lấy danh sách device cho từng rings
    account_devices   = get_ringdevicelist(os.path.join(SWIFT_DIR, 'account.ring.gz'))
    container_devices = get_ringdevicelist(os.path.join(SWIFT_DIR, 'container.ring.gz'))
    object_devices    = {}
    for tier in TIERS:
        object_devices[tier] = get_ringdevicelist(TIERS[tier]['ring_file'])

    # Get iused, ifree
    inode_list = []
    inode_info = subprocess.Popen(["df", "-i", "--type=xfs", "--type=zfs"],stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)

    for string in str(inode_info.communicate()[0].decode('utf-8')).split('\n'):
        device_inode = re.search(r'\d+\s+(\d+)\s+(\d+)\s+\d%+\s+\/\w+\/\w+\/(.*)',string,re.M|re.I)
        if device_inode:
            inode_list.append({device_inode.group(3):{'iused':device_inode.group(1),'ifree':device_inode.group(2)}})

    get_ring_disk_usage()
