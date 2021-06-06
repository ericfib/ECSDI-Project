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
import socket
from multiprocessing import Process, Queue


import argparse

from apscheduler.schedulers.background import BackgroundScheduler
from cachetools.func import ttl_cache
from rdflib import Namespace, Graph, URIRef
from rdflib.namespace import RDF, FOAF

from flask import Flask, request

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, register_agent, get_message_properties, send_message
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ACL, ECSDI, DSO

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
    dport = 9002
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

sched = BackgroundScheduler()

# Agentes
ag_alojamientos_ext = Agent('', '', '', None)


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


# Datos del Agente


AgenteAlojamientos = Agent('AgenteAlojamientos',
                                         agn.AgenteAlojamientos,
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


def directory_search_message(type):
    """
    Busca en el servicio de registro mandando un
    mensaje de request con una accion Seach del servicio de directorio

    Podria ser mas adecuado mandar un query-ref y una descripcion de registo
    con variables

    :param type:
    :return:
    """
    global mss_cnt
    logger.info('Buscamos en el servicio de registro')

    gmess = Graph()

    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[AgenteAlojamientos.name + '-search']
    gmess.add((reg_obj, RDF.type, DSO.Search))
    gmess.add((reg_obj, DSO.AgentType, type))

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgenteAlojamientos.uri,
                        receiver=DirectoryAgent.uri,
                        content=reg_obj,
                        msgcnt=mss_cnt)
    gr = send_message(msg, DirectoryAgent.address)
    mss_cnt += 1
    logger.info('Recibimos informacion del agente')

    return gr


def read_agent(tipus, agente):
    gr = directory_search_message(tipus)
    msg = gr.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = gr.value(subject=msg, predicate=ACL.content)
    ragn_addr = gr.value(subject=content, predicate=DSO.Address)
    ragn_uri = gr.value(subject=content, predicate=DSO.Uri)
    agente.uri = ragn_uri
    agente.address = ragn_addr


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
        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientos.uri,
                                   msgcnt=mss_cnt)

    else:
        # obtener performativa
        perf = msg['performative']

        if perf == ACL.request:
            if 'content' in msg:
                content = msg['content']

                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)
                if accion == ECSDI.Peticion_Alojamientos:
                    ciudad_dict = {'barcelona': 'BCN', 'paris': 'PAR'}

                    precio_max_v = str(grafo_mensaje_entrante.value(subject=content, predicate=ECSDI.rango_precio_alojamiento_max))
                    precio_min_v = str(grafo_mensaje_entrante.value(subject=content, predicate=ECSDI.rango_precio_alojamiento_min))
                    ciudad_destino_v = str(grafo_mensaje_entrante.value(subject=content, predicate=ECSDI.ciudad_destino))
                    fecha_inicial_v = grafo_mensaje_entrante.value(subject=content, predicate=ECSDI.fecha_inicio)
                    fecha_final_v = grafo_mensaje_entrante.value(subject=content, predicate=ECSDI.fecha_final)
                    escentrico = bool(grafo_mensaje_entrante.value(subject=content, predicate=ECSDI.centrico))

                    try:
                        grespuesta = get_alojamientos(ciudad_dict[ciudad_destino_v.lower()], precio_max_v, precio_min_v,
                                                      fecha_inicial_v, fecha_final_v, escentrico)
                        grespuesta = build_message(grespuesta, ACL['inform-'], sender=AgenteAlojamientos.uri,
                                                   msgcnt=mss_cnt, receiver=msg['sender'])
                    except IndexError:
                        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientos.uri,
                                                   msgcnt=mss_cnt)
                    pass
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientos.uri,
                                               msgcnt=mss_cnt)

        else:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteAlojamientos.uri,
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
    pass

def fetch_alojamientos():
    if ag_alojamientos_ext.address == '':
        logger.info('Contactando Agente de alojamientos externo...')
        read_agent(agn.AgenteAlojamientosExternoAmadeus, ag_alojamientos_ext)
    g = Graph()

    peticion_alojamientos = ECSDI['peticion_alojamientos' + str(get_count())]
    g.add((peticion_alojamientos, RDF.type, ECSDI.Peticion_Alojamientos))

    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteAlojamientos.uri, receiver=ag_alojamientos_ext.uri,
                                       msgcnt=get_count(),
                                       content=peticion_alojamientos), ag_alojamientos_ext.address)

    gresp.serialize(destination='../datos/alojamientos.ttl', format='turtle')


@ttl_cache(maxsize=1000000, ttl=10 * 60)
def get_alojamientos(city, pricemax, pricemin, dateIni, dateFi, escentrico):

    gresp = Graph()
    gresp.bind('ECSDI', ECSDI)

    content = ECSDI['Respuesta_Alojamientos'+ str(get_count())]

    g = Graph()
    g.bind('ECSDI', ECSDI)
    g.parse('../datos/alojamientos.ttl', format='turtle')

    queryobj = """
        prefix ecsdi:<http://www.semanticweb.org/eric/ontologies/2021/4/ecsdiOntology#>
        Select ?Alojamiento 
        Where {
            ?Alojamiento ecsdi:ciudad "%s" .
            ?Alojamiento ecsdi:importe ?price
            ?Alojamiento ecsdi:centrico ?centrico
            FILTER(?centrico == %s)
            FILTER(?price <= %s && ?price >= %s)
        }
        LIMIT 1
    """ % (city, escentrico, pricemax, pricemin)

    qpb = g.query(queryobj, initNs=dict(ecsdi=ECSDI))
    alojamientoURI = qpb.result[0][0]
    precioFinal = g.value(subject=alojamientoURI, predicate=ECSDI.importe)
    nombreFinal = g.value(subject=alojamientoURI, predicate=ECSDI.nombre)
    coordenadasFinal = g.value(subject=alojamientoURI, predicate=ECSDI.coordenadas)

    gresp.add((alojamientoURI, RDF.type, ECSDI.Alojamiento))
    gresp.add((alojamientoURI, ECSDI.importe, precioFinal))
    gresp.add((alojamientoURI, ECSDI.nombre, nombreFinal))
    gresp.add((alojamientoURI, ECSDI.coordenadas, coordenadasFinal))
    gresp.add((alojamientoURI, ECSDI.fecha_inical, dateIni))
    gresp.add((alojamientoURI, ECSDI.fecha_final, dateFi))

    return gresp


def reload_data():
    logger.info('Refrescando datos...')
    fetch_alojamientos()


def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteAlojamientos, DirectoryAgent, AgenteAlojamientos.uri, get_count())
    return gr


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """
    gr = register_message()
    reload_data()


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()
    sched.add_job(reload_data, 'cron', day='*', hour='12')
    sched.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
