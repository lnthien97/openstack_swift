#!/usr/bin/env python3.9
import sys
import os
import re
import errno
import json
from argparse import ArgumentParser
from collections import defaultdict

from swift.common.storage_policy import split_policy_string
from swift.obj.diskfile import get_data_dir
from swift.common.ring import Ring
import netifaces

parser = ArgumentParser()
parser.add_argument('-v', '--verbose', help='line oriented output',
                    default=False, action='store_true')
parser.add_argument('ring', help='specify the ring, infers datadir')
parser.add_argument('devices', help='root of devices tree for node',
                    nargs='?', default='/srv/node')
parser.add_argument('--limit', help='max number of handoff parts to output',
                    default=None, type=int)
parser.add_argument('--workers-per-device', type=int, default=1,
                    help='Number of output lines per device, '
                    'parts are split up evenly')
parser.add_argument('--metric-telegraf', help="Export metric monitor for telegraf",
                    default=False)


def split(seq, n):
    """
    split seq into n pieices
    """
    seq = list(seq)
    for i in range(n):
        yield seq[i::n]


def get_ring_and_datadir(path):
    """
    :param path: path to ring

    :returns: a tuple, (ring, datadir)
    """
    ring_name = os.path.basename(path).split('.')[0]
    base, policy = split_policy_string(ring_name)
    if base == 'object':
        datadir = get_data_dir(policy)
    else:
        datadir = base + 's'
    return Ring(path), datadir

def get_server_type(path):
    ring_name = os.path.basename(path).split('.')[0]
    return "{}-server".format(ring_name)


def main(ring_path):
    args = parser.parse_args()
    device_root = args.devices

    ring, datadir = get_ring_and_datadir(ring_path)
    server_type = get_server_type(ring_path)
    dev2parts = defaultdict(set)
    for replica, part2dev in enumerate(ring._replica2part2dev_id):
        for part, device_id in enumerate(part2dev):
            dev2parts[ring.devs[device_id]['device']].add(part)

    #print dev2parts
    handoffs = defaultdict(set)
    device_dirs = os.listdir(device_root)
    for device_dir in device_dirs:
        parts_dir = os.path.join(device_root, device_dir, datadir)
        try:
            parts = os.listdir(parts_dir)
        except OSError as e:
            if e.errno == errno.ENOENT:
                continue
            else:
                raise
        for part in parts:
            if not part.isdigit():
                continue
            part = int(part)
            if part in dev2parts[device_dir]:
                continue
            handoffs[device_dir].add(part)
    handoff_parts = 0
    handoff_device = 0
    for device, parts in handoffs.items():
        handoff_parts += len(parts)
        handoff_device += 1
        if args.metric_telegraf == False:
            if args.limit is not None:
                parts = list(parts)[:args.limit]
            if args.verbose:
                # maybe verbose is more like --debug?
                print (os.path.join(device_root, device))
                for part in parts:
                    print ('   ', part)
                continue
            for sub_parts in split(parts, args.workers_per_device):
                print ('-d %s -p %s' % (device, ','.join(str(p) for p in sub_parts)))
    if args.metric_telegraf:
        output = {}
        output['name'] = "swift-handoff-devices"
        output['role'] = server_type
        output['total-devices'] = handoff_device
        output['total-parts'] = handoff_parts
        return output


if __name__ == "__main__":
    ######################
    ### CONFIG DEFAULT ###
    ######################
    #SRV_ADDRESSES        = [netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'] for iface in netifaces.interfaces() if netifaces.AF_INET in netifaces.ifaddresses(iface) and re.match(r'^(172|10|192)\.', netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr'])]
    SWIFT_DIR            = "/etc/swift"
    SWIFT_CONFIG         = os.path.join(SWIFT_DIR, "swift.conf")
    SWIFT_OBJECT_RINGS   = [f for f in os.listdir(SWIFT_DIR) if re.match(r'(account|container|object)(|\-[0-9])\.ring\.gz$', f)]
    ######################
    output=[]
    for ring in SWIFT_OBJECT_RINGS:
        output.append(main(os.path.join(SWIFT_DIR, ring)))
    print (json.dumps(output))
