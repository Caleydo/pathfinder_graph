from py2neo import Graph

graph = Graph("http://192.168.50.52:7474/db/data/")

graph.cypher.execute("MATCH (n:_Network_Node)<--(s:_Set_Node)-->(x:_Network_Node) WITH n, count(DISTINCT x) as degree SET n.degree = degree")



# for record in res:
#     print record;





