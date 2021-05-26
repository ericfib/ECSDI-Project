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

AgenteExternoVuelos = Agent('AgenteExternoVuelos',
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


def vuelos(origin="Barcelona", destination="Paris"):
    global originAirport
    global destAirport

    g = Graph()

    # Carga el grafo RDF desde el fichero
    ontofile = gzip.open('../datos/FlightRoutes.ttl.gz')

    g.parse(ontofile, format='turtle')

    # Se decide el aeropuerto segun la ciudad de origen
    if origin == "Barcelona":
        originAirport="http://dbpedia.org/resource/Barcelona%E2%80%93El_Prat_Airport"
    elif origin == "Paris":
        originAirport="http://dbpedia.org/resource/Charles_de_Gaulle_Airport"
    elif origin == "Berlin":
        originAirport="http://dbpedia.org/resource/Berlin_Tegel_Airport"

    # Se decide el aeropuerto segun la ciudad de destino
    if destination == "Barcelona":
        destAirport="http://dbpedia.org/resource/Barcelona%E2%80%93El_Prat_Airport"
    elif destination == "Paris":
        destAirport="http://dbpedia.org/resource/Charles_de_Gaulle_Airport"
    elif destination == "Berlin":
        destAirport="http://dbpedia.org/resource/Berlin_Tegel_Airport"


    # Se buscan vuelos con el aeropuerto de origen y destino
    origenquery = """
        prefix tio:<http://purl.org/tio/ns#>
        Select ?vuelo ?fromall ?toall
        where {
            ?vuelo rdf:type tio:Flight .
            ?vuelo tio:to ?toall .
            ?vuelo tio:from ?fromall .
            ?vuelo tio:to <"""+destAirport+"""> .
            ?vuelo tio:from <"""+originAirport+"""> .
            }
        """

    qres = g.query(origenquery, initNs=dict(tio=TIO))
    print()
    for row in qres.result:
        print(row)
    return qres

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


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
