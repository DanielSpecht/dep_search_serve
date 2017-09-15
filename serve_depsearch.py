#!/usr/bin/env python3

# This code can run in both Python 2.7+ and 3.3+

from flask import Flask, Markup
import flask
import json
import requests
import six
import six.moves.urllib as urllib  # use six for python 2.x compatibility
import traceback
import re
import json

DEBUGMODE=False
try:
    from config_local import * #use to override the constants above if you like
except ImportError:
    pass #no config_local

app = Flask("dep_search_webgui")

def get_bosque_ids(src):
    ids = []

    for line in src:
        if line.startswith(u"#") and "sent_id" in line:
            id = re.match(r'.*sent_id.*=(.*)',line)
            id = id.group(1)
            id = id.strip()
            ids.append(id)
            print id

    return ids

def remove_added_comments(lines):
    # Leave only the original comments of the sentence
    # Comments that strt with the strings listed must be removed
    indicators = [u"# visual-style", u"# context-hit",u"# context",u"# hittoken",u"# db-name",u"# graph id"]

    def remove_line(line):
        for indicator in indicators:
            if line.startswith(indicator):
                return True #must be removed
        return False

    return [x for x in lines if not remove_line(x)]

def get_edition_tool_links(sent_ids,dep_search_ids,tokens_comments_json):
    links = []

    for i in range(0,len(sent_ids)):
        links.append(DEP_EDITION_TOOL+"/table"+
            "?tokens="+tokens_comments_json[i]["TOKENS"] +
            "&comments="+tokens_comments_json[i]["COMMENTS"]+
            "&sentence_id="+sent_ids[i]+
            "&db_id="+dep_search_ids[i])

    return links

def get_tokens_and_comments_json(src):
    lines = remove_added_comments(src)
    sentences = []
    
    sentence_dict = {}
    sentence_dict["COMMENTS"] = []
    sentence_dict["TOKENS"] = []

    for line in lines:
        if line==u"":
            
            sentences.append({"TOKENS":json.dumps(sentence_dict["TOKENS"]),
                              "COMMENTS":json.dumps(sentence_dict["COMMENTS"])})

            sentence_dict = {}
            sentence_dict["COMMENTS"] = []
            sentence_dict["TOKENS"] = []

        elif line.startswith(u"#"):
            sentence_dict["COMMENTS"].append(line[1:])

        else:
            columns = line.split("\t")
            sentence_dict["TOKENS"].append({"ID":columns[0],
                                            "FORM":columns[1],
                                            "LEMMA":columns[2],
                                            "UPOSTAG":columns[3],
                                            "XPOSTAG":columns[4],
                                            "FEATS":columns[5],
                                            "HEAD":columns[6],
                                            "DEPREL":columns[7],
                                            "DEPS":columns[8],
                                            "MISC":columns[9]})
    return sentences

def get_dep_search_ids(src):
    ids = []
    
    i = 0
    while i < len(src)-1:
        
        if src[i].startswith(u"#") and "db-name" in src[i]:
            i=i+1

        elif src[i].startswith(u"#") and "graph id:" in src[i]:
            id = re.match(r'.*graph id:(.*)',src[i])
            id = id.group(1)
            id = id.strip()
            ids.append(id)
        
        i=i+1

    return ids

def yield_trees(src):
    current_tree=[]
    current_comment=[]
    current_context=u""
    tree_id = u""

    for line in src:
        if line.startswith(u"# visual-style"):
            current_tree.append(line)
        elif line.startswith(u"# URL:"):
            current_comment.append(Markup(u'<a href="{link}">{link}</a>'.format(link=line.split(u":",1)[1].strip())))
        elif line.startswith(u"# context-hit"):
            current_context+=(u' <b>{sent}</b>'.format(sent=flask.escape(line.split(u":",1)[1].strip())))
        elif line.startswith(u"# context"):
            current_context+=(u' {sent}'.format(sent=flask.escape(line.split(u":",1)[1].strip())))
        elif line.startswith(u"# hittoken"):
            current_tree.append(line)
        elif not line.startswith(u"#"):
            current_tree.append(line)

        if line==u"":
            current_comment.append(Markup(current_context))
            y = u"\n".join(current_tree), current_comment
            yield y
            current_comment=[]
            current_tree=[]
            current_context=u""

