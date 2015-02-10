# -*- coding: utf-8 -*-
"Tunir module to talk to docker"

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

import json
import subprocess


def system(command):
    """
    Executes a given command
    :param command: the command to run
    :return: Tuple of the output and error message.
    """
    ret = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    out, err = ret.communicate()
    return out, err

class Result(str):
    """
    To hold results from docker command executions.
    """
    @property
    def stdout(self):
        return str(self)

class Docker(object):
    """
    Returns a Docker object. The image must have sshd running.
    """
    def __init__(self, image):
        self.image = image
        self.cid = None
        # Now we will start a new container with the given container name
        out, code = system('docker run -d -p 22 %s' % image)
        if not code:
            self.cid = out.strip('\n')
        else:
            print "Some error in creating the container."
            return
        out, code = system('docker inspect %s' % self.cid)
        data = json.loads(out)
        self.port  = data[0]['NetworkSettings']['Ports']['22/tcp'][0]['HostPort']

    def rm(self):
        "Removes the current container."
        system('docker rm --force %s' % self.cid)






if __name__ == '__main__':
    d = Docker('kushaldas/ssh1')
    print d.cid, d.port
    d.rm()