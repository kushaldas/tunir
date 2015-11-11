import unittest
import mock
import tunirlib


class TunirTests(unittest.TestCase):
    """
    Tests tunir's codebase
    """

    def test_config(self):
        data = tunirlib.read_job_configuration(jobname="fedora")
        self.assertEqual(2048, data["ram"], "Missing ram information")



if __name__ == '__main__':
    unittest.main()

