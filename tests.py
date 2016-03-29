import os
import unittest
import sys
import tempfile
from collections import OrderedDict
from contextlib import contextmanager
from StringIO import StringIO
from mock import patch

import tunirlib
from tunirlib.tunirutils import Result, system
from tunirlib import main
from tunirlib import tunirutils

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


class TestVmTest(unittest.TestCase):
    """
    Tests the testvm module.
    """

    @patch('subprocess.call')
    def test_metadata_userdata(self, s_call):
        """
        Tests metadata and userdata creation
        """
        path = '/tmp/test_tunir'
        seed_path = '/tmp/test_tunir/seed.img'
        meta_path = '/tmp/test_tunir/meta/'
        metadata_filepath = '/tmp/test_tunir/meta/meta-data'
        userdata_filepath = '/tmp/test_tunir/meta/user-data'
        testvm.clean_dirs(path)
        testvm.create_dirs(os.path.join(path, 'meta'))
        base_path = path
        testvm.create_user_data(base_path, "passw0rd")
        testvm.create_meta_data(base_path, "test_tunir")
        self.assertTrue(os.path.exists(metadata_filepath))
        self.assertTrue(os.path.exists(userdata_filepath))
        testvm.create_seed_img(meta_path, path)
        self.assertTrue(os.path.exists(seed_path))
        s_call.assert_called_once_with(['virt-make-fs',
                                  '--type=msdos',
                                  '--label=cidata',
                                  meta_path,
                                  path + '/seed.img'])
        testvm.clean_dirs(path)



    @patch('subprocess.Popen')
    def test_boot_image(self, s_popen):
        res = StupidProcess()
        s_popen.return_value = res

        path = '/tmp/test_tunir'
        seed_path = '/tmp/test_tunir/seed.img'
        with captured_output() as (out, err):
            tunirutils.boot_image('/tmp/test_tunir/test.qcow2', seed_path)
        self.assertIn("PID: 42", out.getvalue())



class TestMain(unittest.TestCase):

    def setUp(self):
        meta_path = '/tmp/test_tunir/meta'
        if not os.path.exists(meta_path):
            os.mkdir(meta_path)

    @patch('time.sleep')
    @patch('sys.exit')
    @patch('os.kill')
    @patch('tunirlib.run')
    @patch('tunirlib.build_and_run')
    def test_main(self,p_br, p_run,p_kill, p_exit, p_sleep):
        res = StupidProcess()
        p_br.return_value = res

        r1 = Result("result1")
        r1.return_code = 0
        r2 = Result("result2")
        r2.return_code = 0
        values = [r1, r2]
        p_run.side_effect = values

        # Now let us construct the args
        args = StupidArgs()
        with captured_output() as (out, err):
            main(args)
            self.assertIn("Passed:1", out.getvalue())
            self.assertIn("Job status: True", out.getvalue())
        self.assertTrue(p_kill.called)
        self.assertTrue(p_exit.called)

    def tearDown(self):
        system('rm -rf /tmp/test_tunir')

if __name__ == '__main__':
    unittest.main()

