# -*- coding: utf-8 -*-

from mg import *
from itertools import *
from concurrence import Tasklet
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from uuid import uuid4
import jb
import re
import cgi
import time

max_word_len = 30
max_tag_len = 30
max_inline_chunk_len = 200

posts_per_page = 10

alphabet = "abcdefghijklmnopqrstuvwxyz"

re_split_tags = re.compile(r'\s*(,\s*)+')
re_url_comments = re.compile(r'^([a-f0-9]+)/comments$')
re_extract_uuid = re.compile(r'^.*//([a-f0-9]+)$')
re_wildcard = re.compile(r'^(.*)(.)\*$')
delimiters = r'\s\.,\-\!\&\(\)\'"\:;\<\>\/\?\`\|»\—«'
re_word_symbol = re.compile(r'[^%s]' % delimiters)
re_not_word_symbol = re.compile(r'[%s]' % delimiters)
re_text_chunks = re.compile(r'.{1000,}?\S*|.+', re.DOTALL)

# blog post

class BlogPost(CassandraObject):
    _indexes = {
        "created": [[], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BlogPost-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return BlogPost._indexes

class BlogPostList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BlogPost-"
        kwargs["cls"] = BlogPost
        CassandraObjectList.__init__(self, *args, **kwargs)

class BlogPostContent(CassandraObject):
    _indexes = {
    }
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BlogPostContent-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return BlogPostContent._indexes

class BlogPostContentList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BlogPostContent-"
        kwargs["cls"] = BlogPostContent
        CassandraObjectList.__init__(self, *args, **kwargs)

# blog comment

class BlogComment(CassandraObject):
    _indexes = {
        "post-created": [["post"], "created"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BlogComment-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return BlogComment._indexes

class BlogCommentList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "BlogComment-"
        kwargs["cls"] = BlogComment
        CassandraObjectList.__init__(self, *args, **kwargs)

# linguistics

def word_extractor(text):
    for chunk in re_text_chunks.finditer(text):
        text = chunk.group()
        while True:
            m = re_word_symbol.search(text)
            if not m:
                break
            start = m.start()
            m = re_not_word_symbol.search(text, start)
            if m:
                end = m.end()
                if end - start > 3:
                    yield text[start:end-1].lower()
                text = text[end:]
            else:
                if len(text) >= 3:
                    yield text.lower()
                break

# main module

class Blog(Module):
    def register(self):
        Module.register(self)
        self.rdep(["mg.core.cass_struct.CommonCassandraStruct", "mg.core.web.Web", "mg.core.cass_maintenance.CassandraMaintenance"])
        self.rhook("core.template_path", self.template_path)
        self.rhook("web.global_html", self.web_global_html)
        self.rhook("ext-index.index", self.ext_posts)
        self.rhook("ext-posts.index", self.ext_posts)
        self.rhook("ext-posts.page", self.ext_posts_page)
        self.rhook("ext-posts.handler", self.ext_post)
        self.rhook("ext-tags.index", self.ext_tags)
        self.rhook("ext-tags.handler", self.ext_tag)
        self.rhook("ext-search.index", self.ext_search)
        self.rhook("ext-search.handler", self.ext_search)

    def template_path(self, paths):
        paths.append(jb.__path__[0] + "/templates")

    def web_global_html(self):
        return "joyblog/global.html"

    def ext_posts(self):
        return self.posts(1)

    def ext_posts_page(self):
        return self.posts(intz(self.req().args))

    def posts(self, page):
        req = self.req()
        if req.environ.get("REQUEST_METHOD") == "POST":
            title = req.param("title").strip()
            body = req.param("body").strip()
            tags = req.param("tags").strip()
            if title == "":
                title = "Untitled"
            raw_tags = re_split_tags.split(tags) if len(tags) else []
            tags = set()
            for i in range(0, len(raw_tags)):
                if i % 2 == 0:
                    tag = raw_tags[i]
                    tags.add(raw_tags[i].lower())
            post = self.obj(BlogPost)
            post_content = self.obj(BlogPostContent, post.uuid, data={})
            post.set("created", self.now())
            # storing html encoded values
            post.set("title_html", self.upload_if_large(cgi.escape(title)))
            post_content.set("body_html", self.upload_if_large(cgi.escape(body)))
            post_content.set("tags_html", self.upload_if_large(", ".join(['<a href="/tags/%s">%s</a>' % (cgi.escape(urlencode(tag)), cgi.escape(tag)) for tag in tags])))
            # storing raw values
            if False:
                post.set("title", title)
                post_content.set("body", body)
                post.set("tags", list(tags))
            # updating tags index
            mutations = {}
            mutations_tags = []
            clock = Clock(time.time() * 1000)
            app_tag = self.app().tag
            for tag in tags:
                tag_short = tag
                if len(tag_short) > max_tag_len:
                    tag_short = tag_short[0:max_tag_len]
                tag_short = tag_short.encode("utf-8")
                mutations_tags.append(Mutation(ColumnOrSuperColumn(Column(name=tag_short, value=self.upload_if_large(cgi.escape(tag)), clock=clock))))
                mutations["%s-BlogTaggedPosts-%s" % (app_tag, tag_short)] = {"Objects": [Mutation(ColumnOrSuperColumn(Column(name=post.uuid, value="1", clock=clock)))]}
            if len(mutations_tags):
                mutations["%s-BlogTags" % app_tag] = {"Objects": mutations_tags}
            if len(mutations):
                self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
            words = list(chain(word_extractor(title), word_extractor(body)))
            word_stat = {}
            for word in words:
                try:
                    word_stat[word] += 1
                except KeyError:
                    word_stat[word] = 1
            word_stat = word_stat.items()
            word_stat.sort(key=itemgetter(0))
            word_stat.sort(key=itemgetter(1), reverse=True)
            post_content.set("words_html", self.upload_if_large(''.join(["<tr><td>%s</td><td>%s</td></tr>" % (ent[0], ent[1]) for ent in word_stat])))
            post.store()
            post_content.store()
            # deferring fulltext index
            self.update_fulltext(post.uuid, words)
            self.call("web.redirect", "/posts/%s" % post.uuid)
        # loading posts
        posts = self.objlist(BlogPostList, query_index="created", query_reversed=True)
        pages = (len(posts) - 1) / posts_per_page + 1
        if pages < 1:
            pages = 1
        if page < 1 or page > pages:
            self.call("web.not_found")
        del posts[page * posts_per_page:]
        del posts[0:(page - 1) * posts_per_page]
        posts.load()
        vars = {
            "posts": posts.data()
        }
        # page browser
        if pages > 1:
            pages_list = []
            last_show = None
            for i in range(1, pages + 1):
                show = (i <= 5) or (i >= pages - 5) or (abs(i - page) < 5)
                if show:
                    if len(pages_list):
                        pages_list.append({"delim": True})
                    pages_list.append({"entry": {"text": i, "a": None if i == page else {"href": "/posts/page/%d" % i}}})
                elif last_show:
                    if len(pages_list):
                        pages_list.append({"delim": True})
                    pages_list.append({"entry": {"text": "..."}})
                last_show = show
            vars["pages"] = pages_list
        return self.call("web.response_template", "joyblog/posts.html", vars)

    def update_fulltext(self, post_uuid, words):
        stored = set()
        mutations_search = []
        clock = Clock(time.time() * 1000)
        app_tag = self.app().tag
        for word in words:
            if len(word) > max_word_len:
                word = word[0:max_word_len]
            if not word in stored:
                stored.add(word)
                mutations_search.append(Mutation(ColumnOrSuperColumn(Column(name=(u"%s//%s" % (word, post_uuid)).encode("utf-8"), value="1", clock=clock))))
                if len(mutations_search) >= 1000:
                    mutations = {"%s-BlogSearch" % app_tag: {"Objects": mutations_search}}
                    self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
                    mutations_search = []
        if len(mutations_search):
            mutations = {"%s-BlogSearch" % app_tag: {"Objects": mutations_search}}
            self.app().db.batch_mutate(mutations, ConsistencyLevel.QUORUM)

    def ext_post(self):
        req = self.req()
        post_id = req.args
        comment = re_url_comments.match(req.args)
        if comment:
            post_id = comment.groups(1)[0]
        try:
            post = self.obj(BlogPost, post_id)
            post_content = self.obj(BlogPostContent, post_id)
        except ObjectNotFoundException:
            self.call("web.not_found")
        if comment and req.environ.get("REQUEST_METHOD") == "POST":
            body = req.param("body").strip()
            if body == "":
                self.call("web.redirect", "/posts/%s" % post.uuid)
            comment = self.obj(BlogComment)
            comment.set("created", self.now())
            comment.set("post", post.uuid)
            comment.set("body_html", self.upload_if_large(cgi.escape(body)))
            parent = req.param("parent_id")
            if parent and len(parent) == 32:
                comment.set("parent", parent)
            comment.store()
            # deferring fulltext index
            words = word_extractor(body)
            self.update_fulltext(post.uuid, words)
            self.call("web.redirect", "/posts/%s#%s" % (post.uuid, comment.uuid))
        vars = {
            "post_uuid": post.uuid,
            "post": post.data,
            "post_content": post_content.data,
        }
        # rendering comments
        comments = self.objlist(BlogCommentList, query_index="post-created", query_equal=post.uuid)
        comments.load(silent=True)
        render_comments = []
        rendered_comments = {}
        while len(comments):
            remaining = []
            changed = False
            for comment in comments:
                parent = comment.get("parent")
                if parent is None:
                    render_comments.append(comment)
                    rendered_comments[comment.uuid] = comment
                    comment.children = []
                    changed = True
                else:
                    parent = rendered_comments.get(parent)
                    if parent is None:
                        remaining.append(comment)
                    else:
                        parent.children.append(comment)
                        rendered_comments[comment.uuid] = comment
                        comment.children = []
                        changed = True
            comments = remaining
            if not changed:
                break
        for comment in comments:
            render_comments.append(comment)
            comment.children = []
        comments = []
        self.render_comments(comments, render_comments)
        vars["comments"] = comments
        return self.call("web.response_template", "joyblog/post.html", vars)

    def render_comments(self, result, comments):
        for comment in comments:
            result.append({"b": True})
            result.append({"d": comment.data, "c": comment.uuid})
            if len(comment.children):
                self.render_comments(result, comment.children)
            result.append({"e": True})

    def ext_tags(self):
        app_tag = self.app().tag
        tags = self.app().db.get_slice("%s-BlogTags" % app_tag, ColumnParent("Objects"), SlicePredicate(slice_range=SliceRange("", "", count=10000000)), ConsistencyLevel.QUORUM)
        tags = [tag.column.value for tag in tags]
        vars = {
            "tags": tags
        }
        return self.call("web.response_template", "joyblog/tags.html", vars)

    def ext_tag(self):
        req = self.req()
        tag = req.args
        tag_utf8 = tag
        if len(tag_utf8) > max_tag_len:
            tag_utf8 = tag_utf8[0:max_tag_len]
        tag_utf8 = tag_utf8.encode("utf-8")
        app_tag = self.app().tag
        posts = self.app().db.get_slice("%s-BlogTaggedPosts-%s" % (app_tag, tag_utf8), ColumnParent("Objects"), SlicePredicate(slice_range=SliceRange("", "", count=10000000)), ConsistencyLevel.QUORUM)
        render_posts = [post.column.name for post in posts]
        render_posts = self.objlist(BlogPostList, render_posts)
        render_posts.load(silent=True)
        vars = {
            "tag": cgi.escape(tag),
            "posts": render_posts.data(),
        }
        return self.call("web.response_template", "joyblog/tag.html", vars)

    def ext_search(self):
        req = self.req()
        if req.environ.get("REQUEST_METHOD") == "POST":
            self.call("web.redirect", "/search/%s" % urlencode(req.param("query").lower()))
        query = req.args.lower().strip()
        query_search = query
        if len(query_search) > max_word_len:
            query_search = query_search[0:max_word_len]
        m = re_wildcard.match(query_search)
        if m:
            word, letter = m.group(1, 2)
            next_letter = unichr(ord(letter) + 1)
            start = (word + letter).encode("utf-8")
            finish = (word + next_letter).encode("utf-8")
        else:
            start = (query_search + "//").encode("utf-8")
            finish = (query_search + "/=").encode("utf-8")
        app_tag = self.app().tag
        posts = self.app().db.get_slice("%s-BlogSearch" % app_tag, ColumnParent("Objects"), SlicePredicate(slice_range=SliceRange(start, finish, count=10000000)), ConsistencyLevel.QUORUM)
        render_posts = set()
        for post in posts:
            m = re_extract_uuid.match(post.column.name)
            if m:
                uuid = m.groups(1)[0]
                render_posts.add(uuid)
        render_posts = self.objlist(BlogPostList, list(render_posts))
        render_posts.load(silent=True)
        vars = {
            "query": cgi.escape(query),
            "posts": render_posts.data(),
        }
        return self.call("web.response_template", "joyblog/search.html", vars)

    def upload_if_large(self, data):
        if type(data) == unicode:
            data = data.encode("utf-8")
        if len(data) < max_inline_chunk_len:
            return data
        req = self.req()
        url = str("/storage/%s%s/%s" % (random.choice(alphabet), random.choice(alphabet), uuid4().hex))
        cnn = HTTPConnection()
        try:
            cnn.connect((req.host(), 80))
            try:
                request = HTTPRequest()
                request.method = "PUT"
                request.path = url
                request.host = req.host()
                request.body = data
                request.add_header("Content-type", "application/octet-stream")
                request.add_header("Content-length", len(data))
                response = cnn.perform(request)
                if response.status_code != 201:
                    self.error("Error storing object: %s", response.status)
                    # degradation
                    return ""
                return '<!--# include file="%s" -->' % url
            finally:
                cnn.close()
        except IOError as e:
            self.exception(e)
