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
import json
from multiprocessing import Process, Queue
import socket
import os

import argparse
from pprint import PrettyPrinter
import random

from rdflib import Namespace, Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF

from flask import Flask, request
from dotenv import load_dotenv
from amadeus import Client, ResponseError

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, register_agent, get_message_properties, get_agent_info
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ECSDI, ACL

__author__ = 'javier'

# Definimos los parametros de la linea de comandos
from AgentUtil.Util import gethostname

parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor esta abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--verbose', help="Genera un log de la comunicacion del servidor web", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()
# Configuration stuff
if args.port is None:
    port = 9012
else:
    port = args.port

if args.open:
    hostname = '0.0.0.0'
    hostaddr = gethostname()
else:
    hostaddr = hostname = socket.gethostname()

print('DS Hostname =', hostaddr)

if args.dport is None:
    dport = 9013
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost
# Directory Service Graph
dsgraph = Graph()
dsgraph.bind('acl', ACL)
dsgraph.bind('ecsdi', ECSDI)

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


# Datos del Agente


AgenteExternoVuelosAmadeus = Agent('AgenteExternoVuelosAmadeus',
                                         agn.AgenteExternoVuelosAmadeus,
                                         'http://%s:%d/comm' % (hostname, port),
                                         'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)

# APIs
load_dotenv()
AMADEUS_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_SECRET = os.getenv("AMADEUS_API_SECRET")
amadeus = Client(client_id=AMADEUS_KEY, client_secret=AMADEUS_SECRET)
ppr = PrettyPrinter(indent=4)

def buscar_vuelos_externos():
    # DATE HA DE SER STRING YYYY-MM-DD
    # CALL
    grafo_vuelos = Graph()
    grafo_vuelos.bind('ECSDI', ECSDI)

    content = ECSDI['Respuesta_Vuelos' + str(get_count())]

    flightsbcnprs = amadeus.shopping.flight_offers_search.get(
        originLocationCode='BCN',
        destinationLocationCode='PAR',
        departureDate='2021-07-01',
        adults=1)
    response = flightsbcnprs.data

    if flightsbcnprs.status_code != 200:
        logger.info('Error al buscar vuelos: ' + flightsbcnprs.status_code)
    else:

        for flight in response:
            for f in flight["itineraries"]:
                for x in f["segments"]:
                    vuelo_origen = ECSDI['vuelo' + str(get_count())]
                    compania = ECSDI['proveedor_de_vuelos' + str(get_count())]
                    origen = ECSDI['aeropuerto' + str(get_count())]
                    destino = ECSDI['aeropuerto' + str(get_count())]

                    # Compania
                    grafo_vuelos.add((compania, RDF.type, ECSDI.compania))
                    grafo_vuelos.add((compania, ECSDI.nombre, Literal("Ryanair")))

                    # Llega a
                    grafo_vuelos.add((destino, RDF.type, ECSDI.aeropuerto))
                    grafo_vuelos.add((destino, ECSDI.nombre, Literal("Charles de Gaulle Airport")))


                    # Sale_de
                    grafo_vuelos.add((origen, RDF.type, ECSDI.aeropuerto))
                    grafo_vuelos.add((origen, ECSDI.nombre, Literal("Barcelona El Prat Airport")))

                    importe = random.randint(30, 350)

                    # Vuelo origen
                    grafo_vuelos.add((vuelo_origen, RDF.type, ECSDI.vuelo))
                    grafo_vuelos.add((vuelo_origen, ECSDI.tiene_como_aeropuerto_origen, URIRef(origen)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.tiene_como_aeropuerto_destino, URIRef(destino)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.importe, Literal(importe)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.es_ofrecido_por, URIRef(compania)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.fecha_inicial, Literal(x["departure"]["at"])))
                    grafo_vuelos.add((vuelo_origen, ECSDI.fecha_final, Literal(x["arrival"]["at"])))

    flightsprsbcn = amadeus.shopping.flight_offers_search.get(
        originLocationCode='PAR',
        destinationLocationCode='BCN',
        departureDate='2021-07-01',
        adults=1)
    response = flightsprsbcn.data

    if flightsprsbcn.status_code != 200:
        logger.info('Error al buscar vuelos: ' + flightsprsbcn.status_code)
    else:

        for flight in response:
            for f in flight["itineraries"]:
                for x in f["segments"]:
                    vuelo_origen = ECSDI['vuelo' + str(get_count())]
                    compania = ECSDI['proveedor_de_vuelos' + str(get_count())]
                    origen = ECSDI['aeropuerto' + str(get_count())]
                    destino = ECSDI['aeropuerto' + str(get_count())]

                    # Compania
                    grafo_vuelos.add((compania, RDF.type, ECSDI.compania))
                    grafo_vuelos.add((compania, ECSDI.nombre, Literal("Ryanair")))

                    # Llega a
                    grafo_vuelos.add((destino, RDF.type, ECSDI.aeropuerto))
                    grafo_vuelos.add((destino, ECSDI.nombre, Literal("Barcelona El Prat Airport")))

                    # Sale_de
                    grafo_vuelos.add((origen, RDF.type, ECSDI.aeropuerto))
                    grafo_vuelos.add((origen, ECSDI.nombre, Literal("Charles de Gaulle Airport")))

                    importe = random.randint(30, 350)

                    # Vuelo origen
                    grafo_vuelos.add((vuelo_origen, RDF.type, ECSDI.vuelo))
                    grafo_vuelos.add((vuelo_origen, ECSDI.tiene_como_aeropuerto_origen, URIRef(origen)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.tiene_como_aeropuerto_destino, URIRef(destino)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.importe, Literal(importe)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.es_ofrecido_por, URIRef(compania)))
                    grafo_vuelos.add((vuelo_origen, ECSDI.fecha_inicial, Literal(x["departure"]["at"])))
                    grafo_vuelos.add((vuelo_origen, ECSDI.fecha_final, Literal(x["arrival"]["at"])))

    return grafo_vuelos


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    print("PETICION DE VUELOS RECIBIDA")

    message = request.args['content']

    grafo_mensaje_entrante = Graph()
    grespuesta = Graph()
    grafo_mensaje_entrante.parse(data=message)

    msg = get_message_properties(grafo_mensaje_entrante)

    if msg is None:
        print("baia")
        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteExternoVuelosAmadeus.uri,
                                   msgcnt=mss_cnt)

    else:
        # obtener performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteExternoVuelosAmadeus.uri,
                                       msgcnt=mss_cnt)

        else:
            if 'content' in msg:
                content = msg['content']
                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)

                # hacer lo que pide la accion
                if accion == ECSDI.Peticion_Vuelos:
                    grespuesta = buscar_vuelos_externos()

                    grespuesta = build_message(grespuesta, ACL['inform-'], sender=AgenteExternoVuelosAmadeus.uri,
                                               msgcnt=mss_cnt, receiver=msg['sender'])
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'],
                                               sender=AgenteExternoVuelosAmadeus.uri,
                                               msgcnt=mss_cnt)
            else:
                grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteExternoVuelosAmadeus.uri,
                                           msgcnt=mss_cnt)

    serialize = grespuesta.serialize(format='xml')
    return serialize


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente
    """
    global cola1
    cola1.put(0)

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteExternoVuelosAmadeus, DirectoryAgent, AgenteExternoVuelosAmadeus.uri, get_count())
    return gr


def agentbehavior1():
    """
    Un comportamiento del agente
    :return:
    """
    # Registramos el agente
    gr = register_message()
    #buscar_vuelos_externos()



if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
