# -*- coding: utf-8 -*-
"Tunir module to talk to EC2"

# Copyright © 2015  Kushal Das <kushaldas@gmail.com>
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2, or (at your option) any later
# version.  This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.  You
# should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#

import time
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver


class EC2Node(object):
    def __init__(self, ACCESS_ID, SECRET_KEY, IMAGE_ID, SIZE_ID, region="us-west-1",
                 aki=None, keyname='tunir', security_group='ssh', virt_type='paravirtual'):

        print "Starting an AWS EC2 based job."
        self.region = region
        cls = get_driver(Provider.EC2)
        self.driver = cls(ACCESS_ID, SECRET_KEY, region=region)
        sizes = self.driver.list_sizes()
        images = self.driver.list_images()
        self.size = None
        self.image = None
        self.aki = aki
        self.state = 'pending'
        self.virt_type = virt_type
        self.failed = False
        self.node = None
        self.ip = None
        print "AWS job type:", virt_type
        print "AMI {0}, AKI {1} SIZE {2} REGION {3}".format(IMAGE_ID, aki, SIZE_ID, region)
        try:
            self.size = [s for s in sizes if s.id == SIZE_ID][0]
            self.image = [i for i in images if i.id == IMAGE_ID][0]
        except Exception as err:
            print err
            self.failed = True
            return
        try:
            if self.virt_type == 'hvm':
                self.node = self.driver.create_node(name='tunir_test_node',
                                                    image=self.image, size=self.size, ex_keyname=keyname,
                                                    ex_security_groups=[security_group, ], )
            else:
                self.node = self.driver.create_node(name='tunir_test_node',
                                                    image=self.image, size=self.size, ex_keyname=keyname,
                                                    ex_security_groups=[security_group, ], kernel_id=aki )
            # Now we will try for 3 minutes to get an ip.
            for i in range(5):
                time.sleep(30)
                nodes = self.driver.list_nodes(ex_node_ids=[self.node.id, ])
                n = nodes[0]
                if n.public_ips:
                    self.ip = n.public_ips[0]
                    self.node = n
                    print "Got the IP", self.ip
                    break
            # Now we will wait change the state to running.
            # 0: running
            # 3: pending
            for i in range(5):
                time.sleep(30)
                print "Trying to find the state."
                nodes = self.driver.list_nodes(ex_node_ids=[self.node.id, ])
                n = nodes[0]
                if n.state == 0:
                    self.node = n
                    self.state = 'running'
                    print "The node is in running state."
                    time.sleep(30)
                    break
                else:
                    print "Nope, not yet."

        except Exception as err:
            print err
        if not self.ip:
            self.failed = True

    def destroy(self):
        print "Now trying to destroy the EC2 node."
        if self.node.destroy():
            print "Successfully destroyed."
        else:
            print "There was in issue in destorying the node."


def aws_and_run(config):
    """Takes a config object, starts a new EC2 instance, and then returns it.

    :param config: Dictionary

    :returns: EC2Node object
    """
    node = EC2Node(config['access_key'], config['secret_key'],
                   config['image'], config['size_id'], config.get('region', 'us-west-1'),
                   config.get('aki', None), config.get('keyname', 'ssh'), config.get('security_group', 'ssh'),
                   config.get('virt_type', 'paravirtual'))
    if not node.failed:  # Means we have an ip
        config['host_string'] = node.ip
        config['ip'] = node.ip
    return node, config
