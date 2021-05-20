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

from rdflib import Namespace, Graph
from flask import Flask
from dotenv import load_dotenv
from amadeus import Client, ResponseError

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.DSO import ONTOLOGY

__author__ = 'javier'

# Configuration stuff
hostname = socket.gethostname()
port = 9011

agn = Namespace("http://www.agentes.org#")
# namespace = ONTOLOGY

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgentePersonal = Agent('AgenteSimple',
                       agn.AgenteSimple,
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
    city = 'BCN'
    pricemax = '800'
    pricemin = '200'
    arrivaldate = '2021-12-12'
    departuredate = '2021-12-25'
    buscar_alojamientos(city, pricemax, pricemin, arrivaldate, departuredate, 1)
    pass


def buscar_alojamientos(city, pricemax, pricemin, arrivaldate, departuredate, iscentric):
    pricerange = pricemax + '-' + pricemin
    # DATE HA DE SER STRING YYYY-MM-DD
    # CALL
    cityhotels = amadeus.shopping.hotel_offers.get(cityCode=city)

    response = cityhotels.data

    # TRATAMIENTO RESPUESTA
    # grafo = Graph('dso', namespace)
    out_file = open("../datos/hotels.json", "w")
    json.dump(response, out_file, indent=4)

    code = cityhotels.status_code

    if cityhotels.status_code != 200:
        print('Error al buscar hoteles: ' + cityhotels.status_code)
    else:
        print('HOTELES ENCONTRADOS : \n')
        for hotel in response:
            if hotel["type"] == "hotel-offers":
                nombre = hotel["hotel"]["name"]
                print('Nombre del hotel => ' + nombre)

    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
