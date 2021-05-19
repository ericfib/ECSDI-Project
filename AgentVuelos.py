# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""
import gzip

from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph
from flask import Flask

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.OntoNamespaces import TIO

__author__ = 'javier'

# Configuration stuff
hostname = socket.gethostname()
port = 9010

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgenteVuelos = Agent('AgenteVuelos',
                       agn.AgenteSimple,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    pass


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def vuelos():
    g = Graph()

    # Carga el grafo RDF desde el fichero
    ontofile = gzip.open('FlightRoutes.ttl.gz')
    g.parse(ontofile, format='turtle')

    # Consulta al grafo los aeropuertos dentro de la caja definida por las coordenadas
    qres = g.query(
        """
        prefix tio:<http://purl.org/tio/ns#>
        prefix geo:<http://www.w3.org/2003/01/geo/wgs84_pos#>
        prefix dbp:<http://dbpedia.org/ontology/>
        Select ?f
        where {
            ?f rdf:type dbp:Airport .
            ?f geo:lat ?lat .
            ?f geo:long ?lon .
            Filter ( ?lat < "41.7"^^xsd:float &&
                     ?lat > "41.0"^^xsd:float &&
                     ?lon < "2.3"^^xsd:float &&
                     ?lon > "2.0"^^xsd:float)
            }
        LIMIT 30
        """,
        initNs=dict(tio=TIO))

    # Recorre los resultados y se queda con el ultimo
    for r in qres:
        ap = r['f']


    # Consulta todos los vuelos que conectan con ese aeropuerto
    destinoquery = """
        prefix tio:<http://purl.org/tio/ns#>
        Select *
        where {
            ?f rdf:type tio:Flight.
            ?f tio:flightNo ?fn.
            ?f tio:to <%s>.
            ?f tio:from ?t.
            ?f tio:operatedBy ?o.
            }
        LIMIT 3
        """ % ap
    
    destinores = g.query(destinoquery, initNs=dict(tio=TIO))
    

    origenquery = """
        prefix tio:<http://purl.org/tio/ns#>
        Select *
        where {
            ?vuelo rdf:type tio:Flight .
            ?vuelo tio:to ?allTo .
            ?vuelo tio:from <%s> .    
            }
        LIMIT 3
        """ % ap

    origenres = g.query(origenquery, initNs=dict(tio=TIO))
   
    # Imprime los resultados
    print()
    print("VUELOS DESDE BARCELONA")
    for row in origenres:
        print("EL VUELO " , row['vuelo'])
        print("SALE DESDE " , ap)
        print("Y VA HASTA " , row['allTo'])
        print()

    print()
    print("VUELOS HACIA BARCELONA")
    for row in destinores:
        print("EL VUELO " , row['fn'])
        print("SALE DESDE " , row['t'])
        print("Y VA HASTA " , ap)
        print()

def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """
    vuelos()


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
