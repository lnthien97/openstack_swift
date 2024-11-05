#!/usr/bin/env python3.9
import os, sys
from logging.handlers import SysLogHandler
import logging, time
import json, configparser
from swift.account.backend import AccountBroker
from swift.account.server import DATADIR as account_server_data_dir
#from swift.common import utils
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
    # {0: 'gold', 1: 'silver', 2: 'archive'}
    for section in swconfig:
        if 'storage-policy' in section:
            policy_id   = int(section.split(':')[1])
            policy_name = swconfig[section]['name']
            ring_map[policy_id] = str(policy_name)


class DBBroker(AccountBroker):
    def get_info(self):
        """
        Get global data for the account.
        :returns: dict with keys: account,
                  container_count,
                  object_count, bytes_used
        """
        self._commit_puts_stale_ok()
        with self.get() as conn:
            return dict(conn.execute('''
                SELECT account,
                       container_count, object_count,
                       bytes_used, status, metadata
                FROM account_stat
            ''').fetchone())


def main():
    get_swift_ring()

    logging.basicConfig(filename='/var/log/swift/sns-account-swift.log',
                                filemode='a',
                                format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S',
                                level=logging.INFO)
    debug       =  os.environ.get('debug', 'false')
    devices     = '/srv/node'
    mount_check = True
    DATADIR     = account_server_data_dir

    ## Example: https://python.hotexamples.com/examples/swift.common.ondisk/-/audit_location_generator/python-audit_location_generator-function-examples.html
    all_locs = audit_location_generator(devices, DATADIR, '.db',
                                                mount_check=mount_check,
                                                logger='')

    data=[]
    for path, device, partition in all_locs:
        try:
            conn = DBBroker(path)
            # row {'status': '', 'object_count': 18, 'account': 'AUTH_7ebf4c2c05ee42da857ca4ff55107270', 'bytes_used': 121662601, 'container_count': 3, 'metadata': '{"X-Account-Meta-Temp-Url-Key": ["ucwquonp", "1552553872.59354"], "X-Account-Sysmeta-Project-Domain-Id": ["default", "1539657245.96878"]}'}
            row = conn.get_info()

            """ ring_policy {0: {'bytes_used': 0, 'container_count': 0, 'object_count': 0}, 1: {'bytes_used': 1447, 'container_count': 1, 'object_count': 1}} """
            ring_policy = conn.get_policy_stats(do_migrations=False)
            metadata = json.loads('['+row['metadata']+']')
            row['quota-bytes'] = 0
            row['cls-service'] = 'vstorage'

            for m in metadata:
                if 'X-Account-Meta-Quota-Bytes' in m and m['X-Account-Meta-Quota-Bytes'][0].isdigit():
                    row['quota-bytes'] = m['X-Account-Meta-Quota-Bytes'][0]

                if 'X-Account-Meta-Vngcloud-Cls-Service' in m:
                    row['cls-service'] = str(m['X-Account-Meta-Vngcloud-Cls-Service'][0])
            del row['metadata']

            # Scan each policy
            if row['status'] == '':
                for ring in ring_policy:
                    report_detail_account                    = {}
                    report_detail_account['cls-service']     = row['cls-service']
                    report_detail_account['container_count'] = ring_policy[ring]["container_count"]
                    report_detail_account['object_count']    = ring_policy[ring]["object_count"]
                    report_detail_account['bytes_used']      = ring_policy[ring]["bytes_used"]
                    report_detail_account['policy-name']     = ring_map[ring]
                    report_detail_account['account']         = row['account']
                    report_detail_account['status']          = 'ACTIVE'
                    # {'status': 'ACTIVE', 'object_count': 4637, 'container_count': 29, 'policy-name': 'gold', 'account': 'AUTH_eb01c2542fcf49b689511d9ccbbf5ca7', 'bytes_used': 21066485102}
                    data.append(report_detail_account)

            # Policy ALL
            try:
                if (float(row['quota-bytes']) > 0 and row['bytes_used'] > 0):
                    try:
                        row['percent_used'] = round(float(row['bytes_used']) * 100 / float(row['quota-bytes']),1)
                    except ZeroDivisionError as e:
                        row['percent_used'] = 0
                        logging.exception('ZeroDivisionError: at path {0} {1}'.format(path, e))
                else:
                    row['percent_used'] = 0

                row['percent_used'] = float(row['percent_used'])
                row['quota-bytes'] = int(row['quota-bytes'])
                row['policy-name'] = 'ALL'

                if row['status'] == '':
                    row['status'] = "ACTIVE"

                # """
                # [{'status': 'ACTIVE', 'object_count': 4637, 'container_count': 29, 'policy-name': 'gold', 'account': 'AUTH_eb01c2542fcf49b689511d9ccbbf5ca7', 'bytes_used': 21066485102}, {'status': 'ACTIVE', 'object_count': 37, 'container_count': 3, 'policy-name': 'silver', 'account': 'AUTH_eb01c2542fcf49b689511d9ccbbf5ca7', 'bytes_used': 268445835}, {'status': 'ACTIVE', 'object_count': 32, 'container_count': 6, 'policy-name': 'archive', 'account': 'AUTH_eb01c2542fcf49b689511d9ccbbf5ca7', 'bytes_used': 641238218}, {'status': 'ACTIVE', 'object_count': 4706, 'account': 'AUTH_eb01c2542fcf49b689511d9ccbbf5ca7', 'quota-bytes': 0, 'bytes_used': 21976169155, 'container_count': 38, 'cls-service': 'vstorage', 'percent_used': 0.0, 'policy-name': 'ALL'}]
                # """

                data.append(row)

            except Exception as e:
                logging.exception('Processing data: {0}'.format(e))

            del conn

        except Exception as e:
            logging.exception('GET_INFO: {0}'.format(e))

        

    print (json.dumps(data))

if __name__ == '__main__':
    main()
