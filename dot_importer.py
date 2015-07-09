import os
from os import listdir
from os.path import isfile, join
import csv
import argparse
import itertools

from import_utils import GraphImporter

parser = argparse.ArgumentParser(description='DOT Importer')
parser.add_argument('--db', default="http://192.168.56.1:7474/db/data/")
parser.add_argument('--data_dir', '-d', default='/vagrant_data/', help='data directory')
parser.add_argument('--undirected', action='store_true', help='create undirected graph')
parser.add_argument('--sets', action='store_true', help='create set edges')
parser.add_argument('--clear', action='store_true', help='clear the graph')
parser.add_argument('--commitEvery', type=int, default=100, help='commit every x steps')

args = parser.parse_args()

importer = GraphImporter(args.db, args.commitEvery)

#extras for creating the fields
#MATCH (a:Disease)-[:`ConsistsOfEdge`]->(b) SET b.disease = []
#MATCH (a:Disease)-[:`ConsistsOfEdge`]->(b) SET b.disease = b.disease + a.id
#MATCH (a:Pathways)-[:`ConsistsOfEdge`]->(b) SET b.pathways = []
#MATCH (a:Pathways)-[:`ConsistsOfEdge`]->(b) SET b.pathways = b.pathways + a.id
#MATCH (a:Phenotype)-[:`ConsistsOfEdge`]->(b) SET b.phenotypes = []
#MATCH (a:Phenotype)-[:`ConsistsOfEdge`]->(b) SET b.phenotypes = b.phenotypes + a.id

def import_pathway():
  with open('collections.broad.apr18.tsv','r') as f:
    for row in csv.reader(f, delimiter='\t'):
      #print row
	  id = row[0]
	  geneids = row[3].split(';')
	  #print id, geneids
	  importer.add_node(['_Set_Node','Pathway'], id, dict(name=id))
	  for geneid in geneids:
		try:
		  q = u'MATCH (source:Pathway {{id:"{0}"}}), (target:_Network_Node {{geneids:"{1}"}}) CREATE source-[el:ConsistsOfEdge]->target'.format(id, geneid)
		  importer.append(q)
		except:
		  print 'cant add pathway edge: ',id,geneid

  importer.finish()

def import_pheno():
  with open('mousePhen.humanGenes.tsv','r') as f:
    for row in (r for i, r in enumerate(csv.reader(f, delimiter='\t')) if i > 0):
      #print row
	  geneid = row[0]
	  pheno = row[5]
	  pheno_label = row[6]
	  #print id, geneids
	  importer.add_node(['_Set_Node','Phenotype'], pheno, dict(name=pheno_label))
	  try:
		q = u'MATCH (source:Phenotype {{id:"{0}"}}), (target:_Network_Node {{geneids:"{1}"}}) CREATE source-[el:ConsistsOfEdge]->target'.format(pheno, geneid)
		importer.append(q)
	  except:
		  print 'cant add pheno edge: ',pheno,geneid	

def import_disease():
  with open('humandisease.txt','r') as f:
    for row in (r for i, r in enumerate(csv.reader(f, delimiter='\t')) if i > 0):
      #print row
	  geneid = row[0]
	  disease = row[2]
	  disease_label = row[3]
	  #print id, geneids
	  importer.add_node(['_Set_Node','Disease'], disease, dict(name=disease_label))
	  importer.append(u'MATCH (source:Disease {{id:"{0}"}}), (target:_Network_Node {{geneids:"{1}"}}) CREATE source-[el:ConsistsOfEdge]->target'.format(disease, geneid))

  importer.finish()

if __name__ == '__main__':
  import_pathway()
  import_pheno()
