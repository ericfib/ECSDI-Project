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

__author__ = 'arnau'

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
file_str = '../Examples/data/%s/%s.json'

# parsing de los parametros de la linea de comandos
args = parser.parse_args()
# Configuration stuff
if args.port is None:
    port = 9013
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


AgenteAlojamientosExternoAmadeus = Agent('AgenteActividadesExternoAmadeus',
                                         agn.AgenteActividadesExternoAmadeus,
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

    message = request.args['content']

    grafo_mensaje_entrante = Graph()
    grespuesta = Graph()
    grafo_mensaje_entrante.parse(data=message)

    msg = get_message_properties(grafo_mensaje_entrante)

    if msg is None:
        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                   msgcnt=mss_cnt)
        logger.info("PETICION DE ERRONEA RECIBIDA")

    else:
        # obtener performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                       msgcnt=mss_cnt)
            logger.info("PETICION DE ERRONEA RECIBIDA")

        else:
            if 'content' in msg:
                content = msg['content']
                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)

                # hacer lo que pide la accion
                if accion == ECSDI.Peticion_Actividades:
                    grespuesta = buscar_actividades_externos()

                    grespuesta = build_message(grespuesta, ACL['inform-'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                               msgcnt=mss_cnt, receiver=msg['sender'])
                    logger.info("PETICION DE ACTIVIDADES RECIBIDA")
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'],
                                               sender=AgenteAlojamientosExternoAmadeus.uri,
                                               msgcnt=mss_cnt)
                    logger.info("PETICION DE ERRONEA RECIBIDA")
            else:
                grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientosExternoAmadeus.uri,
                                           msgcnt=mss_cnt)
                logger.info("PETICION DE ERRONEA RECIBIDA")

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


def buscar_actividades_externos():
    grafo_actividades = Graph()
    grafo_actividades.bind('ECSDI', ECSDI)
    array_city = [{'lat': '41.38879', 'long': '2.15899', 'code': 'BCN'}, {'lat': '48.85341', 'long': '2.3488',
                                                                          'code': 'PAR'}]
    types = {'cultural': 'SIGHTS', 'ludica': 'NIGHTLIFE',
             'festiva': 'RESTAURANT, SHOPPING'}
    ECSDI_LIST = [ECSDI.Cultural, ECSDI.Ludica, ECSDI.Festiva]
    content = ECSDI['Respuesta_Actividades' + str(get_count())]
    for city in array_city:
        for i, (key, t) in enumerate(types.items()):
            try:
                activities = amadeus.reference_data.locations.points_of_interest.get(latitude=city['lat'],
                                                                                     longitud=city['long'],
                                                                                     radius=5, categories=t)
            except ResponseError:
                with open(file_str % (city['code'], key)) as file:
                    activities = json.load(file)
            for item in activities.get('data'):
                actividad = ECSDI[key + '-' + str(get_count())]
                grafo_actividades.add((actividad, RDF.type, ECSDI_LIST[i]))
                grafo_actividades.add((actividad, ECSDI.nombre, Literal(item["name"])))
                grafo_actividades.add((actividad, ECSDI.ciudad, Literal(city['code'])))
                grafo_actividades.add((actividad, ECSDI.coordenadas, Literal(str(item['geoCode']['latitude']) + ', ' +
                                                                             str(item['geoCode']['longitude']))))
    return grafo_actividades


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
