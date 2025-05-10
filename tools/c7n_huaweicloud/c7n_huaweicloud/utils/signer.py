#
# Copyright (c) Huawei Technologies CO., Ltd. 2022-2024. All rights reserved.
#
import copy
import sys
import hashlib
import hmac
import binascii
from datetime import datetime

if sys.version_info.major < 3:
    from urllib import quote, unquote

    def hmacsha256(byte, msg):
        return hmac.new(byte, msg, digestmod=hashlib.sha256).digest()

    # Create a "String to Sign".
    def StringToSign(request, time):
        b = HexEncodeSHA256Hash(request)
        return "%s\n%s\n%s" % (Alg, datetime.strftime(time, DateFormat), b)

else:
    from urllib.parse import quote, unquote

    def hmacsha256(byte, msg):
        return hmac.new(byte.encode('utf-8'),
                        msg.encode('utf-8'),
                        digestmod=hashlib.sha256).digest()

    # Create a "String to Sign".
    def StringToSign(request, time):
        b = HexEncodeSHA256Hash(request.encode('utf-8'))
        return "%s\n%s\n%s" % (Alg, datetime.strftime(time, DateFormat), b)


def urlencode(str):
    return quote(str, safe='~')


def findHeader(req, h):
    for header in req.headers:
        if header.lower() == h.lower():
            return req.headers[header]
    return None


# HexEncodeSHA256Hash returns hexcode of sha256
def HexEncodeSHA256Hash(d):
    sha = hashlib.sha256()
    sha.update(d)
    return sha.hexdigest()


# HWS API Gateway Signature
class HttpRequest:
    def __init__(self, m="", u="", h=None, b=""):
        self.method = m
        sp = u.split("://", 1)
        s = 'http'
        if len(sp) > 1:
            s = sp[0]
            u = sp[1]
        q = {}
        sp = u.split('?', 1)
        u = sp[0]
        if len(sp) > 1:
            for kv in sp[1].split("&"):
                sp = kv.split("=", 1)
                k = sp[0]
                v = ""
                if len(sp) > 1:
                    v = sp[1]
                if k != '':
                    k = unquote(k)
                    v = unquote(v)
                    if k in q:
                        q[k].append(v)
                    else:
                        q[k] = [v]
        sp = u.split('/', 1)
        host = sp[0]
        if len(sp) > 1:
            u = '/' + sp[1]
        else:
            u = '/'

        self.scheme = s
        self.host = host
        self.uri = u
        self.query = q
        if h is None:
            self.headers = {}
        else:
            self.headers = copy.deepcopy(h)
        if sys.version_info.major < 3:
            self.body = b
        else:
            self.body = b.encode("utf-8")


DateFormat = "%Y%m%dT%H%M%SZ"
Alg = "SDK-HMAC-SHA256"
HXDate = "X-Sdk-Date"
HHost = "host"
HAuthorization = "Authorization"
HContentSha256 = "x-sdk-content-sha256"


# Build a CanonicalRequest from a regular request string
#
# CanonicalRequest =
#  HTTPRequestMethod + '\n' +
#  CanonicalURI + '\n' +
#  CanonicalQueryString + '\n' +
#  CanonicalHeaders + '\n' +
#  SignedHeaders + '\n' +
#  HexEncode(Hash(RequestPayload))
def CanonicalRequest(req, sHeaders):
    canonicalHeaders = CanonicalHeaders(req, sHeaders)
    hencode = findHeader(req, HContentSha256)
    if hencode is None:
        hencode = HexEncodeSHA256Hash(req.body)
    return "%s\n%s\n%s\n%s\n%s\n%s" % (req.method.upper(), CanonicalURI(req),
                                       CanonicalQueryString(req),
                                       canonicalHeaders,
                                       ";".join(sHeaders), hencode)


def CanonicalURI(req):
    patterns = unquote(req.uri).split('/')
    uri = []
    for value in patterns:
        uri.append(urlencode(value))
    url_path = "/".join(uri)
    if url_path[-1] != '/':
        url_path = url_path + "/"  # always end with /
    # r.uri = urlpath
    return url_path


def CanonicalQueryString(req):
    keys = []
    for key in req.query:
        keys.append(key)
    keys.sort()
    arr = []
    for key in keys:
        ke = urlencode(key)
        value = req.query[key]
        if type(value) is list:
            value.sort()
            for v in value:
                kv = ke + "=" + urlencode(str(v))
                arr.append(kv)
        else:
            kv = ke + "=" + urlencode(str(value))
            arr.append(kv)
    return '&'.join(arr)


def CanonicalHeaders(req, sHeaders):
    arr = []
    _headers = {}
    for k in req.headers:
        keyEncoded = k.lower()
        value = req.headers[k]
        valueEncoded = value.strip()
        _headers[keyEncoded] = valueEncoded
        if sys.version_info.major == 3:
            req.headers[k] = valueEncoded.encode("utf-8").decode('iso-8859-1')
    for k in sHeaders:
        arr.append(k + ":" + _headers[k])
    return '\n'.join(arr) + "\n"


def SignedHeaders(req):
    arr = []
    for k in req.headers:
        arr.append(k.lower())
    arr.sort()
    return arr


# Create the HWS Signature.
def SignStringToSign(strToSign, sigKey):
    hmac = hmacsha256(sigKey, strToSign)
    return binascii.hexlify(hmac).decode()


# Get the finalized value for the "Authorization" header.  The signature
# parameter is the output from SignStringToSign
def AuthHeaderValue(sig, AppKey, sHeaders):
    return "%s Access=%s, SignedHeaders=%s, Signature=%s" % (
        Alg, AppKey, ";".join(sHeaders), sig)


class Signer:
    def __init__(self):
        self.Key = ""
        self.Secret = ""

    def Verify(self, req, authorization):
        if sys.version_info.major == 3 and isinstance(req.body, str):
            req.body = req.body.encode('utf-8')
        headerTime = findHeader(req, HXDate)
        if headerTime is None:
            return False
        else:
            time = datetime.strptime(headerTime, DateFormat)

        r_verify = copy.deepcopy(req)
        r_verify.headers.pop(HAuthorization, None)
        signedHeaders = SignedHeaders(r_verify)
        canonicalRequest = CanonicalRequest(r_verify, signedHeaders)
        stringToSign = StringToSign(canonicalRequest, time)
        signature = SignStringToSign(stringToSign, self.Secret)
        authValue = AuthHeaderValue(signature, self.Key, signedHeaders)
        return authorization == authValue

    # SignRequest set Authorization header
    def Sign(self, req):
        if sys.version_info.major == 3 and isinstance(req.body, str):
            req.body = req.body.encode('utf-8')
        headerTime = findHeader(req, HXDate)
        if headerTime is None:
            time = datetime.utcnow()
            req.headers[HXDate] = datetime.strftime(time, DateFormat)
        else:
            time = datetime.strptime(headerTime, DateFormat)

        haveHost = False
        for key in req.headers:
            if key.lower() == 'host':
                haveHost = True
                break
        if not haveHost:
            req.headers["host"] = req.host
        req.headers["content-length"] = str(len(req.body))
        queryString = CanonicalQueryString(req)
        if queryString != "":
            req.uri = req.uri + "?" + queryString
        signedHeaders = SignedHeaders(req)
        canonicalRequest = CanonicalRequest(req, signedHeaders)
        stringToSign = StringToSign(canonicalRequest, time)
        signature = SignStringToSign(stringToSign, self.Secret)
        authValue = AuthHeaderValue(signature, self.Key, signedHeaders)
        req.headers[HAuthorization] = authValue
