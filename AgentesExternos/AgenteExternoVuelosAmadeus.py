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
from pprint import PrettyPrinter

from rdflib import Namespace, Graph
from flask import Flask
from dotenv import load_dotenv
from amadeus import Client, ResponseError

from AgentUtil.ACLMessages import register_agent
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.OntoNamespaces import ECSDI, ACL
from AgentUtil.Logging import config_logger

__author__ = 'javier'

# Configuration stuff
hostname = socket.gethostname()
port = 9011

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

# Logging
logger = config_logger(level=1)

# Datos del Agente

AgenteExternoVuelosAmadeus = Agent('AgenteExternoVuelosAmadeus',
                       agn.AgenteExternoVuelos,
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

# APIs
load_dotenv()
AMADEUS_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_SECRET = os.getenv("AMADEUS_API_SECRET")
amadeus = Client(client_id=AMADEUS_KEY, client_secret=AMADEUS_SECRET)
ppr = PrettyPrinter(indent=4)


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


def vuelosAmadeus():
    try:
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode='BCN',
            destinationLocationCode='PAR',
            departureDate='2021-06-01',
            adults=1)
        print("FLIGHTS")
        print("-----------------------------------")
        ppr.pprint(response.data)
    except ResponseError as error:
        print(error)
    

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


def agentbehavior1(cola):
    """
    Un comportamiento del agente
    :return:
    """
    # Registramos el agente
    gr = register_message()

    # Escuchando la cola hasta que llegue un 0
    fin = False
    while not fin:
        while cola.empty():
            pass
        v = cola.get()
        if v == 0:
            fin = True
        else:
            print(v)



if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
