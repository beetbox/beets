############
Contributing
############

.. contents::
    :depth: 3

Thank you!
==========

First off, thank you for considering contributing to beets! It’s people
like you that make beets continue to succeed.

These guidelines describe how you can help most effectively. By
following these guidelines, you can make life easier for the development
team as it indicates you respect the maintainers’ time; in return, the
maintainers will reciprocate by helping to address your issue, review
changes, and finalize pull requests.

Types of Contributions
======================

We love to get contributions from our community—you! There are many ways
to contribute, whether you’re a programmer or not.

Non-Programming
---------------

-  Promote beets! Help get the word out by telling your friends, writing
   a blog post, or discussing it on a forum you frequent.
-  Improve the `documentation`_. It’s
   incredibly easy to contribute here: just find a page you want to
   modify and hit the “Edit on GitHub” button in the upper-right. You
   can automatically send us a pull request for your changes.
-  GUI design. For the time being, beets is a command-line-only affair.
   But that’s mostly because we don’t have any great ideas for what a
   good GUI should look like. If you have those great ideas, please get
   in touch.
-  Benchmarks. We’d like to have a consistent way of measuring speed
   improvements in beets’ tagger and other functionality as well as a
   way of comparing beets’ performance to other tools. You can help by
   compiling a library of freely-licensed music files (preferably with
   incorrect metadata) for testing and measurement.
-  Think you have a nice config or cool use-case for beets? We’d love to
   hear about it! Submit a post to our `our
   forums <https://discourse.beets.io/>`__ under the “Show and Tell”
   category for a chance to get featured in `the
   docs <https://beets.readthedocs.io/en/stable/guides/advanced.html>`__.
-  Consider helping out in `our forums <https://discourse.beets.io/>`__
   by responding to support requests or driving some new discussions.

Programming
-----------

-  As a programmer (even if you’re just a beginner!), you have a ton of
   opportunities to get your feet wet with beets.
-  For developing plugins, or hacking away at beets, there’s some good
   information in the `“For Developers” section of the
   docs <https://beets.readthedocs.io/en/stable/dev/>`__.

Getting the Source
^^^^^^^^^^^^^^^^^^

The easiest way to get started with the latest beets source is to use
`pip`_ to install an “editable” package. This
can be done with one command:

.. code-block:: bash

    $ pip install -e git+https://github.com/beetbox/beets.git#egg=beets

Or, equivalently:

.. code-block:: bash

    $ git clone https://github.com/beetbox/beets.git
    $ cd beets
    $ pip install -e .

If you already have a released version of beets installed, you may need
to remove it first by typing ``pip uninstall beets``. The pip command
above will put the beets source in a ``src/beets`` directory and install
the ``beet`` CLI script to a standard location on your system. You may
want to use the ``--src`` option to specify the parent directory where
the source will be checked out and the ``--user`` option such that the
package will be installed to your home directory (compare with the
output of ``pip install --help``).

Code Contribution Ideas
^^^^^^^^^^^^^^^^^^^^^^^

-  We maintain a set of `issues marked as
   “bite-sized” <https://github.com/beetbox/beets/labels/bitesize>`__.
   These are issues that would serve as a good introduction to the
   codebase. Claim one and start exploring!
-  Like testing? Our `test
   coverage <https://codecov.io/github/beetbox/beets>`__ is somewhat
   low. You can help out by finding low-coverage modules or checking out
   other `testing-related
   issues <https://github.com/beetbox/beets/labels/testing>`__.
