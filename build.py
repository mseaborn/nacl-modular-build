
import os
import sys

import action_tree
import cmd_env


tar_dir = "/home/mseaborn/devel/nacl-trunk/src/third_party"
patch_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client/tools/patches"


class Module1(object):

    def __init__(self):
        self._name = "binutils"
        self._env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
        self._prefix = os.path.join(os.getcwd(), "prefix")

    def all(self):
        return action_tree.make_node(
            [self.unpack, self.configure, self.make], self._name)

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


class Module2(object):

    def __init__(self):
        self._name = "gcc"
        self._env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
        self._prefix = os.path.join(os.getcwd(), "prefix")

    def all(self):
        return action_tree.make_node(
            [self.unpack, self.configure, self.make], self._name)

    def unpack(self, log):
        self._env.cmd(["mkdir", "-p", "source"])
        self._env.cmd(["tar", "-C", "source", "-xf",
                       os.path.join(tar_dir, "gcc/gcc-core-4.2.2.tar.bz2")])
        self._env.cmd(["tar", "-C", "source", "-xf",
                       os.path.join(tar_dir, "gcc/gcc-g++-4.2.2.tar.bz2")])
        self._env.cmd(["patch", "-d", "source/gcc-4.2.2",
                       "-p1",
                       "-i", os.path.join(patch_dir, "gcc-4.2.2.patch")])

    def configure(self, log):
        self._env.cmd(["mkdir", "-p", "build/gcc"])
        # CFLAGS has to be passed via environment because the
        # configure script can't cope with spaces otherwise.
        self._env.cmd(["sh", "-c",
                       "cd build/gcc && "
                       "CC=gcc "
                       'CFLAGS="-Dinhibit_libc -D__gthr_posix_h -DNACL_ALIGN_BYTES=32 -DNACL_ALIGN_POW2=5" '
                       "../../source/gcc-4.2.2/configure "

                       "--without-headers "
                       "--disable-libmudflap "
                       "--disable-decimal-float "
                       "--disable-libssp "
                       "--enable-languages=c "
                       "--disable-threads " # pregcc
                       "--disable-libstdcxx-pch "
                       "--disable-shared "

                       "--prefix=%s "
                       "--target=nacl"
                       % self._prefix])

    def make(self, log):
        # The default make target doesn't work - it gives libiberty
        # configure failures.  Need to do "all-gcc" instead.
        self._env.cmd(["sh", "-c", "cd build/gcc && make all-gcc -j2"])
        self._env.cmd(["sh", "-c", "cd build/gcc && make install-gcc"])


mods = [
    Module1(),
    Module2(),
    ]

def all_mods():
    return action_tree.make_node([mod.all() for mod in mods], name="all")


if __name__ == "__main__":
    action_tree.action_main(all_mods(), sys.argv[1:])