class Query:

    @classmethod
    def from_formdata(cls,fdata):
        query=fdata[u'query'].strip()
        hits_per_page=int(fdata[u'hits_per_page'])
        treeset=fdata[u'treeset'].strip()
        if fdata.get(u'case'):
            case_sensitive=True
        else:
            case_sensitive=False
        return(cls(treeset,query,case_sensitive,hits_per_page))

    @classmethod
    def from_get_request(cls,args):
        query=args[u"search"]
        treeset=args[u"db"]
        case_sensitive=True
        hits_per_page=10
        return(cls(treeset,query,case_sensitive,hits_per_page))

    def __init__(self,treeset,query,case_sensitive,hits_per_page):
        self.treeset,self.query,self.case_sensitive,self.hits_per_page=treeset,query,case_sensitive,hits_per_page

    def query_link(self,url=u"",treeset=None):
        if treeset is None:
            treeset=self.treeset
        if six.PY2:
            return url+u"query?search={query}&db={treeset}&case_sensitive={case_sensitive}&hits_per_page={hits_per_page}".format(query=unicode(urllib.parse.quote(self.query.encode("utf-8")),"utf-8"),treeset=treeset,case_sensitive=self.case_sensitive,hits_per_page=self.hits_per_page)
        else:
            return url+u"query?search={query}&db={treeset}&case_sensitive={case_sensitive}&hits_per_page={hits_per_page}".format(query=urllib.parse.quote(self.query),treeset=treeset,case_sensitive=self.case_sensitive,hits_per_page=self.hits_per_page)

    def download_link(self,url=""):
        if six.PY2:
            return DEP_SEARCH_WEBAPI+u"?search={query}&db={treeset}&case={case_sensitive}&retmax=5000&dl".format(query=unicode(urllib.parse.quote(self.query.encode("utf-8")),"utf-8"),treeset=self.treeset,case_sensitive=self.case_sensitive)
        else:
            return DEP_SEARCH_WEBAPI+u"?search={query}&db={treeset}&case={case_sensitive}&retmax=5000&dl".format(query=urllib.parse.quote(self.query),treeset=self.treeset,case_sensitive=self.case_sensitive)
        
@app.route(u"/")
def index():
    r=requests.get(DEP_SEARCH_WEBAPI+u"/metadata") #Ask about the available corpora
    metadata=json.loads(r.text)
    return flask.render_template(u"index_template.html",corpus_groups=metadata[u"corpus_groups"])

#This is what JS+AJAX call
@app.route(u'/query',methods=[u"POST"])
def query_post():
    try:
        sources=[]
        q=Query.from_formdata(flask.request.form)
        r=requests.get(DEP_SEARCH_WEBAPI,params={u"db":q.treeset, u"case":q.case_sensitive, u"context":3, u"search":q.query, u"retmax":q.hits_per_page})
        if r.text.startswith(u"# Error in query"):
            ret = flask.render_template(u"query_error.html", err=r.text)
        elif not r.text.strip():
            ret = flask.render_template(u"empty_result.html")
        else:
            lines=r.text.splitlines()

            if lines[0].startswith("# SourceStats : "):
                sources=json.loads(lines[0].split(" : ",1)[1])

                trees = yield_trees(lines[1:])
                bosque_ids = get_bosque_ids(lines[1:])
                db_ids = get_dep_search_ids(lines[1:])
                sentences_json=get_tokens_and_comments_json(lines[1:])
                editor_links=get_edition_tool_links(bosque_ids,db_ids,sentences_json)

                ret=flask.render_template(  u"result_tbl.html",
                                            trees=trees,
                                            bosque_ids = bosque_ids,
                                            db_ids = db_ids,
                                            sentences_json=sentences_json,
                                            editor_links=editor_links)
                
                #print get_sentences_json(lines[1:])

            else:
                
                trees = yield_trees(lines)
                bosque_ids = get_bosque_ids(lines)
                db_ids = get_dep_search_ids(lines)
                sentences_json=get_tokens_and_comments_json(lines)
                editor_links=get_edition_tool_links(bosque_ids,db_ids,sentences_json)

                ret=flask.render_template(  u"result_tbl.html",
                                            trees=trees,
                                            bosque_ids = bosque_ids,
                                            db_ids = db_ids,
                                            sentences_json=sentences_json,
                                            editor_links=editor_links)
                
                #print get_sentences_json(lines)

        links=['<a href="{link}">{src}</a>'.format(link=q.query_link(treeset=src),src=src) for src in sources]
        return json.dumps({u'ret':ret,u'source_links':u' '.join(links),u'query_link':q.query_link(),u'download_link':q.download_link()});

    except:
        traceback.print_exc()
        

#This is what GET calls
#We return the index and prefill a script call to launch the form for us
@app.route(u'/query',methods=[u"GET"])
def query_get():
    r=requests.get(DEP_SEARCH_WEBAPI+u"/metadata") #Ask about the available corpora
    metadata=json.loads(r.text)

    if u"db" not in flask.request.args or u"search" not in flask.request.args:
        return flask.render_template(u"get_help.html",corpus_groups=metadata[u"corpus_groups"])

    q=Query.from_get_request(flask.request.args)
    run_request=Markup(u'dsearch_simulate_form("{treeset}","{query}","{case_sensitive}","{max_hits}");'.format(treeset=q.treeset,query=q.query.replace(u'"',u'\\"'),case_sensitive=q.case_sensitive,max_hits=q.hits_per_page))
    return flask.render_template(u"index_template.html",corpus_groups=metadata[u"corpus_groups"],run_request=run_request)

if __name__ == u'__main__':
    app.run(debug=DEBUGMODE,host='0.0.0.0', port=5000)
    r=requests.get(DEP_SEARCH_WEBAPI+u"/metadata") #Ask about the available corpora
    metadata=json.loads(r.text)

