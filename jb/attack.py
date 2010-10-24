from mg import *
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from concurrence import *
import random
import time

alphabet = "abcdefghijklmnopqrstuvwxyz"

def store_error(target, error):
    error = str(error)
    print "%s error: %s" % (target["host"], error)
    try:
        target["errors"][error] += 1
    except KeyError:
        target["errors"][error] = 1

def random_string(length):
    return ''.join([random.choice(alphabet) for i in range(0, length)])
    
def create_post(target, title, body):
    content = "title=%s&body=%s" % (urlencode(title), urlencode(body))
    if len(content) > 1024 * 1024:
        store_error(target, "request_too_large")
        return
    cnn = HTTPConnection()
    try:
        cnn.connect((target["host"], 80))
        try:
            start = time.time()
            req = cnn.post("/posts", content)
            req.add_header("Content-type", "application/x-www-form-urlencoded")
            req.add_header("Content-length", len(content))
            res = cnn.perform(req)
            if res.status_code != 302:
                store_error(target, "create_post: %d" % res.status_code)
            print "post len=%d, time=%f" % (len(content), time.time() - start)
        finally:
            cnn.close()
    except IOError as e:
        store_error(target, e)

def fetch_post(target, id):
    cnn = HTTPConnection()
    try:
        cnn.connect((target["host"], 80))
        try:
            start = time.time()
            req = cnn.get("/posts/%s" % id)
            res = cnn.perform(req)
            if res.status_code != 200:
                store_error(target, "fetch_post: %d" % res.status_code)
            print "get time=%f" % (time.time() - start)
        finally:
            cnn.close()
    except IOError as e:
        store_error(target, e)

def comment_post(target, id, body):
    content = "body=%s" % (urlencode(body))
    if len(content) > 1024 * 1024:
        store_error(target, "request_too_large")
        return
    cnn = HTTPConnection()
    try:
        cnn.connect((target["host"], 80))
        try:
            start = time.time()
            req = cnn.post("/posts/%s/comments" % id, content)
            req.add_header("Content-type", "application/x-www-form-urlencoded")
            req.add_header("Content-length", len(content))
            res = cnn.perform(req)
            if res.status_code != 302:
                store_error(target, "create_comment: %d" % res.status_code)
            print "comment len=%d, time=%f" % (len(content), time.time() - start)
        finally:
            cnn.close()
    except IOError as e:
        store_error(target, e)

def create_post_with_large_title(target):
    create_post(target, "Title", random_string(950000))
