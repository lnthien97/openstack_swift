#!/usr/bin/env python3.9
import os, sys
import json, logging
import time
from datetime import datetime
import configparser
from swift.container.backend import ContainerBroker
from swift.container.server import DATADIR as container_server_data_dir
from swift.common.utils import audit_location_generator

######################
### CONFIG DEFAULT ###
######################
SWIFT_DIR            = "/etc/swift"
SWIFT_CONFIG         = os.path.join(SWIFT_DIR, "swift.conf")

swconfig = configparser.ConfigParser()
swconfig.read(SWIFT_CONFIG)
ring_map = {}

def get_swift_ring():
    # Example ring_map
    # {'object-2.ring.gz': {'name': 'diamond', 'id': 2}, 'object-1.ring.gz': {'name': 'silver', 'id': 1}, 'object.ring.gz': {'name': 'gold', 'id': 0}}
    for section in swconfig:
        if 'storage-policy' in section:
            policy_id   = int(section.split(':')[1])
            policy_name = swconfig[section]['name']
            if policy_id == 0:
                ring_file = 'object.ring.gz'
            else:
                ring_file = 'object-{}.ring.gz'.format(policy_id)

            ring_map[ring_file] = {}
            ring_map[ring_file]['name'] = str(policy_name)
            ring_map[ring_file]['id'] = int(policy_id)

def is_busy(logging, pending_path):
    if os.path.exists(pending_path) and os.path.getsize(pending_path) > 0:
        logging.warning("Pending file is busy at %s and size %s" % (pending_path, os.path.getsize(pending_path)))
        return True
    return False

def main():
    get_swift_ring()

    logging.basicConfig(filename='/var/log/swift/sns-container-swift.log',
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.INFO)

    devices = '/srv/node'
    mount_check=True
    all_locs = audit_location_generator(devices, container_server_data_dir, '.db',
                                            mount_check=mount_check,
                                            logger='')
    result=[]
    for path, device, partition in all_locs:
        data = {}
        pending_path   = "{}.pending".format(path)

        try:
            # if is_busy(logging, pending_path): raise SwiftDatabaseBusy("DB file busy {}.".format(path))
            is_busy(logging, pending_path)
            broker = ContainerBroker(path, timeout=0.1, pending_timeout=0.1, skip_commits=True, stale_reads_ok=True)

            if not broker:
                # raise SwiftBrokerBusy("DB file can not create broker {}.".format(path))
                logging.info("DB file can not create broker {}.".format(path))

            info, is_deleted = broker.get_info_is_deleted()

            if info == None or not info:
                logging.info('{} container is busy or deleted')
                return None

            # If container is ACTIVE
            if is_deleted == False and info['account'] != '.expiring_objects':

                last_modification       = datetime.utcfromtimestamp(os.path.getmtime(path))
                now                     = datetime.utcnow()
                diff                    = (now - last_modification).total_seconds()

                data['object_count']    = info['object_count']
                data['account']         = info['account']
                data['container']       = info['container']
                data['db_state']       = info['db_state']
                data['bytes_used']      = info['bytes_used']
                data['inactive']        = int(diff)
                data['created_at']      = float(info['created_at'])

                for ring in ring_map:
                    if (ring_map[ring]['id'] == info['storage_policy_index']):
                        data['policy-name'] = ring_map[ring]['name']

                # {'account': 'AUTH_a7323d5838624395be9b6f52e7444f4d', 'container': 'container_tier_segments', 'policy-name': 'silver', 'created_at': 1602660134.44054, 'inactive': 141632, 'object-count': 0, 'bytes-used': 0}
                result.append(data)

        except Exception as e:
            logging.exception('Exception: {0}'.format(e))

    print (json.dumps(result))

if __name__ == '__main__':
    main()