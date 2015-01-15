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




if __name__ == '__main__':
    d = Docker('fedora', 60)
    print d.run('ls -l /foobar12')
    d.rm()