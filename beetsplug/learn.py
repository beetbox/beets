# This file is part of beets.
# Copyright 2013, Pedro Silva.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Learn things about a Beets library.
"""
import logging

import beets

PLUGIN = 'cluster'
log = logging.getLogger('beets')


def _transform(items, features, kind):
    import numpy as np
    import sklearn.preprocessing
    import sklearn.feature_extraction

    if kind == 'categorical':
        X = [dict((f, getattr(i, f, np.nan)) for f in features) for i in items]
        X = sklearn.feature_extraction.DictVectorizer().fit_transform(X)
    elif kind == 'text':
        X = [getattr(i, f, np.nan) for f in features for i in items]
        X = sklearn.feature_extraction.text.TfidfVectorizer().fit_transform(X)
    elif kind == 'numeric':
        X = [[getattr(i, f, np.nan) for f in features] for i in items]
    else:
        raise Exception('Dont\' know kind of feature %s' % kind)

    return sklearn.preprocessing.Imputer().fit_transform(X)


def _fit(X, k):
    import sklearn.cluster
    kmeans = sklearn.cluster.MiniBatchKMeans(k).fit(X)
    return kmeans


def _predict(kmeans, X):
    labels = kmeans.predict(X)
    return labels


def _reduce(X, c):
    import sklearn.decomposition
    pca = sklearn.decomposition.PCA(n_components=c).fit_transform(X)
    return pca


def _encode(y, scale):
    import sklearn.preprocessing
    labels = sklearn.preprocessing.LabelEncoder().fit_transform(y)
    if scale:
        labels = labels.reshape((len(y), 1)).astype(float)
        labels = sklearn.preprocessing.MinMaxScaler().fit_transform(labels)
        labels = labels.reshape((len(y),))
    return labels


def _plot(X, groups, savefig):
    import matplotlib.cm
    import matplotlib.pyplot

    n_samples, n_features = X.shape
    fig = matplotlib.pyplot.figure()
    colors = matplotlib.cm.jet(_encode(groups, True))

    if n_features == 1:
        matplotlib.pyplot.scatter(xrange(len(X)), X[:, 0], c=colors, s=30)
    elif n_features == 2:
        matplotlib.pyplot.scatter(X[:, 0], X[:, 1], c=colors, s=30)
    elif n_features >= 3:
        import mpl_toolkits.mplot3d
        if n_features > 3:
            X = _reduce(X, 3)
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(X[:, 0], X[:, 1], X[:, 2], c=colors, s=30)

    if savefig:
        matplotlib.pyplot.savefig(savefig)
    else:
        matplotlib.pyplot.show()


class LearnPlugin(beets.plugins.BeetsPlugin):
    '''Learn things about a Beets library.
    '''
    def __init__(self):
        super(LearnPlugin, self).__init__()

        self.config.add({'attributes': []})
        self.config.add({'clusters': 2})
        self.config.add({'format': ''})
        self.config.add({'kind': 'numeric'})
        self.config.add({'plot': False})
        self.config.add({'savefig': False})
        self.config.add({'test': []})
        self.config.add({'train': []})

        self._command = beets.ui.Subcommand('learn', help=__doc__)

        self._command.parser.add_option('-a', '--attributes',
                                        action='callback', dest='attributes',
                                        metavar='LIST',
                                        callback=beets.ui.vararg_callback,
                                        help='list of attributes to cluster')

        self._command.parser.add_option('-c', '--clusters',
                                        action='store', metavar='K',
                                        type=int,
                                        help='how many clusters to find')

        self._command.parser.add_option('-f', '--format',
                                        action='store', type=str,
                                        help='print with custom format',
                                        metavar='FMT')

        self._command.parser.add_option('-k', '--kind',
                                        action='store',
                                        choices=['numeric',
                                                 'categorical',
                                                 'text'],
                                        help='type of attributes (numeric, \
                                        categorical numeric]')

        self._command.parser.add_option('-p', '--plot',
                                        action='store_true',
                                        help='plot results')

        self._command.parser.add_option('-s', '--savefig',
                                        action='store',
                                        help='plot results to file')

        self._command.parser.add_option('-T', '--test',
                                        action='callback', dest='test',
                                        metavar='QUERY',
                                        callback=beets.ui.vararg_callback,
                                        help='test set query')

        self._command.parser.add_option('-t', '--train',
                                        action='callback', dest='train',
                                        metavar='QUERY',
                                        callback=beets.ui.vararg_callback,
                                        help='training set query')

    def commands(self):
        def _learn(lib, opts, args):

            self.config.set_args(opts)
            kind = self.config['kind'].get(str)
            features = self.config['attributes'].get(list)
            fmt = self.config['format'].get(str)
            k = self.config['clusters'].get(int)
            plot = self.config['plot'].get(bool)
            savefig = self.config['savefig'].get(str)
            test = self.config['test'].get(list)
            train = self.config['train'].get(list)
            if not fmt:
                fmt = '$albumartist - $album - $title'
            fmt += ' - {0}'

            items = lib.items(beets.ui.decargs(train or args))
            X = _transform(items, features, kind)
            kmeans = _fit(X, k)

            items = lib.items(beets.ui.decargs(test or args))
            X = _transform(items, features, kind)
            labels = _predict(kmeans, X)

            if plot or savefig:
                _plot(X, labels, savefig)

            for item, label in zip(items, labels):
                beets.ui.print_obj(item, lib, fmt=fmt.format(label))

        self._command.func = _learn
        return [self._command]
