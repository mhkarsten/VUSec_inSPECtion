import os
import shutil
from ..package import Package
from ..util import run, download, require_program, param_attrs


class APR(Package):
    """
    The Apache Portable Runtime.

    :identifier: apr-<version>
    :param version: version to download
    """
    def __init__(self, version: str):
        self.version = version

    def ident(self):
        return 'apr-' + self.version

    def fetch(self, ctx):
        _fetch_and_unpack(ctx, 'apr', 'apr-' + self.version)

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        if not os.path.exists('Makefile'):
            run(ctx, ['../src/configure',
                      '--prefix=' + self.path(ctx, 'install')])
        run(ctx, 'make -j%d' % ctx.jobs)

    def install(self, ctx):
        os.chdir('obj')
        run(ctx, 'make install')

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def is_built(self, ctx):
        return os.path.exists('obj/apr-1-config')

    def is_installed(self, ctx):
        return os.path.exists('install/bin/apr-1-config')

    def config_path(self, ctx):
        return self.path(ctx, 'install', 'bin', 'apr-1-config')


class APRUtil(Package):
    """
    The Apache Portable Runtime utilities.

    :identifier: apr-util-<version>
    :param version: version to download
    :param apr: APR package to depend on
    """
    @param_attrs
    def __init__(self, version: str, apr: APR):
        pass

    def dependencies(self):
        yield self.apr

    def ident(self):
        return 'apr-util-' + self.version

    def fetch(self, ctx):
        _fetch_and_unpack(ctx, 'apr', 'apr-util-' + self.version)

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        if not os.path.exists('Makefile'):
            run(ctx, ['../src/configure',
                      '--prefix=' + self.path(ctx, 'install'),
                      '--with-apr=' + self.apr.config_path(ctx)])
        run(ctx, 'make -j%d' % ctx.jobs)

    def install(self, ctx):
        os.chdir('obj')
        run(ctx, 'make install')

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def is_built(self, ctx):
        return os.path.exists('obj/apu-1-config')

    def is_installed(self, ctx):
        return os.path.exists('install/bin/apu-1-config')

    def config_path(self, ctx):
        return self.path(ctx, 'install', 'bin', 'apu-1-config')


class ApacheBench(Package):
    """
    Apache's ``ab`` benchmark.

    :identifier: ab-<version>
    :param httpd_version: httpd version
    :param apr: APR package to depend on
    :param apr_util: APR utilities package to depend on
    """
    @param_attrs
    def __init__(self, httpd_version: str, apr: APR, apr_util: APRUtil):
        pass

    def dependencies(self):
        yield self.apr
        yield self.apr_util

    def ident(self):
        return 'ab-' + self.httpd_version

    def fetch(self, ctx):
        _fetch_and_unpack(ctx, 'httpd', 'httpd-' + self.httpd_version)

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        if not os.path.exists('Makefile'):
            run(ctx, ['../src/configure',
                      '--prefix=' + self.path(ctx, 'install'),
                      '--with-apr=' + self.apr.config_path(ctx),
                      '--with-apr-util=' + self.apr_util.config_path(ctx)])
        run(ctx, 'make -C support TARGETS=ab')

    def install(self, ctx):
        os.makedirs('install/bin', exist_ok=True)
        shutil.copy('obj/support/ab', 'install/bin')

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def is_built(self, ctx):
        return os.path.exists('obj/support/ab')

    def is_installed(self, ctx):
        return os.path.exists('install/bin/ab')

    @classmethod
    def default(cls, httpd_version='2.4.41',
                apr_version='1.7.0',
                apr_util_version='1.6.1'):
        """
        Create a package with default versions for all dependencies.

        :param httpd_version: httpd version
        :param apr_version: APR version
        :param apr_util_version: APR utilities version
        """
        apr = APR(apr_version)
        apr_util = APRUtil(apr_util_version, apr)
        return cls(httpd_version, apr, apr_util)


def _fetch_and_unpack(ctx, repo, basename):
    require_program(ctx, 'tar', 'required to unpack source tarfile')
    tarname = basename + '.tar.bz2'
    download(ctx, 'http://apache.cs.uu.nl/%s/%s' % (repo, tarname))
    run(ctx, ['tar', '-xf', tarname])
    shutil.move(basename, 'src')
    os.remove(tarname)
