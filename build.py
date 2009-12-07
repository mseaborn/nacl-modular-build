
import os
import sys

import action_tree
import cmd_env


nacl_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client"
tar_dir = "/home/mseaborn/devel/nacl-trunk/src/third_party"
patch_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client/tools/patches"


class ModuleBase(object):

    def __init__(self, prefix):
        self._env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
        self._prefix = prefix

    def all(self):
        return action_tree.make_node(
            [self.unpack, self.configure, self.make], self.name)


class Module1(ModuleBase):

    name = "binutils"

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


class Module2(ModuleBase):

    name = "gcc"

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


class Module3(ModuleBase):

    name = "newlib"

    def unpack(self, log):
        self._env.cmd(["mkdir", "-p", "source"])
        self._env.cmd(["tar", "-C", "source", "-xf",
                       os.path.join(tar_dir, "newlib/newlib-1.17.0.tar.gz")])
        self._env.cmd(["patch", "-d", "source/newlib-1.17.0",
                       "-p1",
                       "-i", os.path.join(patch_dir, "newlib-1.17.0.patch")])

    def configure(self, log):
        # This is like exporting the kernel headers to glibc.
        # This should be done differently.
        self._env.cmd(
            [os.path.join(nacl_dir, "src/trusted/service_runtime/export_header.py"),
             os.path.join(nacl_dir, "src/trusted/service_runtime/include"),
             "source/newlib-1.17.0/newlib/libc/sys/nacl"])

        self._env.cmd(["mkdir", "-p", "build/newlib"])
        # CFLAGS has to be passed via environment because the
        # configure script can't cope with spaces otherwise.
        self._env.cmd(["sh", "-c",
                       "cd build/newlib && "
                       'CFLAGS="-m32 -march=i486 -msse2 -mfpmath=sse" '
                       "../../source/newlib-1.17.0/configure "
                       "--enable-newlib-io-long-long "
                       "--enable-newlib-io-c99-formats "
                       "--prefix=%s "
                       "--target=nacl"
                       % self._prefix])

    def make(self, log):
        self._env.cmd(["sh", "-c", "cd build/newlib && make"])
        self._env.cmd(["sh", "-c", "cd build/newlib && make install"])


mods = [
    Module1,
    Module2,
    Module3,
    ]

def all_mods():
    nodes = []
    env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
    prefix_base = os.path.join(os.getcwd(), "prefix")
    for mod in mods:
        # prefix = os.path.join(prefix_base, mod.name)
        # os.environ["PATH"] = "%s:%s" % (prefix, os.environ["PATH"])
        prefix = os.path.join(os.getcwd(), "sharedprefix")
        os.environ["PATH"] = "%s:%s" % (os.path.join(prefix, "bin"),
                                        os.environ["PATH"])
        nodes.append(mod(prefix).all())
    return action_tree.make_node(nodes, name="all")


if __name__ == "__main__":
    action_tree.action_main(all_mods(), sys.argv[1:])
