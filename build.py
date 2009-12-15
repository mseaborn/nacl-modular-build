
import os
import shutil
import subprocess
import sys

import action_tree
import cmd_env


nacl_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client"
tar_dir = "/home/mseaborn/devel/nacl-trunk/src/third_party"
patch_dir = "/home/mseaborn/devel/nacl-trunk/src/native_client/tools/patches"


def get_one(lst):
    assert len(lst) == 1, lst
    return lst[0]

def write_file(filename, data):
    fh = open(filename, "w")
    try:
        fh.write(data)
    finally:
        fh.close()


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


# write_tree(dest_dir) makes a fresh copy of the tree in dest_dir.
# It can assume that dest_dir is initially empty.
# The state of dest_dir is undefined if write_tree() fails.

class EmptyTree(object):

    def write_tree(self, env, dest_dir):
        pass


class TarballTree(object):

    def __init__(self, tar_path):
        self._tar_path = tar_path

    def write_tree(self, env, dest_dir):
        untar(env, dest_dir, os.path.join(tar_dir, self._tar_path))


class MultiTarballTree(object):

    def __init__(self, tar_paths):
        self._tar_paths = tar_paths

    def write_tree(self, env, dest_dir):
        untar_multiple(env, dest_dir, [os.path.join(tar_dir, tar_path)
                                       for tar_path in self._tar_paths])


class PatchedTree(object):

    def __init__(self, orig_tree, patch_file):
        self._orig_tree = orig_tree
        self._patch_file = patch_file

    def write_tree(self, env, dest_dir):
        self._orig_tree.write_tree(env, dest_dir)
        env.cmd(["patch", "-d", dest_dir, "-p1",
                 "-i", os.path.join(patch_dir, self._patch_file)])


class EnvVarEnv(object):

    def __init__(self, envvars, env):
        self._envvars = envvars
        self._env = env

    def cmd(self, args, **kwargs):
        return self._env.cmd(
            ["env"] + ["%s=%s" % (key, value) for key, value in self._envvars]
            + args, **kwargs)


class ModuleBase(object):

    def __init__(self, build_dir, prefix, install_dir, env_vars):
        self._env = cmd_env.VerboseWrapper(cmd_env.BasicEnv())
        self._source_dir = os.path.join(os.getcwd(), "source", self.name)
        self._build_dir = build_dir
        self._prefix = prefix
        self._install_dir = install_dir
        self._build_env = cmd_env.PrefixCmdEnv(
            cmd_env.in_dir(self._build_dir), EnvVarEnv(env_vars, self._env))
        self._args = {"prefix": self._prefix,
                      "source_dir": self._source_dir}

    def all(self):
        return action_tree.make_node(
            [self.unpack, self.configure, self.make], self.name)

    def unpack(self, log):
        if not os.path.exists(self._source_dir):
            temp_dir = "%s.temp" % self._source_dir
            os.makedirs(temp_dir)
            self.source.write_tree(self._env, temp_dir)
            os.rename(temp_dir, self._source_dir)


def remove_tree(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)


def copy_onto(source_dir, dest_dir):
    for leafname in os.listdir(source_dir):
        subprocess.check_call(["cp", "-a", os.path.join(source_dir, leafname),
                               "-t", dest_dir])


def install_destdir(prefix_dir, install_dir, func):
    temp_dir = "%s.tmp" % install_dir
    remove_tree(temp_dir)
    func(temp_dir)
    remove_tree(install_dir)
    # Tree is installed into $DESTDIR/$prefix.
    # We need to strip $prefix.
    assert prefix_dir.startswith("/")
    os.rename(os.path.join(temp_dir, prefix_dir.lstrip("/")), install_dir)
    # TODO: assert that temp_dir doesn't contain anything except prefix dirs
    remove_tree(temp_dir)
    subprocess.check_call(["mkdir", "-p", prefix_dir])
    copy_onto(install_dir, prefix_dir)


binutils_tree = PatchedTree(TarballTree("binutils/binutils-2.20.tar.bz2"), 
                            "binutils-2.20.patch")
gcc_tree = PatchedTree(MultiTarballTree(["gcc/gcc-core-4.2.2.tar.bz2",
                                         "gcc/gcc-g++-4.2.2.tar.bz2"]),
                       "gcc-4.2.2.patch")
newlib_tree = PatchedTree(TarballTree("newlib/newlib-1.17.0.tar.gz"),
                          "newlib-1.17.0.patch")


class ModuleBinutils(ModuleBase):

    name = "binutils"
    source = binutils_tree

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
        install_destdir(
            self._prefix, self._install_dir,
            lambda dest: self._build_env.cmd(["make", "install",
                                              "DESTDIR=%s" % dest]))


