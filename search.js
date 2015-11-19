/**
 * Created by sam on 13.03.2015.
 */
define(['../caleydo_core/main', '../caleydo_core/event', '../caleydo_core/ajax'],function(C, events, ajax) {
  'use strict';

  function ServerSearch() {
    events.EventHandler.call(this);
    this._socket = null;
    this._initialMessage = [];

    this.search_cache = {};
    this._nodelookup = {};
    this._rellookup = {};
  }
  C.extendClass(ServerSearch, events.EventHandler);

  function uc() {
    return C.hash.getProp('uc', C.param.getProp('uc', 'dblp'));
  }

  ServerSearch.prototype.resolveConfig = function() {
    return ajax.getAPIJSON('/pathway/config.json?uc='+uc());
  };

  ServerSearch.prototype.extendPath = function(path) {
    var that = this;
    return {
      nodes: path.nodes.map(function(n) { return that.extendNode(n); }),
      edges: path.edges.map(function(n) { return that.extendRel(n); })
    }
  };
  ServerSearch.prototype.extendNode = function(node) {
    if (node.id in this._nodelookup) {
      return this._nodelookup[node.id];
    }
    return node;
  };
  ServerSearch.prototype.extendRel = function(node) {
    if (node.id in this._rellookup) {
      return this._rellookup[node.id];
    }
    return node;
  };

  ServerSearch.prototype.onMessage = function(msg) {
    var node;
    if (msg.type === 'query_path') {
      msg.data.path = this.extendPath(msg.data.path);
    } else if (msg.type === 'neighbor_neighbor') {
      msg.data.neighbor = this.extendNode(msg.data.neighbor);
    } else if (msg.type === 'found') {
      msg.data.node = this.extendNode(msg.data.node);
    } else if (msg.type === 'new_node') {
      node = msg.data;
      this._nodelookup[node.id] = node;
      return;
    } else if (msg.type === 'new_relationship') {
      node = msg.data;
      this._rellookup[node.id] = node;
      return;
    }
    this.fire(msg.type, msg.data);
  };
  function asMessage(type, msg) {
    msg.uc = uc();
    return JSON.stringify({type: type, data: msg});
  }
  ServerSearch.prototype.send = function(type, msg) {
    var that = this;
    if (!this._socket) {
      that._initialMessage.push(asMessage(type,msg));

      var s = new WebSocket('ws://' + document.domain + ':' + location.port + '/api/pathway/query');
      that.fire('ws_open');
      s.onmessage = function (msg) {
        //console.log('got message', msg);
        that.onMessage(JSON.parse(msg.data));
      };
      s.onopen = function() {
        that._socket = s;
        that._initialMessage.forEach(function(msg) {
          s.send(msg);
        });
        that._initialMessage = [];
        that.fire('ws_ready');
      };
      s.onclose = function () {
        that._socket = null; //clear socket upon close
        that.fire('ws_closed');
      };

    } else if (this._socket.readyState !== WebSocket.OPEN) {
      //not yet open cache it
      that._initialMessage.push(asMessage(type, msg));
    } else {
      //send directly
      this._socket.send(asMessage(type, msg));
    }
  };

  ServerSearch.prototype.loadQuery = function(query, k, maxDepth, just_network_edges, minLength) {
    var msg = {
      k : k || 10,
      maxDepth : maxDepth || 10,
      query : query ? query.serialize() : null,
      just_network_edges : just_network_edges || false,
      minLength : minLength || 0
    };
    this.send('query', msg);
  };

  /**
   * finds a set of nodes given a query
   * @param query
   * @param k
   */
  ServerSearch.prototype.find = function(query, k) {
    var msg = {
      k : k || 10,
      query : query ? query.serialize() : null
    };
    this.send('find', msg);
  };

  /**
   *
   * @param node_id
   * @param just_network_edges boolean whether just network edges should be considered
   * @param tag additional tag to transfer, identifying the query
   */
  ServerSearch.prototype.loadNeighbors = function(node_id, just_network_edges, tag) {
    var msg = {
      node : node_id,
      just_network_edges : just_network_edges || false
    };
    if (tag) {
      msg.tag = tag;
    }
    this.send('neighbor', msg);
  };

  ServerSearch.prototype.clearSearchCache = function() {
    this.search_cache = {};
  };

  /**
   * server search for auto completion
   * @param query the query to search
   * @param prop the property to look in
   * @param nodeType the node type to look in
   */
  ServerSearch.prototype.search = function(query, prop, nodeType) {
    prop = prop || 'name';
    nodeType = nodeType || '_Network_Node';
    var cache = this.search_cache[nodeType+'.'+prop];
    if (!cache) {
      cache = {};
      this.search_cache[nodeType+'.'+prop] = cache;
    }
    if (cache && query in cache) {
      return Promise.resolve(cache[query]);
    }
    return ajax.getAPIJSON('/pathway/search', {q: query, prop: prop, label: nodeType, uc : uc()}).then(function (data) {
      cache[query] = data.results;
      return data.results;
    });
  };

  return new ServerSearch();
});
