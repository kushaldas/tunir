import unittest

from mock import patch
import sys
import tunirlib
from contextlib import contextmanager
from StringIO import StringIO
from tunirlib.tunirdocker import Result


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


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


if __name__ == '__main__':
    unittest.main()

