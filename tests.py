import os
import unittest
import sys

from collections import OrderedDict
from contextlib import contextmanager
from StringIO import StringIO

from mock import patch

import tunirlib

from tunirlib.tunirdocker import Result, system
from tunirlib import testvm, main

@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err

def create_initrd_kernel(missing=False):
    """
    Creates initrd and kernel test file.
    """
    if not os.path.exists('/tmp/test_tunir/'):
        os.mkdir('/tmp/test_tunir/')
    seed_path = '/tmp/test_tunir/seed.img'
    system('touch /tmp/test_tunir/test.qcow2')
    if not missing:
        system('touch /tmp/test_tunir/test-vmlinuz')
        system('touch /tmp/test_tunir/test-initramfs')
    system('touch %s' % seed_path)

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


class TunirTests(unittest.TestCase):
    """
    Tests tunir's codebase
    """

    def test_config(self):
        data = tunirlib.read_job_configuration(jobname="fedora")
        self.assertEqual(2048, data["ram"], "Missing ram information")


class ExecuteTests(unittest.TestCase):
    """
    Tests the execute function.
    """
    @patch('tunirlib.run')
    def test_execute(self, t_run):
        config = {"host_string": "127.0.0.1",
                  "user": "fedora"}
        r1 = Result("result1")
        r1.return_code = 0
        t_run.return_value=r1
        res, negative = tunirlib.execute(config, 'ls')
        self.assertEqual(res, "result1")
        self.assertEqual(negative, "no")

    @patch('tunirlib.run')
    def test_execute_nagative(self, t_run):
        config = {"host_string": "127.0.0.1",
                  "user": "fedora"}
        r1 = Result("result1")
        r1.return_code = 127
        t_run.return_value=r1
        res, negative = tunirlib.execute(config, '@@ ls')
        self.assertEqual(res, "result1")
        self.assertEqual(negative, "yes")

    @patch('tunirlib.run')
    def test_execute_nongating(self, t_run):
        config = {"host_string": "127.0.0.1",
                  "user": "fedora"}
        r1 = Result("result1")
        r1.return_code = 127
        t_run.return_value=r1
        res, negative = tunirlib.execute(config, '## ls')
        self.assertEqual(res, "result1")
        self.assertEqual(negative, "dontcare")

class UpdateResultTest(unittest.TestCase):
    """
    Tests the update_result function.
    """
    def setUp(self):
        tunirlib.STR = OrderedDict()

    def test_updateresult(self):

        r1 = Result("result1")
        r1.return_code = 0
        r2 = Result("result2")
        r2.return_code = 127
        r3 = Result("result3")
        r3.return_code = 1
        values = [(r1, 'no', 'ls'), (r2, 'yes', '@@ sudo reboot'), (r3, 'dontcare', '## ping foo')]
        for res, negative, command in values:
            tunirlib.update_result(res, command, negative)

        res = [True, True, False]
        for out, result in zip(tunirlib.STR.iteritems(), res):
            self.assertEqual(out[1]['status'], result)


class TestVmTest(unittest.TestCase):
    """
    Tests the testvm module.
    """
    def test_directory_handling(self):
        """
        Tests metadata dir creation details.
        """
        path = '/tmp/test_tunir'
        testvm.clean_dirs(path)
        self.assertFalse(os.path.exists(path))
        testvm.create_dirs(path)
        self.assertTrue(os.path.exists(path))
        testvm.clean_dirs()

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
        create_initrd_kernel()
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

    @patch('subprocess.call')
    def test_download_initrd_kernel(self, s_call):
        """
        Tests the initrd and kernel extraction.
        """
        create_initrd_kernel()
        result= testvm.download_initrd_and_kernel('/tmp/test_tunir/test.qcow2', '/tmp/test_tunir')
        self.assertEqual(result['kernel'], '/tmp/test_tunir/test-vmlinuz')
        self.assertEqual(result['initrd'], '/tmp/test_tunir/test-initramfs')

    @patch('subprocess.call')
    def test_download_initrd_kernel_exception(self, s_call):
        """
        Tests the initrd and kernel extraction.
        """
        testvm.clean_dirs('/tmp/test_tunir')
        create_initrd_kernel(missing=True)
        with captured_output() as (out, err):
            result= testvm.download_initrd_and_kernel('/tmp/test_tunir/test.qcow2', '/tmp/test_tunir')
        self.assertIn("Unable to find kernel or initrd, did they download?", out.getvalue())

    @patch('subprocess.Popen')
    def test_boot_image(self, s_popen):
        res = StupidProcess()
        s_popen.return_value = res

        path = '/tmp/test_tunir'
        seed_path = '/tmp/test_tunir/seed.img'
        testvm.clean_dirs(path)
        testvm.create_dirs(os.path.join(path, 'meta'))
        with captured_output() as (out, err):
            testvm.boot_image('/tmp/test_tunir/test.qcow2', seed_path)
        self.assertIn("PID: 42", out.getvalue())


class TestVmFullRunTest(unittest.TestCase):
    """
    Tests the whole process of booting up an image.
    """

    def setUp(self):
        create_initrd_kernel()
        meta_path = '/tmp/test_tunir/meta'
        if not os.path.exists(meta_path):
            os.mkdir(meta_path)

    @patch('tunirlib.testvm.clean_dirs')
    @patch('subprocess.call')
    @patch('subprocess.Popen')
    def test_build_run(self, s_popen, s_call, s_cleandirs):
        """
        Tests te build_and_run function.
        """
        res = StupidProcess()
        s_popen.return_value = res
        path = '/tmp/test_tunir'
        s_call.return_value = 0
        seed_path = '/tmp/test_tunir/seed.img'
        with captured_output() as (out, err):
            testvm.build_and_run(image_url='/tmp/test_tunir/test.qcow2', image_dir=path)
        self.assertTrue(s_popen.called)
        self.assertTrue(s_call.called)
        self.assertTrue(s_cleandirs.called)

    def tearDown(self):
        system('rm -rf /tmp/test_tunir')


class TestMain(unittest.TestCase):

    def setUp(self):
        create_initrd_kernel()

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

        main(args)
        self.assertTrue(p_kill.called)
        self.assertTrue(p_exit.called)

    def tearDown(self):
        system('rm -rf /tmp/test_tunir')

if __name__ == '__main__':
    unittest.main()