class ModulePregcc(ModuleBase):

    name = "gcc"
    source = gcc_tree

    def configure(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        # CFLAGS has to be passed via environment because the
        # configure script can't cope with spaces otherwise.
        self._build_env.cmd(["sh", "-c",
                       "CC=gcc "
                       'CFLAGS="-Dinhibit_libc -D__gthr_posix_h -DNACL_ALIGN_BYTES=32 -DNACL_ALIGN_POW2=5" '
                       "%(source_dir)s/configure "

                       "--with-as=`which nacl-as` " # Experimental

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
        install_destdir(
            self._prefix, self._install_dir,
            lambda dest: self._build_env.cmd(["make", "install-gcc",
                                              "DESTDIR=%s" % dest]))


class ModuleFullgcc(ModuleBase):

    name = "fullgcc"
    source = gcc_tree

    def configure(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        # CFLAGS has to be passed via environment because the
        # configure script can't cope with spaces otherwise.
        self._build_env.cmd(["sh", "-c",
                       "CC=gcc "
                       'CFLAGS="-Dinhibit_libc -DNACL_ALIGN_BYTES=32 -DNACL_ALIGN_POW2=5" '
                       "%(source_dir)s/configure "

                       "--with-as=`which nacl-as` " # Experimental
                       "--with-newlib "
                       "--enable-threads=nacl "
                       "--enable-tls "

                       # "--without-headers "
                       "--disable-libmudflap "
                       "--disable-decimal-float "
                       "--disable-libssp "
                       "--disable-libgomp "
                       "--enable-languages=c "
                       # "--disable-threads " # pregcc
                       "--disable-libstdcxx-pch "
                       "--disable-shared "
                       '--enable-languages="c,c++" '

                       "--prefix=%(prefix)s "
                       "--target=nacl"
                       % self._args])

    def make(self, log):
        # The default make target doesn't work - it gives libiberty
        # configure failures.  Need to do "all-gcc" instead.
        self._build_env.cmd(["sh", "-c", "make all -j2"])
        install_destdir(
            self._prefix, self._install_dir,
            lambda dest: self._build_env.cmd(["make", "install",
                                              "DESTDIR=%s" % dest]))


class ModuleNewlib(ModuleBase):

    name = "newlib"
    source = newlib_tree

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
        install_destdir(
            self._prefix, self._install_dir,
            lambda dest: self._build_env.cmd(["make", "install",
                                              "DESTDIR=%s" % dest]))


class ModuleNcthreads(ModuleBase):

    name = "nc_threads"
    source = EmptyTree()

    def configure(self, log):
        pass

    def make(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        def do_make(dest):
            self._build_env.cmd(
                cmd_env.in_dir(nacl_dir) +
                ["./scons", "MODE=nacl_extra_sdk", "install_libpthread",
                 "naclsdk_mode=custom:%s" %
                 os.path.join(dest, self._prefix.lstrip("/")),
                 "naclsdk_validate=0",
                 "--verbose"])
        install_destdir(self._prefix, self._install_dir, do_make)


class ModuleLibnacl(ModuleBase):

    # Covers libnacl.a, crt[1ni].o and misc libraries built with Scons.
    name = "libnacl"
    source = EmptyTree()

    def configure(self, log):
        pass

    def make(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        # This requires scons to pass PATH through so that it can run
        # nacl-gcc.  We set naclsdk_mode to point to an empty
        # directory so it can't get nacl-gcc from there.  However, if
        # scons-out is already populated, scons won't try to run
        # nacl-gcc.
        def do_make(dest):
            self._build_env.cmd(
                cmd_env.in_dir(nacl_dir) +
                ["./scons", "MODE=nacl_extra_sdk", "extra_sdk_update",
                 "naclsdk_mode=custom:%s" %
                 os.path.join(dest, self._prefix.lstrip("/")),
                 "naclsdk_validate=0",
                 "--verbose"])
        install_destdir(self._prefix, self._install_dir, do_make)


class TestModule(ModuleBase):

    name = "test"
    source = EmptyTree()

    def configure(self, log):
        pass

    def make(self, log):
        self._env.cmd(["mkdir", "-p", self._build_dir])
        write_file(os.path.join(self._build_dir, "hellow.c"), """
#include <stdio.h>
int main() {
  printf("Hello world\\n");
  return 0;
}
""")
        self._build_env.cmd(["sh", "-c", "nacl-gcc hellow.c -o hellow"])


def add_to_path(path, dir_path):
    return "%s:%s" % (dir_path, path)


mods = [
    ModuleBinutils,
    ModulePregcc,
    ModuleNewlib,
    ModuleNcthreads,
    ModuleFullgcc,
    ModuleLibnacl,
    TestModule,
    ]

def all_mods_shared_prefix():
    nodes = []
    path = os.environ["PATH"]
    env_vars = []

    prefix = os.path.join(os.getcwd(), "shared/prefix")
    build_base = os.path.join(os.getcwd(), "shared/build")
    install_base = os.path.join(os.getcwd(), "shared/install")
    path = add_to_path(path, os.path.join(prefix, "bin"))
    for mod in mods:
        build_dir = os.path.join(build_base, mod.name)
        install_dir = os.path.join(install_base, mod.name)
        nodes.append(mod(build_dir, prefix, install_dir, env_vars).all())
    env_vars.append(("PATH", path))
    return action_tree.make_node(nodes, name="all")

def all_mods_split_prefix():
    nodes = []
    path = os.environ["PATH"]
    env_vars = []

    prefix_base = os.path.join(os.getcwd(), "split/prefix")
    build_base = os.path.join(os.getcwd(), "split/build")
    install_base = os.path.join(os.getcwd(), "shared/install")
    for mod in mods:
        prefix = os.path.join(prefix_base, mod.name)
        build_dir = os.path.join(build_base, mod.name)
        install_dir = os.path.join(install_base, mod.name)
        path = add_to_path(path, os.path.join(prefix, "bin"))
        nodes.append(mod(build_dir, prefix, install_dir, env_vars).all())
    env_vars.append(("PATH", path))
    return action_tree.make_node(nodes, name="all")


class AllMods(object):

    @action_tree.action_node
    def all(self):
        return [("shared", all_mods_shared_prefix()),
                ("split", all_mods_split_prefix())]


if __name__ == "__main__":
    action_tree.action_main(AllMods().all, sys.argv[1:])
