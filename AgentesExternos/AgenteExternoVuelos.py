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
from random import randrange
from datetime import timedelta
from datetime import datetime
import random

from rdflib import Namespace, Graph
from flask import Flask, request

import argparse
from rdflib import Namespace, Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, register_agent, get_message_properties, get_agent_info
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ECSDI,ACL,TIO

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
    port = 9021
else:
    port = args.port

if args.open:
    hostname = '0.0.0.0'
    hostaddr = gethostname()
else:
    hostaddr = hostname = socket.gethostname()

print('DS Hostname =', hostaddr)

if args.dport is None:
    dport = 9000
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

# Contador de mensajes
def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

# Datos del Agente

AgenteExternoVuelos = Agent('AgenteExternoVuelos',
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


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    print("PETICION DE VUELOS MEDIANTE BD RECIBIDA")

    message = request.args['content']

    grafo_mensaje_entrante = Graph()
    grespuesta = Graph()
    grafo_mensaje_entrante.parse(data=message)

    msg = get_message_properties(grafo_mensaje_entrante)

    if msg is None:
        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteExternoVuelos.uri,
                                   msgcnt=mss_cnt)

    else:
        # obtener performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteExternoVuelos.uri,
                                       msgcnt=mss_cnt)

        else:
            if 'content' in msg:
                content = msg['content']
                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)

                # hacer lo que pide la accion
                if accion == ECSDI.Peticion_Vuelos:     
                   
                    grespuesta = buscar_vuelos_externos()

                    grespuesta = build_message(grespuesta, ACL['inform-'], sender=AgenteExternoVuelos.uri,
                                               msgcnt=mss_cnt, receiver=msg['sender'])
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'],
                                               sender=AgenteExternoVuelos.uri,
                                               msgcnt=mss_cnt)
            else:
                grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteExternoVuelos.uri,
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

