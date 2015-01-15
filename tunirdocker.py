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

class Result(object):
    """
    To hold results from docker command executions.
    """
    def __init__(self, msg, ret_code=0):
        self.msg = unicode(msg)
        self.return_code = ret_code

    def __repr__(self):
        return self.msg

    def __str__(self):
        return self.msg


class Docker(object):
    """
    Returns a Docker object.
    """
    def __init__(self, image, wait=600):
        self.image = image
        self.cid = None
        # Now we will start a new container with the given container name
        out, code = system('docker run -d %s sleep %d' % (image, wait))
        if not code:
            self.cid = out.strip('\n')
        else:
            print "Some error in creating the container."

    def run(self, command):
        """
        Executes the given command in the currect container.
        :param command: Command to execute
        :return: Tuple of the output and error message.
        """
        return system('docker exec %s %s' % (self.cid, command))

    def rm(self):
        "Removes the current container."
        system('docker rm --force %s' % self.cid)

    def execute(self, command):
        """
        Executes a command and returns a result
        :param command: The command to execute
        :return: Returns a result object similar to Fabric API.
        """
        res = Result('')
        out, err = self.run(command)
        if err:
            res.msg = u'%s %s' % (out, err)
            res.return_code = -1
        else:
            res.msg = unicode(out)
        return res




if __name__ == '__main__':
    d = Docker('fedora', 60)
    print d.run('ls -l /foobar12')
    d.rm()