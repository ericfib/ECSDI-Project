# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent
Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH
Agente que se registra como agente de hoteles y espera peticiones
@author: javier
"""

from datetime import datetime
from functools import lru_cache
from multiprocessing import Process, Queue
import socket

import argparse

from apscheduler.schedulers.background import BackgroundScheduler
from rdflib import Namespace, Graph
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
ag_vuelos_ext = [Agent('', '', '', None),Agent('', '', '', None)]



def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


# Datos del Agente


AgenteVuelos = Agent('AgenteVuelos',
                                         agn.AgenteVuelos,
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
    reg_obj = agn[AgenteVuelos.name + '-search']
    gmess.add((reg_obj, RDF.type, DSO.Search))
    gmess.add((reg_obj, DSO.AgentType, type))

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgenteVuelos.uri,
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

def get_vuelos():
    global ag
    if mss_cnt % 2 != 0:
        ag = ag_vuelos_ext[0]
        if ag.address == '':
            logger.info('Contactando Agente de alojamientos externo...')
            read_agent(agn.AgenteExternoVuelos, ag)
    else:
        ag = ag_vuelos_ext[1]
        logger.info('Contactando Agente de alojamientos externo amadeus...')
        if ag.address == '':
            read_agent(agn.AgenteExternoVuelosAmadeus, ag)

    g = Graph()

    peticion_vuelos = ECSDI['peticion_vuelos' + str(get_count())]
    g.add((peticion_vuelos, RDF.type, ECSDI.Peticion_Vuelos))

    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteVuelos.uri, receiver=ag.uri,
                                   msgcnt=mss_cnt,
                                   content=peticion_vuelos), ag.address)

    logger.info('Todo ha ido bien')
    gresp.serialize(destination='../datos/vuelos.ttl', format='turtle')


def reload_data():


    logger.info('Refrescando datos... haha')
    get_vuelos()


def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteVuelos, DirectoryAgent, AgenteVuelos.uri, get_count())
    return gr


    # sched.add_job(get_alojamientos, 'cron', day='*', hour='12')


@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    return 'Nothing to see here'


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


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
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(),
                           ACL['not-understood'],
                           sender=AgenteVuelos.uri,
                           msgcnt=mss_cnt)
    else:
        # obtener performativa
        perf = msg['performative']

        if perf == ACL.request:
            if 'content' in msg:
                content = msg['content']

                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)
                if accion == ECSDI.Peticion_Vuelos:
                    # PROCESAR PARAMETROS QUE ENVIA ARNAU I BUSCARLOS EN CACHE/FICHERO, O PEDIR A AGENTE EXTERNO
                    pass
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteVuelos.uri,
                                               msgcnt=mss_cnt)


        # elif perf == ACL.inform:
        #     if 'content' in msg:
        #         content = msg['content']
        #
        #         accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)
        #         if accion == ECSDI.Res:
        #             # GUARDAR EN FICHERO/CACHE LA RESPUESTA DEL AGENTE EXTERNO
        #             pass
        #         else:
        #             grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteVuelos.uri,
        #                                        msgcnt=mss_cnt)

        else:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteVuelos.uri,
                                       msgcnt=mss_cnt)

    serialize = grespuesta.serialize(format='xml')
    return serialize, 200


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
    reload_data()


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()
    sched.start()
    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
