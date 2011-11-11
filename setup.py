#! /usr/bin/env python

import os
swdir = os.getcwd()+'/sw'

from distutils.core import setup
from distutils.extension import Extension


ext_commands = { }
ext_modules = [
    Extension("_simplematrix", ["simplematrix.i"],
              swig_opts=['-c++', '-modern'],
              include_dirs=[swdir+'/include'],
              libraries=['linbox', 'gmp', 'givaro', 'lapack', 'cblas'],
              library_dirs=[swdir+'/lib'],
              define_macros=[
                  # other options include:
                  #  FATGHOL_USE_LINBOX_ELIMINATION_PIVOT_NONE
                  #  FATGHOL_USE_LINBOX_DEFAULT (black-box, as of LinBox 1.1.7)
                  #  FATGHOL_USE_RHEINFALL
                  ('FATGHOL_USE_LINBOX_ELIMINATION_PIVOT_LINEAR', 1),
                  ],
            )
    ]
# if Cython is available, use it to compile modules
try:
    import Cython.Distutils
    ext_commands['build_ext'] = Cython.Distutils.build_ext
    NO_ASSERTS = [
        ('PYREX_WITHOUT_ASSERTIONS', 1),
        ('NDEBUG', 1),
        ]
    ext_modules.extend([
        Extension("aggregate",      ["aggregate.py"],      define_macros=NO_ASSERTS),
        Extension("cache",          ["cache.py"],          define_macros=NO_ASSERTS),
        Extension("combinatorics",  ["combinatorics.py"],  define_macros=NO_ASSERTS),
        Extension("cycliclist",     ["cycliclist.py"],     define_macros=NO_ASSERTS),
        Extension("graph_homology", ["graph_homology.py"], define_macros=NO_ASSERTS),
        Extension("homology",       ["homology.py"],       define_macros=NO_ASSERTS),
        Extension("iterators",      ["iterators.py"],      define_macros=NO_ASSERTS),
        Extension("loadsave",       ["loadsave.py"],       define_macros=NO_ASSERTS),
        Extension("rg",             ["rg.py"],             define_macros=NO_ASSERTS),
        Extension("utils",          ["utils.py"],          define_macros=NO_ASSERTS),
        Extension("valences",       ["valences.py"],       define_macros=NO_ASSERTS),
        ])
except ImportError:
    pass


def read_whole_file(path):
    stream = open(path, 'r')
    text = stream.read()
    stream.close
    return text



setup (
    name = "fatghol",
    version = "5.0", # see: http://packages.python.org/distribute/setuptools.html

    # for building the package
    cmdclass = ext_commands,
    ext_modules = ext_modules,

    # metadata for upload to PyPI
    description = "A Python library and simple command-line frontend for computing with Penner's Fat Graphs",
    long_description = read_whole_file('README.txt'),
    author = "Riccardo Murri",
    author_email = "riccardo.murri@gmail.com",
    license = "LGPL",
    keywords = "geometry fatgraphs homology",
    url = "http://fatghol.googlecode.com/", # project home page
    # see http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "License :: DFSG approved",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Scientific/Engineering",
        ],

    # run-time dependencies
    install_requires = [
        # Cython
        'cython',
        # Michele Simionato's "decorator" package
        'decorator',
        ],

    # `zip_safe` can ease deployment, but is only allowed if the package
    # do *not* do any __file__/__path__ magic nor do they access package data
    # files by file name (use `pkg_resources` instead).
    zip_safe = True,
)