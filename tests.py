import os
import unittest
import sys
import tempfile
from collections import OrderedDict
from contextlib import contextmanager
from StringIO import StringIO
from mock import patch, Mock

import tunirlib
from tunirlib.tunirutils import Result, system
from tunirlib import main
from tunirlib import tunirutils, tunirmultihost

@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err

class StupidProcess(object):
    """
    For testing vm creation.
    """
    def __init__(self):
        self.pid = 42 # Answer to all problems.

class StupidArgs(object):
    """
    For testing vm creation.
    """
    def __init__(self):
        self.job = 'testvm'
        self.config_dir = './'
        self.atomic = None
        self.image_dir = None
        self.multi = None
        self.debug = False


class TunirTests(unittest.TestCase):
    """
    Tests tunir's codebase
    """

    def test_single_config(self):
        data = tunirlib.read_job_configuration(jobname="fedora", config_dir='./testvalues/')
        self.assertEqual(2048, data["ram"], "Missing ram information")


    def test_match_vm_numbers(self):
        path = './testvalues/multihost.txt'
        vms = ['vm1', 'vm2']
        self.assertTrue(tunirutils.match_vm_numbers(vms, path))
        vms = ['vm1',]
        with captured_output() as (out, err):
            self.assertFalse(tunirutils.match_vm_numbers(vms, path))
            self.assertIn('vm2', out.getvalue())

    def test_ansible(self):
        vms = {'vm1': {'ip': '192.168.1.100', 'user':'fedora'},\
               'vm2': {'ip': '192.168.1.102', 'user':'fedora'}}
        tdir = tempfile.mkdtemp()
        new_inventory = os.path.join(tdir, 'tunir_ansible')
        old_inventory = os.path.join(tdir, 'inventory')
        with open(old_inventory, 'w') as fobj:
            fobj.write('[web]\nvm1\nvm2')
        tunirutils.create_ansible_inventory(vms, new_inventory)
        self.assertTrue(os.path.exists(new_inventory))
        with open(new_inventory) as fobj:
            data = fobj.read()
        tunirutils.clean_tmp_dirs([tdir,])
        self.assertIn('vm2 ansible_ssh_host=192.168.1.102 ansible_ssh_user=fedora\n', data)
        self.assertIn('vm1 ansible_ssh_host=192.168.1.100 ansible_ssh_user=fedora\n', data)
        self.assertIn('[web]\nvm1\nvm2', data)


    @patch('tunirlib.tunirutils.run')
    @patch('codecs.open')
    @patch('subprocess.call')
    @patch('subprocess.Popen')
    @patch('os.system')
    @patch('time.sleep')
    @patch('sys.exit')
    @patch('os.kill')
    @patch('paramiko.SSHClient')
    @patch('tunirlib.tunirmultihost.boot_qcow2')
    def test_multihost(self,p_br,p_sc,p_kill, p_exit, p_sleep, p_system,p_usystem, p_scall, p_codecs,p_run):
        res = StupidProcess()
        p_br.side_effect = [(res, 'ABCD'),(res,'XYZ')]

        r1 = Result("result1")
        r1.return_code = 0
        r2 = Result("result2")
        r2.return_code = 0
        r3 = Result("result3")
        r3.return_code = 0
        values = [r1, r2, r3]
        p_run.side_effect = values

        c1 = Mock()
        c1.communicate.return_value = ('192.168.1.100','')
        c1.return_code = 0
        c2 = Mock()
        c2.communicate.return_value = ('? (192.168.122.100) at ABCD [ether] on virbr0\n? (192.168.122.116) at 00:16:3e:33:ba:a2 [ether] on virbr0','')
        c2.return_code = 0
        c3 = Mock()
        c3.communicate.return_value = ('h','h')
        c3.return_code = 0
        c4 = Mock()
        c4.communicate.return_value = ('? (192.168.122.102) at XYZ [ether] on virbr0\n? (192.168.122.116) at 00:16:3e:33:ba:a2 [ether] on virbr0','')
        c4.return_code = 0
        p_usystem.side_effect = [c1,c2,c3,c4]


        with captured_output() as (out, err):
            tunirmultihost.start_multihost('multihost', './testvalues/multihost.txt', debug=False, config_dir='./testvalues/')

            #self.assertIn("Passed:1", out.getvalue())
            #self.assertIn("Job status: True", out.getvalue())
        for calls,vals in zip(p_run.mock_calls,(('192.168.122.100', 22, 'fedora', None, 'sudo su -c"echo Hello > /abcd.txt"'),('192.168.122.102', 22, 'fedora', None, 'ls /'),('192.168.122.100', 22, 'fedora', None, 'cat /etc/os-release'))):
            self.assertEqual(calls[1],vals)


class ExecuteTests(unittest.TestCase):
    """
    Tests the execute function.
    """

    @patch('tunirlib.tunirutils.run')
    def test_execute(self, t_run):
        config = {"host_string": "127.0.0.1",
                  "user": "fedora"}
        r1 = Result("result1")
        r1.return_code = 0
        t_run.return_value=r1
        res, negative = tunirutils.execute(config, 'ls')
        self.assertEqual(res, "result1")
        self.assertEqual(negative, "no")

    @patch('tunirlib.tunirutils.run')
    def test_execute_nagative(self, t_run):
        config = {"host_string": "127.0.0.1",
                  "user": "fedora"}
        r1 = Result("result1")
        r1.return_code = 127
        t_run.return_value=r1
        res, negative = tunirutils.execute(config, '@@ ls')
        self.assertEqual(res, "result1")
        self.assertEqual(negative, "yes")

    @patch('tunirlib.tunirutils.run')
    def test_execute_nongating(self, t_run):
        config = {"host_string": "127.0.0.1",
                  "user": "fedora"}
        r1 = Result("result1")
        r1.return_code = 127
        t_run.return_value=r1
        res, negative = tunirutils.execute(config, '## ls')
        self.assertEqual(res, "result1")
        self.assertEqual(negative, "dontcare")

class UpdateResultTest(unittest.TestCase):
    """
    Tests the update_result function.
    """
    def setUp(self):
        tunirutils.STR = OrderedDict()

    def test_updateresult(self):

        r1 = Result("result1")
        r1.return_code = 0
        r2 = Result("result2")
        r2.return_code = 127
        r3 = Result("result3")
        r3.return_code = 1
        values = [(r1, 'no', 'ls'), (r2, 'yes', '@@ sudo reboot'), (r3, 'dontcare', '## ping foo')]
        for res, negative, command in values:
            tunirutils.update_result(res, command, negative)

        res = [True, True, False]
        for out, result in zip(tunirlib.STR.iteritems(), res):
            self.assertEqual(out[1]['status'], result)


if __name__ == '__main__':
    unittest.main()