def random_date(start, end):
    """
    This function will return a random datetime between two datetime 
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)

def buscar_vuelos_externos():
    global originAirport
    global destAirport

    g = Graph()
    grafo_vuelos = Graph()
    grafo_vuelos.bind('ECSDI', ECSDI)

    content = ECSDI['Respuesta_Alojamiento' + str(get_count())]

    # Carga el grafo RDF desde el fichero
    ontofile = gzip.open('../datos/FlightRoutes.ttl.gz')

    g.parse(ontofile, format='turtle')

    
    bcn = "http://dbpedia.org/resource/Barcelona%E2%80%93El_Prat_Airport"
    prs = "http://dbpedia.org/resource/Charles_de_Gaulle_Airport"


    # Se buscan vuelos con el aeropuerto de origen y destino
    origenquerypb = """
        prefix tio:<http://purl.org/tio/ns#>
        Select ?vuelo ?fromall ?toall ?comp
        where {
            ?vuelo rdf:type tio:Flight .
            ?vuelo tio:to ?toall .
            ?vuelo tio:from ?fromall .
            ?vuelo tio:operatedBy ?comp .
            ?vuelo tio:to <"""+bcn+"""> .
            ?vuelo tio:from <"""+prs+"""> .
            }
        """

    qpb = g.query(origenquerypb, initNs=dict(tio=TIO))

    
    ini_date='1/1/2021'
    fin_date='1/1/2022'
    min_price=50
    max_price=250

    dat_origen = datetime.strptime(ini_date+' 6:30 AM', '%d/%m/%Y %I:%M %p')
    dat_destino = datetime.strptime(fin_date+' 6:30 AM', '%d/%m/%Y %I:%M %p')
    

    for row in qpb.result:
        print(row)
        fecha_salida=random_date(dat_origen,dat_destino)
        fecha_salida_origen = random_date(fecha_salida, fecha_salida+timedelta(hours=14))
        fecha_llegada_origen = random_date(fecha_salida_origen+timedelta(hours=3), fecha_salida_origen+timedelta(hours=5))
    
        precio_origen = random.randint(min_price,max_price)

        print(fecha_salida_origen)
        print(fecha_llegada_origen)

        print(precio_origen)


        # COMPROBAR QUE TODO EXISTA Y SI NO, AÑADIRLO!
        vuelo_origen = ECSDI['vuelo' + str(get_count())]
        vuelo_destino = ECSDI['vuelo' + str(get_count())]
        compania = ECSDI['proveedor_de_vuelos' + str(get_count())]
        origen = ECSDI['aeropuerto'+str(get_count())]
        destino = ECSDI['aeropuerto'+str(get_count())]

        # Compania
        grafo_vuelos.add((compania, RDF.type, ECSDI.compania))
        grafo_vuelos.add((compania, ECSDI.nombre, Literal(row[3])))

        # Llega a
        grafo_vuelos.add((destino, RDF.type, ECSDI.aeropuerto))
        grafo_vuelos.add((destino, ECSDI.nombre, Literal(row[2])))

        # Sale_de
        grafo_vuelos.add((origen, RDF.type, ECSDI.aeropuerto))
        grafo_vuelos.add((origen, ECSDI.nombre, Literal(row[1])))


        # Vuelo origen
        grafo_vuelos.add((vuelo_origen, RDF.type, ECSDI.vuelo))
        grafo_vuelos.add((vuelo_origen, ECSDI.tiene_como_aeropuerto_origen, URIRef(origen)))
        grafo_vuelos.add((vuelo_origen, ECSDI.importe, Literal(precio_origen))) # comprobar que importe sea atributo de vuelo
        grafo_vuelos.add((vuelo_origen, ECSDI.es_ofrecido_por, URIRef(compania)))
        grafo_vuelos.add((vuelo_origen, ECSDI.fecha_inicial, Literal(fecha_salida_origen)))
        grafo_vuelos.add((vuelo_origen, ECSDI.fecha_final, Literal(fecha_llegada_origen)))


    # Se buscan vuelos con el aeropuerto de origen y destino
    origenquerybp = """
        prefix tio:<http://purl.org/tio/ns#>
        Select ?vuelo ?fromall ?toall ?comp
        where {
            ?vuelo rdf:type tio:Flight .
            ?vuelo tio:to ?toall .
            ?vuelo tio:from ?fromall .
            ?vuelo tio:operatedBy ?comp .
            ?vuelo tio:to <"""+prs+"""> .
            ?vuelo tio:from <"""+bcn+"""> .
            }
        """

    qbp = g.query(origenquerybp, initNs=dict(tio=TIO))

    for row in qbp.result:
        print(row)
        fecha_llegada=random_date(dat_origen,dat_destino)
        fecha_salida_destino = random_date(fecha_llegada, fecha_llegada+timedelta(hours=14))
        fecha_llegada_destino = random_date(fecha_salida_destino+timedelta(hours=3), fecha_salida_destino+timedelta(hours=5))

        precio_destino = random.randint(min_price,max_price)

        print(fecha_salida_destino)
        print(fecha_llegada_destino)

        print(precio_destino)

        # COMPROBAR QUE TODO EXISTA Y SI NO, AÑADIRLO!
        vuelo_origen = ECSDI['vuelo' + str(get_count())]
        vuelo_destino = ECSDI['vuelo' + str(get_count())]
        compania = ECSDI['proveedor_de_vuelos' + str(get_count())]
        origen = ECSDI['aeropuerto'+str(get_count())]
        destino = ECSDI['aeropuerto'+str(get_count())]

        # Compania
        grafo_vuelos.add((compania, RDF.type, ECSDI.compania))
        grafo_vuelos.add((compania, ECSDI.nombre, Literal(row[3])))

        # Llega a
        grafo_vuelos.add((destino, RDF.type, ECSDI.aeropuerto))
        grafo_vuelos.add((destino, ECSDI.nombre, Literal(row[2])))

        # Sale_de
        grafo_vuelos.add((origen, RDF.type, ECSDI.aeropuerto))
        grafo_vuelos.add((origen, ECSDI.nombre, Literal(row[1])))

        # Vuelo destino
        grafo_vuelos.add((vuelo_destino, RDF.type, ECSDI.vuelo))
        grafo_vuelos.add((vuelo_destino, ECSDI.tiene_como_aeropuerto_destino, URIRef(destino)))
        grafo_vuelos.add((vuelo_destino, ECSDI.importe, Literal(precio_destino))) # comprobar que importe sea atributo de vuelo
        grafo_vuelos.add((vuelo_destino, ECSDI.es_ofrecido_por, URIRef(compania)))
        grafo_vuelos.add((vuelo_destino, ECSDI.fecha_inicial, Literal(fecha_salida_destino)))
        grafo_vuelos.add((vuelo_destino, ECSDI.fecha_final, Literal(fecha_llegada_destino)))


    # Devolvemos el grafo de vuelos
    logger.info('DEVOLVEMOS EL GRAFO DE VUELOS')
    return grafo_vuelos
        
def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteExternoVuelos, DirectoryAgent, AgenteExternoVuelos.uri, get_count())
    return gr

def tidyup():
    """
    Acciones previas a parar el agente
    """
    global cola1
    cola1.put(0)


def agentbehavior1():
    """
    Un comportamiento del agente
    :return:
    """
    # Registramos el agente
    gr = register_message()

    buscar_vuelos_externos()


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
