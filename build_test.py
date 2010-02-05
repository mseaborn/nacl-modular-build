
import os
import shutil
import subprocess
import tempfile
import unittest

import build
import cmd_env


def read_file(filename):
    fh = open(filename, "r")
    try:
        return fh.read()
    finally:
        fh.close()

def write_file(filename, data):
    fh = open(filename, "w")
    try:
        fh.write(data)
    finally:
        fh.close()


# From http://lackingrhoticity.blogspot.com/2008/11/tempdirtestcase-python-unittest-helper.html
class TempDirTestCase(unittest.TestCase):

    def setUp(self):
        self._on_teardown = []

    def make_temp_dir(self):
        temp_dir = tempfile.mkdtemp(prefix="tmp-%s-" % self.__class__.__name__)
        def tear_down():
            shutil.rmtree(temp_dir)
        self._on_teardown.append(tear_down)
        return temp_dir

    def tearDown(self):
        for func in reversed(self._on_teardown):
            func()


class Test(TempDirTestCase):

    def test_untar(self):
        temp_dir = self.make_temp_dir()
        os.mkdir(os.path.join(temp_dir, "foo-1.0"))
        write_file(os.path.join(temp_dir, "foo-1.0", "README"), "hello")
        tar_file = os.path.join(temp_dir, "foo-1.0.tar.gz")
        subprocess.check_call(["tar", "-cf", tar_file, "foo-1.0"],
                              cwd=temp_dir)

        dest_dir = self.make_temp_dir()
        tree = build.TarballTree(tar_file)
        tree.write_tree(cmd_env.BasicEnv(), dest_dir)
        self.assertEquals(os.listdir(dest_dir), ["README"])

        dest_dir = self.make_temp_dir()
        tree = build.MultiTarballTree([tar_file, tar_file])
        tree.write_tree(cmd_env.BasicEnv(), dest_dir)
        self.assertEquals(os.listdir(dest_dir), ["README"])


if __name__ == "__main__":
    unittest.main()
