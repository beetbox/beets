# Decorator for the HTTP Access Control
# By Armin Ronacher
# http://flask.pocoo.org/snippets/56/
#
# Cross-site HTTP requests are HTTP requests for resources from a different
# domain than the domain of the resource making the request.
# For instance, a resource loaded from Domain A makes a request for a resource
# on Domain B. The way this is implemented in modern browsers is by using
# HTTP Access Control headers
#
# https://developer.mozilla.org/en/HTTP_access_control
#
# The following view decorator implements this
#
# Note that some changes have been made to the original snippet
# to allow changing the CORS origin after the decorator has been attached
# This was done because the flask routing functions are defined before the
# beetsplug hook is called.

from datetime import timedelta
from flask import make_response, request, current_app
from functools import update_wrapper

cors_origin = 'http://127.0.0.1'


def set_cors_origin(origin):
    global cors_origin
    cors_origin = origin


def get_cors_origin():
    return cors_origin


def crossdomain(methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = get_cors_origin()
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator
