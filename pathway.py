
import httplib, urllib
import json
from py2neo import Graph
from flask import Flask, request, Response, jsonify
from caleydo_server.config import view as configview
import caleydo_server.websocket as ws

app = Flask(__name__)
websocket = ws.Socket(app)

class Config(object):
  def __init__(self, id, raw):
    self.id = id
    self.raw = raw
    sett = raw
    c = configview('pathfinder_graph')
    self.port = sett.get('port',c.port)
    self.host = sett.get('host', c.host)
    self.url = sett.get('url','http://'+self.host+':'+str(self.port))

    self.node_label = sett.get('node_label','_Network_Node')
    self.set_label = sett.get('set_label','_Set_Node')

    self.directions = sett.get('directions', dict(Edge='out',ConsistsOfEdge='both')) #both ConsistsOf for the reversal
    #by default inline ConsistsOfEdges
    self.inline = sett.get('inline', dict(inline='ConsistsOfEdge',undirectional=False,flag='_isSetEdge',aggregate='pathways',toaggregate='id',type='Edge'))

    self.client_conf = configview('pathfinder.uc').get(id)

config = None


def update_config(args):
  global config
  uc = args.get('uc','dblp')
  print args, uc
  config = Config(uc, configview('pathfinder_graph.uc').get(uc))

@app.before_request
def resolve_usecase():
  print 'before'
  update_config(request.args)

def resolve_db():
  graph = Graph(config.url + "/db/data/")
  return graph

@app.route('/config.json')
def get_config():
  return jsonify(config.client_conf)

def preform_search(s, limit=20, label = None, prop = 'name'):
  if label is None:
    label = config.node_label
  """ performs a search for a given search query
  :param s:
  :param limit: maximal number of results
  :return:
  """
  if len(s) < 2:  # too short search query
    return []

  import re
  # convert to reqex expression
  s = '.*' + re.escape(s.lower()).replace('\\','\\\\') + '.*'

  graph = resolve_db()

  query = 'MATCH (n:{0}) WHERE n.{1} =~ "(?i){2}" RETURN id(n) as id, n.{1} as name, n.id as nid ORDER BY n.{1} LIMIT {3}'.format(label, prop, s, limit)

  print query

  records = graph.cypher.execute(query)

  def convert(result):
    return dict(value=result.id, label=result.name, id=result.nid)

  return [convert(r) for r in records]


@app.route("/search")
def find_node():
  s = request.args.get('q', '')
  limit = request.args.get('limit', 20)
  label = request.args.get('label', config.node_label)
  prop = request.args.get('prop','name')

  results = preform_search(s, limit, label, prop)

  return jsonify(q=s, linit=limit, label=label, prop=prop, results=results)

def parse_incremental_json(text, on_chunk):
  """
  an incremental json parser, assumes a data stream like: [{...},{...},...]
  :param text: text to parse
  :param on_chunk: callback to call when a chunk was found
  :return: the not yet parsed text
  """
  act = 0
  open_braces = 0
  l = len(text)

  if l > 0 and (text[act] == '[' or text[act] == ','): #skip initial:
    act = 1

  start = act

  while act < l:
    c = text[act]
    if c == '{': #starting object
      open_braces += 1
    elif c == '}': #end object
      open_braces -= 1
      if open_braces == 0: #at the root
        on_chunk(json.loads(text[start:act+1]))
        start = act + 1
        act += 1
        if act < l and text[act] == ',': #skip separator
          start += 1
          act += 1
    act += 1
  if start == 0:
    return text
  return text[start:]


class SocketTask(object):
  def __init__(self, socket_ns):
    self.socket_ns = socket_ns

  def send_impl(self, t, msg):
    #print 'send'+t+str(msg)
    d = json.dumps(dict(type=t,data=msg))
    self.socket_ns.send(d)

class NodeAsyncTask(SocketTask):
  def __init__(self, q, socket_ns):
    super(NodeAsyncTask, self).__init__(socket_ns)
    self.q = q
    self.conn = httplib.HTTPConnection(config.host, config.port)
    from threading import Event
    self.shutdown = Event()
    self._sent_nodes = set()
    self._sent_relationships = set()
    self._graph = resolve_db()

  def abort(self):
    if self.shutdown.isSet():
      return
    self.conn.close()
    self.shutdown.set()

  def send_incremental(self, path):
    pass

  def send_start(self):
    pass

  def send_done(self):
   pass

  def send_node(self, node):
    nid = node['id']
    if nid in self._sent_nodes:
      return #already sent during this query
    print 'send_node '+str(nid)
    try:
      gnode = self._graph.node(nid)
      self.send_impl('new_node', dict(id=nid,labels=map(str,gnode.labels),properties=gnode.properties))
    except ValueError:
      pass
      self.send_impl('new_node', node)
    self._sent_nodes.add(nid)

  def send_relationship(self, rel):
    rid = rel['id']
    if rid < 0: #its a fake one
      return
    if rid in self._sent_relationships:
      return #already sent during this query
    print 'send_relationship '+str(rid)
    base = rel.copy()
    try:
      grel = self._graph.relationship(rid)
      base['properties'] = grel.properties
    except ValueError:
      pass
    self.send_impl('new_relationship', base)
    self._sent_relationships.add(rid)

  def to_url(self, args):
    return '/caleydo/kShortestPaths/?{0}'.format(args)

  def run(self):
    headers = {
      'Content-type': 'application/json',
      'Accept': 'application/json'
      }
    args = { k : json.dumps(v) if isinstance(v, dict) else v for k,v in self.q.iteritems()}
    print args
    args = urllib.urlencode(args)
    url = self.to_url(args)
    print url
    body = ''
    self.conn.request('GET', url, body, headers)
    self.send_start()
    self.stream()

  def stream(self):
    response = self.conn.getresponse()
    if self.shutdown.isSet():
      print 'aborted early'
      return
    content_length = int(response.getheader('Content-Length', '0'))
    print 'waiting for response: '+str(content_length)
    # Read data until we've read Content-Length bytes or the socket is closed
    l = 0
    data = ''
    while not self.shutdown.isSet() and (l < content_length or content_length == 0):
      s = response.read(4)  #read at most 32 byte
      if not s or self.shutdown.isSet():
        break
      data += s
      l += len(s)
      data = parse_incremental_json(data,self.send_incremental)

    if self.shutdown.isSet():
      print 'aborted'
      return

    parse_incremental_json(data,self.send_incremental)
    # print response.status, response.reason
    #data = response.read()
    self.send_done()

    self.conn.close()
    self.shutdown.set()
    print 'end'

class Query(NodeAsyncTask):
  def __init__(self, q, socket_ns):
    super(Query, self).__init__(q, socket_ns)
    self.paths = []

  def send_incremental(self, path):
    if self.shutdown.isSet():
      return
    self.paths.append(path)
    #check for all nodes in the path and load and send their missing data
    for n in path['nodes']:
      self.send_node(n)
    for e in path['edges']:
      self.send_relationship(e)
    print 'sending path ',len(self.paths)
    self.send_impl('query_path',dict(query=self.q,path=path,i=len(self.paths)))

  def send_start(self):
    self.send_impl('query_start',dict(query=self.q))

  def send_done(self):
    print 'sending done ',len(self.paths)
    self.send_impl('query_done',dict(query=self.q)) #,paths=self.paths))

  def to_url(self, args):
    return '/caleydo/kShortestPaths/?{0}'.format(args)


class Neighbors(NodeAsyncTask):
  def __init__(self, q, socket_ws):
    super(Neighbors, self).__init__(q, socket_ws)
    self.node = q['node']
    self.neighbors = []

  def send_incremental(self, neighbor):
    if self.shutdown.isSet():
      return
    self.neighbors.append(neighbor)
    self.send_node(neighbor)
    print 'sending neighbor ',len(self.neighbors)
    self.send_impl('neighbor_neighbor',dict(node=self.node,neighbor=neighbor,i=len(self.neighbors)))

  def send_start(self):
    self.send_impl('neighbor_start',dict(node=self.node))

  def send_done(self):
    print 'sending done ',len(self.neighbors)
    self.send_impl('neighbor_done',dict(node=self.node,neighbors=self.neighbors)) #,paths=self.paths))

  def to_url(self, args):
    return '/caleydo/kShortestPaths/neighborsOf/{0}?{1}'.format(str(self.node),args)


current_query = None

@websocket.route('/query')
def websocket_query(ws):
  global current_query
  while True:
    msg = ws.receive()
    if msg is None:
      continue
    print msg
    data = json.loads(msg)
    t = data['type']
    payload = data['data']

    update_config(payload)

    if current_query is not None:
      current_query.abort()
    if t == 'query':
      current_query = Query(to_query(payload), ws)
    elif t == 'neighbor':
      current_query = Neighbors(to_neighbors_query(payload), ws)
    current_query.run()

def to_query(msg):
  """
  converts the given message to kShortestPath query arguments
  :param msg:
  :return:
  """
  k = msg.get('k',1) #number of paths
  max_depth = msg.get('maxDepth', 10) #max length
  just_network = msg.get('just_network_edges', False)
  q = msg['query']
  print q

  args = {
    'k': k,
    'maxDepth': max_depth,
  }

  min_length = msg.get('minLength', 0)
  if min_length > 0:
    args['minLength'] = min_length

  constraint = {'context': 'node', '$contains' : config.node_label}

  #TODO generate from config
  directions = dict(config.directions)
  inline = config.inline

  if q is not None:
    constraint = {'$and' : [constraint, q] }

  args['constraints'] = dict(c=constraint,dir=directions,inline=inline,acyclic=True)
  if just_network:
    del directions[inline['inline']]
    c = args['constraints']
    del c['inline']

  return args

def to_neighbors_query(msg):
  """
  based on the message converts to kShortestPaths args
  :param msg: the incoming message, supporting 'just_network_edges' and 'node' attribute
  :return:
  """
  just_network = msg.get('just_network_edges', False)
  node = int(msg.get('node'))
  args = {
    'node': node
  }
  #TODO generate from config
  directions = dict(config.directions)
  inline = config.inline
  args['constraints'] = dict(dir=directions,inline=inline,acyclic=True)
  if just_network:
    del directions[inline['inline']]
    c = args['constraints']
    del c['inline']

  return args


@app.route("/summary")
def get_graph_summary():
  """
  api for getting a graph summary (nodes, edge, set count)
  :return:
  """
  graph = resolve_db()

  def compute():
    query = 'MATCH (n:{0}) RETURN COUNT(n) AS nodes'.format(config.node_label)
    records = graph.cypher.execute(query)
    num_nodes = records[0].nodes

    query = 'MATCH (n1:{0})-[e]->(n2:{0}) RETURN COUNT(e) AS edges'.format(config.node_label)
    records = graph.cypher.execute(query)
    num_edges = records[0].edges

    query = 'MATCH (n:{0}) RETURN COUNT(n) AS sets'.format(config.set_label)
    records = graph.cypher.execute(query)
    num_sets = records[0].sets

    yield json.dumps(dict(Nodes=num_nodes,Edges=num_edges,Sets=num_sets))

  return Response(compute(), mimetype='application/json')


def create_get_sets_query(sets):
  # convert to query form
  set_queries = ['"{0}"'.format(s) for s in sets]

  #create the query
  return 'MATCH (n:{1}) WHERE n.id in [{0}] RETURN n, n.id as id, id(n) as uid'.format(', '.join(set_queries), config.set_label)


@app.route("/setinfo")
def get_set_info():
  """
  delivers set information for a given list of set ids
  :return:
  """
  sets = request.args.getlist('sets[]')
  print sets
  if len(sets) == 0:
    return jsonify()

  graph = resolve_db()

  def compute():
    query = create_get_sets_query(sets)
    records = graph.cypher.execute(query)

    response = dict()

    for record in records:
      node = record.n

      response[record.id] = {
        'id': record.uid,
        'labels': map(str, node.labels),
        'properties': node.properties
      }
    print 'sent setinfo for ',sets
    yield json.dumps(response)

  return Response(compute(), mimetype='application/json')

def create():
  """
   entry point of this plugin
  """
  app.debug = True
  return app


if __name__ == '__main__':
  app.debug = True
  app.run(host='0.0.0.0')
