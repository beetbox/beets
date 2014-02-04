from base64 import b64encode
import gzip
import sys
import urllib
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
import hmac
import time
import socket
import logging

from hashlib import sha256

try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

# Python 2.4 compatibility
# http://code.google.com/p/boto/source/detail?r=1011
if sys.version[:3] == "2.4":
    # we are using an hmac that expects a .new() method.
    class Faker:
        def __init__(self, which):
            self.which = which
            self.digest_size = self.which().digest_size

        def new(self, *args, **kwargs):
            return self.which(*args, **kwargs)

    sha256 = Faker(sha256)

try:
    from exceptions import Exception
except ImportError:
    pass

SERVICE_DOMAINS = {
    'CA': ('ecs.amazonaws.ca', 'xml-ca.amznxslt.com'),
    'CN': ('webservices.amazon.cn', 'xml-cn.amznxslt.com'),
    'DE': ('ecs.amazonaws.de', 'xml-de.amznxslt.com'),
    'ES': ('webservices.amazon.es', 'xml-es.amznxslt.com'),
    'FR': ('ecs.amazonaws.fr', 'xml-fr.amznxslt.com'),
    'IT': ('webservices.amazon.it', 'xml-it.amznxslt.com'),
    'JP': ('ecs.amazonaws.jp', 'xml-jp.amznxslt.com'),
    'UK': ('ecs.amazonaws.co.uk', 'xml-uk.amznxslt.com'),
    'US': ('ecs.amazonaws.com', 'xml-us.amznxslt.com'),
}

class AmazonError(Exception):
    pass

class AmazonCall(object):
    def __init__(self, AWSAccessKeyId=None, AWSSecretAccessKey=None, \
            AssociateTag=None, Operation=None, Version=None, Region=None, \
            Timeout=None):

        self.AWSAccessKeyId = AWSAccessKeyId
        self.AWSSecretAccessKey = AWSSecretAccessKey
        self.Operation = Operation
        self.AssociateTag = AssociateTag
        self.Version = Version
        self.Region = Region
        self.Timeout = Timeout

    def signed_request(self):
        pass

    def __getattr__(self, k):
        try:
            return object.__getattr__(self, k)
        except:
            return AmazonCall(self.AWSAccessKeyId, self.AWSSecretAccessKey, \
                    self.AssociateTag, Operation=k, Version=self.Version,
                    Region=self.Region, Timeout=self.Timeout)

    def __call__(self, **kwargs):
        logger = logging.getLogger(__name__)

        if 'Style' in kwargs:
            raise AmazonError("The `Style` parameter has been discontinued by AWS. Please remove all references to it and reattempt your request.")

        kwargs['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kwargs['Operation'] = self.Operation
        kwargs['Version'] = self.Version
        kwargs['AWSAccessKeyId'] = self.AWSAccessKeyId
        kwargs['Service'] = "AWSECommerceService"

        if self.AssociateTag:
            kwargs['AssociateTag'] = self.AssociateTag

        service_domain = SERVICE_DOMAINS[self.Region][0]

        keys = sorted(kwargs.keys())

        if sys.version_info[0] == 3:
            quoted_strings = "&".join("%s=%s" % (k, urllib.parse.quote(str(kwargs[k]).encode('utf-8'), safe = '~')) for k in keys)
        else:
            quoted_strings = "&".join("%s=%s" % (k, urllib.quote(unicode(kwargs[k]).encode('utf-8'), safe = '~')) for k in keys)

        data = "GET\n" + service_domain + "\n/onca/xml\n" + quoted_strings

        if sys.version_info[0] == 3:
            digest = hmac.new(bytes(self.AWSSecretAccessKey, encoding='utf-8'), bytes(data, encoding='utf-8'), sha256).digest()
            signature = urllib.parse.quote(b64encode(digest))
        else:
            digest = hmac.new(self.AWSSecretAccessKey, data, sha256).digest()
            signature = urllib.quote(b64encode(digest))

        api_string = "http://" + service_domain + "/onca/xml?" + quoted_strings + "&Signature=%s" % signature
        api_request = urllib2.Request(api_string, headers={"Accept-Encoding": "gzip"})
        if self.Timeout:
            socket.setdefaulttimeout(self.Timeout)

        logger.debug("Amazon URL: %s" % api_string)
        response = urllib2.urlopen(api_request)
        if self.Timeout:
            socket.setdefaulttimeout(None)

        if sys.version_info[0] == 3:
            if "gzip" in response.info().get("Content-Encoding"):
                response_text = gzip.decompress(response.read())
            else:
                response_text = response.read()
        else:
            if "gzip" in response.info().getheader("Content-Encoding"):
                gzipped_file = gzip.GzipFile(fileobj=StringIO(response.read()))
                response_text = gzipped_file.read()
            else:
                response_text = response.read()
        return response_text

class Amazon(AmazonCall):
    def __init__(self, AWSAccessKeyId=None, AWSSecretAccessKey=None, \
            AssociateTag=None, Operation=None, Version="2011-08-01", Region="US", \
            Timeout=None):

        AmazonCall.__init__(self, AWSAccessKeyId, AWSSecretAccessKey, \
            AssociateTag, Operation, Version=Version, Region=Region, Timeout=Timeout)

__all__ = ["Amazon", "AmazonError"]