-  There are several ways to improve the tests in general (see :ref:`testing` and some
   places to think about performance optimization (see
   `Optimization <https://github.com/beetbox/beets/wiki/Optimization>`__).
-  Not all of our code is up to our coding conventions. In particular,
   the `library API
   documentation <https://beets.readthedocs.io/en/stable/dev/library.html>`__
   are currently quite sparse. You can help by adding to the docstrings
   in the code and to the documentation pages themselves. beets follows
   `PEP-257 <https://www.python.org/dev/peps/pep-0257/>`__ for
   docstrings and in some places, we also sometimes use `ReST autodoc
   syntax for
   Sphinx <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`__
   to, for example, refer to a class name.

Your First Contribution
=======================

If this is your first time contributing to an open source project,
welcome! If you are confused at all about how to contribute or what to
contribute, take a look at `this great
tutorial <http://makeapullrequest.com/>`__, or stop by our
`forums <https://discourse.beets.io/>`__ if you have any questions.

We maintain a list of issues we reserved for those new to open source
labeled `“first timers
only” <https://github.com/beetbox/beets/issues?q=is%3Aopen+is%3Aissue+label%3A%22first+timers+only%22>`__.
Since the goal of these issues is to get users comfortable with
contributing to an open source project, please do not hesitate to ask
any questions.

How to Submit Your Work
=======================

Do you have a great bug fix, new feature, or documentation expansion
you’d like to contribute? Follow these steps to create a GitHub pull
request and your code will ship in no time.

1. Fork the beets repository and clone it (see above) to create a
   workspace.
2. Make your changes.
3. Add tests. If you’ve fixed a bug, write a test to ensure that you’ve
   actually fixed it. If there’s a new feature or plugin, please
   contribute tests that show that your code does what it says.
4. Add documentation. If you’ve added a new command flag, for example,
   find the appropriate page under ``docs/`` where it needs to be
   listed.
5. Add a changelog entry to ``docs/changelog.rst`` near the top of the
   document.
6. Run the tests and style checker. The easiest way to run the tests is
   to use `tox`_. For more information on running tests, see :ref:`testing`.
7. Push to your fork and open a pull request! We’ll be in touch shortly.
8. If you add commits to a pull request, please add a comment or
   re-request a review after you push them since GitHub doesn’t
   automatically notify us when commits are added.

Remember, code contributions have four parts: the code, the tests, the
documentation, and the changelog entry. Thank you for contributing!

The Code
========

The documentation has a section on the
`library API <https://beets.readthedocs.io/en/stable/dev/library.html>`__
that serves as an introduction to beets’ design.

Coding Conventions
==================

General
-------
There are a few coding conventions we use in beets:

-  Whenever you access the library database, do so through the provided
   Library methods or via a Transaction object. Never call
   ``lib.conn.*`` directly. For example, do this:

   .. code-block:: python

       with g.lib.transaction() as tx:
             rows = tx.query('SELECT DISTINCT "{0}" FROM "{1}" ORDER BY "{2}"'
                             .format(field, model._table, sort_field))

   To fetch Item objects from the database, use lib.items(…) and supply
   a query as an argument. Resist the urge to write raw SQL for your
   query. If you must use lower-level queries into the database, do
   this:

   .. code-block:: python

       with lib.transaction() as tx:
           rows = tx.query('SELECT …')

   Transaction objects help control concurrent access to the database
   and assist in debugging conflicting accesses.
-  Always use the `future
   imports <http://docs.python.org/library/__future__.html>`__
   ``print_function``, ``division``, and ``absolute_import``, but *not*
   ``unicode_literals``. These help keep your code modern and will help
   in the eventual move to Python 3.
-  ``str.format()`` should be used instead of the ``%`` operator
-  Never ``print`` informational messages; use the
   `logging <http://docs.python.org/library/logging.html>`__ module
   instead. In particular, we have our own logging shim, so you’ll see
   ``from beets import logging`` in most files.

   -  The loggers use
      `str.format <http://docs.python.org/library/stdtypes.html#str.format>`__-style
      logging instead of ``%``-style, so you can type
      ``log.debug("{0}", obj)`` to do your formatting.

-  Exception handlers must use ``except A as B:`` instead of
   ``except A, B:``.

Style
-----

We follow `PEP 8`_ and `google's docstring format`_.

You can use ``tox -e lint`` to check your code for any style errors.

.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _google's docstring format: https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings

Handling Paths
--------------

A great deal of convention deals with the handling of **paths**. Paths
are stored internally—in the database, for instance—as byte strings
(i.e., ``bytes`` instead of ``str`` in Python 3). This is because POSIX
operating systems’ path names are only reliably usable as byte
strings—operating systems typically recommend but do not require that
filenames use a given encoding, so violations of any reported encoding
are inevitable. On Windows, the strings are always encoded with UTF-8;
on Unix, the encoding is controlled by the filesystem. Here are some
guidelines to follow:

-  If you have a Unicode path or you’re not sure whether something is
   Unicode or not, pass it through ``bytestring_path`` function in the
   ``beets.util`` module to convert it to bytes.
-  Pass every path name trough the ``syspath`` function (also in
   ``beets.util``) before sending it to any *operating system* file
   operation (``open``, for example). This is necessary to use long
   filenames (which, maddeningly, must be Unicode) on Windows. This
   allows us to consistently store bytes in the database but use the
   native encoding rule on both POSIX and Windows.
-  Similarly, the ``displayable_path`` utility function converts
   bytestring paths to a Unicode string for displaying to the user.
   Every time you want to print out a string to the terminal or log it
   with the ``logging`` module, feed it through this function.

Editor Settings
---------------

Personally, I work on beets with `vim`_. Here are
some ``.vimrc`` lines that might help with PEP 8-compliant Python
coding::

    filetype indent on
    autocmd FileType python setlocal shiftwidth=4 tabstop=4 softtabstop=4 expandtab shiftround autoindent

Consider installing `this alternative Python indentation
plugin <https://github.com/mitsuhiko/vim-python-combined>`__. I also
like `neomake <https://github.com/neomake/neomake>`__ with its flake8
checker.

.. _testing:

Testing
=======

Running the Tests
-----------------

To run the tests for multiple Python versions, compile the docs, and
check style, use `tox`_. Just type ``tox`` or use something like
``tox -e py27`` to test a specific configuration. `detox`_ makes this go
faster.

You can disable a hand-selected set of "slow" tests by setting the
environment variable SKIP_SLOW_TESTS before running them.

Other ways to run the tests:

-  ``python testall.py`` (ditto)
-  ``python -m unittest discover -p 'test_*'`` (ditto)
-  `pytest`_

You can also see the latest test results on `Linux`_ and on `Windows`_.

Note, if you are on Windows and are seeing errors running tox, it may be related to `this issue`_,
in which case you may have to install tox v3.8.3 e.g. ``python -m pip install tox=3.8.3``

.. _this issue: https://github.com/tox-dev/tox/issues/1550

Coverage
^^^^^^^^

``tox -e cov`` will add coverage info for tests: Coverage is pretty low
still -- see the current status on `Codecov`_.

Red Flags
^^^^^^^^^

The `pytest-random`_ plugin makes it easy to randomize the order of
tests. ``py.test test --random`` will occasionally turn up failing tests
that reveal ordering dependencies—which are bad news!

Test Dependencies
^^^^^^^^^^^^^^^^^

The tests have a few more dependencies than beets itself. (The
additional dependencies consist of testing utilities and dependencies of
non-default plugins exercised by the test suite.) The dependencies are
listed under 'test' in ``extras_require`` in `setup.py`_.
To install the test dependencies, run ``python -m pip install .[test]``.
Or, just run a test suite with ``tox`` which will install them
automatically.

.. _setup.py: https://github.com/beetbox/beets/blob/master/setup.py

Writing Tests
-------------

Writing tests is done by adding or modifying files in folder `test`_.
Take a look at
`https://github.com/beetbox/beets/blob/master/test/test_template.py#L224`_
to get a basic view on how tests are written. We currently allow writing
tests with either `unittest`_ or `pytest`_.

Any tests that involve sending out network traffic e.g. an external API
call, should be skipped normally and run under our weekly `integration
test`_ suite. These tests can be useful in detecting external changes
that would affect ``beets``. In order to do this, simply add the
following snippet before the applicable test case:

.. code-block:: python

    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')

If you do this, it is also advised to create a similar test that 'mocks'
the network call and can be run under normal circumstances by our CI and
others. See `unittest.mock`_ for more info.

-  **AVOID** using the ``start()`` and ``stop()`` methods of
   ``mock.patch``, as they require manual cleanup. Use the annotation or
   context manager forms instead.

.. _Python unittest: https://docs.python.org/2/library/unittest.html
.. _Codecov: https://codecov.io/github/beetbox/beets
.. _pytest-random: https://github.com/klrmn/pytest-random
.. _tox: https://tox.readthedocs.io/en/latest/
.. _detox: https://pypi.org/project/detox/
.. _pytest: https://docs.pytest.org/en/stable/
.. _Linux: https://github.com/beetbox/beets/actions
.. _Windows: https://ci.appveyor.com/project/beetbox/beets/
.. _`https://github.com/beetbox/beets/blob/master/setup.py#L99`: https://github.com/beetbox/beets/blob/master/setup.py#L99
.. _test: https://github.com/beetbox/beets/tree/master/test
.. _`https://github.com/beetbox/beets/blob/master/test/test_template.py#L224`: https://github.com/beetbox/beets/blob/master/test/test_template.py#L224
.. _unittest: https://docs.python.org/3.8/library/unittest.html
.. _integration test: https://github.com/beetbox/beets/actions?query=workflow%3A%22integration+tests%22
.. _unittest.mock: https://docs.python.org/3/library/unittest.mock.html
.. _Python unittest: https://docs.python.org/2/library/unittest.html
.. _documentation: https://beets.readthedocs.io/en/stable/
.. _pip: https://pip.pypa.io/en/stable/
.. _vim: https://www.vim.org/
