# Thank you!
First off, thank you for considering contributing to `beets`. It's people like you that continue to allow `beets` to succeed.

Following these guidelines helps to communicate that you respect the time of the developers managing and developing this open source project. In return, they should reciprocate that respect in addressing your issue, assessing changes, and helping you finalize your pull requests.

# Types of contributions

`beets` is an open source project and we love to receive contributions from our community — you! There are many ways to contribute, programmer or not.

## Non-programming contribution ideas
* Promote beets! Help get the word out by telling your friends, writing a blog
  post, or discussing it on a forum you frequent.
* Improve the [documentation][docs]. It's incredibly easy to contribute here:
  just find a page you want to modify and hit the "Edit on GitHub" button in
  the upper-right. You can automatically send us a pull request for your
  changes.
* GUI design. For the time being, beets is a command-line-only affair. But
  that's mostly because I don't have any great ideas for what a good GUI
  should look like. If you have those great ideas, please get in touch.
* Benchmarks. We'd like to have a consistent way of measuring speed
  improvements in beets' tagger and other functionality as well as a way of
  comparing beets' performance to other tools. You can help by compiling a
  library of freely-licensed music files (preferably with incorrect metadata)
  for testing and measurement.
* Think you have a nice config or unique use-case for beets? We'd love to hear about it! Submit a post to our [our forums](https://discourse.beets.io/) under the label 'recipe' for a chance to get featured in our [docs](https://beets.readthedocs.io/en/stable/guides/advanced.html).
* Consider helping out in [our forums](https://discourse.beets.io/) by responding to support requests or driving some new discussions. 

[docs]: http://beets.readthedocs.org/

## Programming contributions
* As a programmer (even if you're just a beginner!), you have a ton of opportunities to get your feet wet with `beets`. 
* For developing plugins, or hacking away at beets, there's some good information in the [for developers](https://beets.readthedocs.io/en/stable/dev/) section of the docs.

### Getting the Source

The easiest way to get started with the latest beets source is to use [pip](http://pip.openplans.org/)  to install an "editable" package. This can be done with one command:

    $ pip install -e git+https://github.com/beetbox/beets.git#egg=beets

Or, equivalently:

    $ git clone https://github.com/beetbox/beets.git
    $ cd beets
    $ pip install -e .

If you already have a released version of beets installed, you may need to
remove it first by typing `pip uninstall beets`. The pip command above will put
the beets source in a `src/beets` directory and install the `beet` CLI script to
a standard location on your system. You may want to use the `--src` option to specify
the parent directory where the source will be checked out and the `--user` option
such that the package will be installed to your home directory (compare with the output of
`pip install --help`). 

Alternatively, you can get the source via 
[git at GitHub](http://github.com/beetbox/beets). The pip method above installs
dependencies automatically, but if you do it manually, you can use pip to
install these Python modules:  
* `mutagen`
* `munkres`
* `unidecode`
* `pyYAML`
* `musicbrainzngs`
* `confuse`
* `mediafile`
* `jellyfish`

Please be aware that this list might be out of date, but [setup.py](https://github.com/beetbox/beets/blob/60bba370c0ecc58b4057d78867273e5936d22dee/setup.py#L89-L110) contains a list that is always up to date. With all the required modules in place, you can just type `./beet` in the source directory to run beets from there.


### Code contribution ideas
* We maintain a set of [issues marked as "bite-sized"](https://github.com/beetbox/beets/labels/bitesize). These are issues that would serve as a good introduction to the codebase. Claim one and start exploring!
* Like testing? Our [test coverage](https://codecov.io/github/beetbox/beets) is somewhat low. You can help out by finding low-coverage modules or checking out other [testing-related issues](https://github.com/beetbox/beets/labels/testing).
* There are several ways to improve the tests in general (see [Testing](https://github.com/beetbox/beets/wiki/Testing)) and some places to think about performance optimization (see [Optimization](https://github.com/beetbox/beets/wiki/Optimization)).
* Not all of our code is up to our coding conventions. In particular, the [API documentation][apidocs] are currently quite sparse. You can help by adding to the docstrings in the code and to the documentation pages themselves.

## Your first contribution
If this is your first time contributing to an open source project, welcome! If you are confused at all about how to contribute or what to contribute, take a look at [this great tutorial](http://makeapullrequest.com/), or stop by our [gitter chat room](https://gitter.im/beetbox/beets#) if you have any questions. 

We maintain a list of issues we feel are perfect for first-timers tagged "[good first issue](https://github.com/beetbox/beets/labels/good%20first%20issue)". These issues are perfect for anyone new to open source. In fact, we encourage only users who are new to open source to tackle these. Ideally, the goal for these issues is to get users comfortable with contributing to an open source project for the first time. Please, do not hesitate to ask any questions.

## How to Submit Your Work

Do you have a great bug fix, new feature, or documentation expansion you'd like to contribute? Follow these steps to create a GitHub pull request and your code will ship in no time.

1. Fork the beets repository and clone it (see above) to create a workspace.
2. Make your changes.
3. Add tests. If you've fixed a bug, write a test to ensure that you've actually fixed it. If there's a new feature or plugin, please contribute tests that show that your code does what it says.
4. Add documentation. If you've added a new command flag, for example, find the appropriate page under `docs/` where it needs to be listed.
5. Add a changelog entry to `docs/changelog.rst` near the top of the document.
6. Run the tests and style checker. The easiest way to run the full battery of tests is to use [tox](https://tox.readthedocs.org/en/latest/). This will run the same set of tests that we run on Travis.
7. Push to your fork and open a pull request! We'll be in touch soon.
8. If you add commits to a pull request, please *add a comment* after you push them. (GitHub doesn't notify us when commits are added, so we need your comment so we get an email alert.)

Remember, code contributions have four parts: the code, the tests, the documentation, and the changelog entry. Thank you for contributing!


# The Code

The documentation has an [API documentation section][apidocs] that serves as an introduction to beets' design. There's also an [[Architecture]] page on this wiki.

[apidocs]: http://beets.readthedocs.org/en/latest/dev/api.html

## Coding Conventions

There are a few coding conventions we use in beets:

* Whenever you access the library database, do so through the provided Library
  methods or via a Transaction object. Never call `lib.conn.*` directly.
  Transaction objects help control concurrent access to the database and assist
  in debugging conflicting accesses.
* Always use the [future imports][] `print_function`, `division`, and
  `absolute_import`, but *not* `unicode_literals`. These help keep your code
  modern and will help in the eventual move to Python 3.
* `str.format()` should be used instead of the `%` operator
* Never `print` informational messages; use the [logging][] module instead. In
  particular, we have our own logging shim, so you'll see `from beets import
  logging` in most files.
    * Always log Unicode strings (e.g., `log.debug(u"hello world")`).
    * The loggers use [str.format][]-style logging instead of ``%``-style, so
      you can type `log.debug(u"{0}", obj)` to do your formatting.
 * exceptions must use `except A as B:` instead of `except A, B:`

[future imports]: http://docs.python.org/library/__future__.html
[logging]: http://docs.python.org/library/logging.html
[str.format]: http://docs.python.org/library/stdtypes.html#str.format
[modformat]: http://docs.python.org/library/stdtypes.html#string-formatting-operations

We follow [PEP 8](http://www.python.org/dev/peps/pep-0008/) for style. The buildbot and `tox` will complain if you use tabs for indentation, for example.

## Handling Paths

A great deal of convention deals with the handling of **paths**. Paths are
stored internally -- in the database, for instance -- as byte strings (not
unicode objects). This is because POSIX operating systems' path names are only
reliably usable as byte strings -- even if you request unicode paths, you might
still get back bytes. On Windows, the strings are always encoded with UTF-8; on
Unix, the encoding is controlled by the filesystem. Here are some guidelines to
follow:

* If you have a Unicode path or you're not sure whether something is Unicode or
  not, pass it through `bytestring_path` function in the `beets.util` module to
  convert it to bytes.
* Pass every path name trough the `syspath` function (also in `beets.util`)
  before sending it to any *operating system* file operation (`open`, for
  example). This is necessary to use long filenames (which, maddeningly, must
  be Unicode) on Windows. This allows us to consistently store bytes in the
  database but use the native encoding rule on both POSIX and Windows.
* Similarly, the `displayable_path` utility function converts bytestring paths
  to a Unicode string for displaying to the user. Every time you want to print
  out a string to the terminal or log it with the `logging` module, feed it
  through this function.

## Editor Settings

Personally, I work on beets with [vim](http://www.vim.org/). Here are some
`.vimrc` lines that might help with PEP 8-compliant Python coding:

    filetype indent on
    autocmd FileType python setlocal shiftwidth=4 tabstop=4 softtabstop=4 expandtab shiftround autoindent

Consider installing [this alternative Python indentation
plugin](https://github.com/mitsuhiko/vim-python-combined). I also like
[Syntastic](https://github.com/scrooloose/syntastic) with its [flake8 checker](https://github.com/scrooloose/syntastic/wiki/Python%3A---flake8).
