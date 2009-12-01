
import os
import sys

import action_tree
import cmd_env


tar_dir = "/home/mseaborn/devel/nacl-trunk/src/third_party"
patch_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client/tools/patches"


class Module(object):

    def __init__(self):
        self._env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
        self._prefix = os.path.join(os.getcwd(), "prefix")

    @action_tree.action_node
    def all(self):
        yield self.unpack
        yield self.configure
        yield self.make

    def unpack(self, log):
        self._env.cmd(["mkdir", "-p", "source"])
        self._env.cmd(["tar", "-C", "source", "-xf",
                       os.path.join(tar_dir, "binutils/binutils-2.20.tar.bz2")])
        self._env.cmd(["patch", "-d", "source/binutils-2.20",
                       "-p1",
                       "-i", os.path.join(patch_dir, "binutils-2.20.patch")])

    def configure(self, log):
        self._env.cmd(["mkdir", "-p", "build/binutils"])
        self._env.cmd(["sh", "-c",
                       "cd build/binutils && "
                       "../../source/binutils-2.20/configure "
                       'CFLAGS="-DNACL_ALIGN_BYTES=32 -DNACL_ALIGN_POW2=5" '
                       "--prefix=%s "
                       "--target=nacl"
                       % self._prefix])

    def make(self, log):
        self._env.cmd(["sh", "-c", "cd build/binutils && make"])
        self._env.cmd(["sh", "-c", "cd build/binutils && make install"])


if __name__ == "__main__":
    action_tree.action_main(Module().all, sys.argv[1:])
