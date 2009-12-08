
import os
import sys

import action_tree
import cmd_env


nacl_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client"
tar_dir = "/home/mseaborn/devel/nacl-trunk/src/third_party"
patch_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client/tools/patches"


def get_one(lst):
    assert len(lst) == 1, lst
    return lst[0]


def untar_multiple(env, dest_dir, tar_files):
    assert os.listdir(dest_dir) == []
    for tar_file in tar_files:
        env.cmd(["tar", "-C", dest_dir, "-xf", tar_file])
    tar_name = get_one(os.listdir(dest_dir))
    for leafname in os.listdir(os.path.join(dest_dir, tar_name)):
        os.rename(os.path.join(dest_dir, tar_name, leafname),
                  os.path.join(dest_dir, leafname))
    os.rmdir(os.path.join(dest_dir, tar_name))


def untar(env, dest_dir, tar_file):
    assert os.listdir(dest_dir) == []
    env.cmd(["tar", "-C", dest_dir, "-xf", tar_file])
    tar_name = get_one(os.listdir(dest_dir))
    for leafname in os.listdir(os.path.join(dest_dir, tar_name)):
        os.rename(os.path.join(dest_dir, tar_name, leafname),
                  os.path.join(dest_dir, leafname))
    os.rmdir(os.path.join(dest_dir, tar_name))


class ModuleBase(object):

    def __init__(self, prefix):
        self._env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
        self._source_dir = os.path.join(os.getcwd(), "source", self.name)
        self._build_dir = os.path.join(os.getcwd(), "build", self.name)
        self._prefix = prefix
        self._build_env = cmd_env.PrefixCmdEnv(
            cmd_env.in_dir(self._build_dir), self._env)
        self._args = {"prefix": self._prefix,
                      "source_dir": self._source_dir}

    def all(self):
        return action_tree.make_node(
            [self.unpack, self.configure, self.make], self.name)

    def unpack(self, log):
        if not os.path.exists(self._source_dir):
            temp_dir = "%s.temp" % self._source_dir
            os.mkdir(temp_dir)
            self.get(self._env, temp_dir)
            os.rename(temp_dir, self._source_dir)


class Module1(ModuleBase):

    name = "binutils"

    def get(self, env, dest_dir):
        untar(env, dest_dir,
              os.path.join(tar_dir, "binutils/binutils-2.20.tar.bz2"))
        self._env.cmd(["patch", "-d", dest_dir, "-p1",
                       "-i", os.path.join(patch_dir, "binutils-2.20.patch")])

    def configure(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        self._build_env.cmd(["sh", "-c",
                       "%(source_dir)s/configure "
                       'CFLAGS="-DNACL_ALIGN_BYTES=32 -DNACL_ALIGN_POW2=5" '
                       "--prefix=%(prefix)s "
                       "--target=nacl"
                       % self._args])

    def make(self, log):
        self._build_env.cmd(["make"])
        self._build_env.cmd(["make", "install"])


class Module2(ModuleBase):

    name = "gcc"

    def get(self, env, dest_dir):
        untar_multiple(env, dest_dir,
                       [os.path.join(tar_dir, "gcc/gcc-core-4.2.2.tar.bz2"),
                        os.path.join(tar_dir, "gcc/gcc-g++-4.2.2.tar.bz2")])
        self._env.cmd(["patch", "-d", dest_dir, "-p1",
                       "-i", os.path.join(patch_dir, "gcc-4.2.2.patch")])

    def configure(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        # CFLAGS has to be passed via environment because the
        # configure script can't cope with spaces otherwise.
        self._build_env.cmd(["sh", "-c",
                       "CC=gcc "
                       'CFLAGS="-Dinhibit_libc -D__gthr_posix_h -DNACL_ALIGN_BYTES=32 -DNACL_ALIGN_POW2=5" '
                       "%(source_dir)s/configure "

                       "--without-headers "
                       "--disable-libmudflap "
                       "--disable-decimal-float "
                       "--disable-libssp "
                       "--enable-languages=c "
                       "--disable-threads " # pregcc
                       "--disable-libstdcxx-pch "
                       "--disable-shared "

                       "--prefix=%(prefix)s "
                       "--target=nacl"
                       % self._args])

    def make(self, log):
        # The default make target doesn't work - it gives libiberty
        # configure failures.  Need to do "all-gcc" instead.
        self._build_env.cmd(["sh", "-c", "make all-gcc -j2"])
        self._build_env.cmd(["sh", "-c", "make install-gcc"])


class Module3(ModuleBase):

    name = "newlib"

    def get(self, env, dest_dir):
        untar(env, dest_dir,
              os.path.join(tar_dir, "newlib/newlib-1.17.0.tar.gz"))
        self._env.cmd(["patch", "-d", dest_dir, "-p1",
                       "-i", os.path.join(patch_dir, "newlib-1.17.0.patch")])

    def configure(self, log):
        # This is like exporting the kernel headers to glibc.
        # This should be done differently.
        self._env.cmd(
            [os.path.join(nacl_dir, "src/trusted/service_runtime/export_header.py"),
             os.path.join(nacl_dir, "src/trusted/service_runtime/include"),
             os.path.join(self._source_dir, "newlib/libc/sys/nacl")])

        self._env.cmd(["mkdir", "-p", self._build_dir])
        # CFLAGS has to be passed via environment because the
        # configure script can't cope with spaces otherwise.
        self._build_env.cmd(["sh", "-c",
                       'CFLAGS="-m32 -march=i486 -msse2 -mfpmath=sse" '
                       "%(source_dir)s/configure "
                       "--enable-newlib-io-long-long "
                       "--enable-newlib-io-c99-formats "
                       "--prefix=%(prefix)s "
                       "--target=nacl"
                       % self._args])

    def make(self, log):
        self._build_env.cmd(["sh", "-c", "make"])
        self._build_env.cmd(["sh", "-c", "make install"])


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
