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
    port = 9001
else:
    port = args.port

if args.open:
    hostname = '0.0.0.0'
    hostaddr = gethostname()
else:
    hostaddr = hostname = socket.gethostname()

print('DS Hostname =', hostaddr)

if args.dport is None:
    dport = 9011
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


AgenteAlojamientosExternoAmadeus = Agent('AgenteAlojamientosExternoAmadeus',
                                         agn.AgenteAlojamientosExternoAmadeus,
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


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    print("PETICION DE ALOJAMIENTOS RECIBIDA")

    message = request.args['content']

    grafo_mensaje_entrante = Graph()
    grespuesta = Graph()
    grafo_mensaje_entrante.parse(data=message)

    msg = get_message_properties(grafo_mensaje_entrante)

    if msg is None:
        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                   msgcnt=mss_cnt)

    else:
        # obtener performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                       msgcnt=mss_cnt)

        else:
            if 'content' in msg:
                content = msg['content']
                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)

                # hacer lo que pide la accion
                if accion == ECSDI.Peticion_Alojamientos:
                    grespuesta = buscar_alojamientos_externos()

                    grespuesta = build_message(grespuesta, ACL['inform-'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                               msgcnt=mss_cnt, receiver=msg['sender'])
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'],
                                               sender=AgenteAlojamientosExternoAmadeus.uri,
                                               msgcnt=mss_cnt)
            else:
                grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                           msgcnt=mss_cnt)

    serialize = grespuesta.serialize(format='xml')
    return serialize, 200


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
    pass


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """
    gr = register_message()

    pass

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteAlojamientosExternoAmadeus, DirectoryAgent, AgenteAlojamientosExternoAmadeus.uri, get_count())
    return gr


def buscar_alojamientos_externos():
    # DATE HA DE SER STRING YYYY-MM-DD
    # CALL
    grafo_hoteles = Graph()
    grafo_hoteles.bind('ECSDI', ECSDI)
    array_city = ["BCN", "PAR"]

    content = ECSDI['Respuesta_Alojamiento' + str(get_count())]

    for city in array_city:
        for i in range(1, 10):
            j = 0
            cityhotels = amadeus.shopping.hotel_offers.get(cityCode=city, page=i)
            response = cityhotels.data

            # TRATAMIENTO RESPUESTA
            # grafo = Graph('dso', namespace)

            code = cityhotels.status_code

            if cityhotels.status_code != 200:
                print('Error al buscar hoteles: ' + cityhotels.status_code)
            else:
                for hotel in response:
                    if hotel["type"] == "hotel-offers":
                        j += 1
                        alojamiento = ECSDI['alojamiento' + city + str(i * j)]
                        proveedor_alojamientos = ECSDI['proveedor_alojamientos' + city + str(i * j)]
                        ciudad = ECSDI['ciudad']
                        localizacion = ECSDI['localizacion' + city + str(i * j)]

                        # localizacion
                        grafo_hoteles.add((localizacion, RDF.type, ECSDI.Localizacion))

                        # alojamiento
                        centrico = hotel["hotel"]["hotelDistance"]["distance"] <= 1

                        grafo_hoteles.add((alojamiento, RDF.type, ECSDI.Alojamiento))
                        grafo_hoteles.add((alojamiento, RDF.fecha_inicial, Literal(hotel["hotel"]["startDate"])))
                        grafo_hoteles.add((alojamiento, RDF.fecha_final, Literal(hotel["hotel"]["endDate"])))
                        grafo_hoteles.add((alojamiento, RDF.id_alojamiento, Literal(hotel["hotel"]["hotelId"])))
                        grafo_hoteles.add((alojamiento, RDF.nombre, Literal(hotel["hotel"]["name"])))
                        grafo_hoteles.add((alojamiento, RDF.centrico, Literal(centrico)))
                        grafo_hoteles.add((alojamiento, RDF.importe, Literal(hotel["offers"]["price"]["total"])))

                        # proveedor_alojamientos
                        grafo_hoteles.add((proveedor_alojamientos, RDF.type, ECSDI.Proveedor_alojamiento))
                        grafo_hoteles.add((proveedor_alojamientos, RDF.nombre, Literal(hotel["hotel"]["chainCode"])))

                        # ciudad NOT SURE DE SI FA FALTA
                        grafo_hoteles.add((ciudad, RDF.type, ECSDI.Ciudad))
                        grafo_hoteles.add((ciudad, RDF.nombre, Literal(city)))

                        # relacions
                        grafo_hoteles.add((alojamiento, RDF.tiene_ubicacion, URIRef(localizacion)))
                        grafo_hoteles.add((alojamiento, RDF.es_ofrecido_por, URIRef(proveedor_alojamientos)))

    return grafo_hoteles


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
