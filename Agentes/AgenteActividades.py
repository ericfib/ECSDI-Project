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
from datetime import datetime, timedelta
from multiprocessing import Process, Queue
import socket

import argparse

from apscheduler.schedulers.background import BackgroundScheduler
from cachetools.func import ttl_cache
from rdflib import Namespace, Graph, Literal
from rdflib.namespace import RDF, FOAF

from flask import Flask, request

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, register_agent, get_message_properties, send_message
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ECSDI, ACL, DSO

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

# parsing de los parametros de la linea de comandos
args = parser.parse_args()
# Configuration stuff
if args.port is None:
    port = 9003
else:
    port = args.port

if args.open:
    hostname = '0.0.0.0'
    hostaddr = gethostname()
else:
    hostaddr = hostname = socket.gethostname()

print('DS Hostname =', hostaddr)

if args.dport is None:
    dport = 9012
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


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


# Datos del Agente


AgenteActividades = Agent('AgenteActividades',
                                         agn.AgenteActividades,
                                         'http://%s:%d/comm' % (hostname, port),
                                         'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

agn_externo = Agent('', '', '', None)

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
    reg_obj = agn[AgenteActividades.name + '-search']
    gmess.add((reg_obj, RDF.type, DSO.Search))
    gmess.add((reg_obj, DSO.AgentType, type))

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgenteActividades.uri,
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

def reload_data():
    if agn_externo.address == '':
        logger.info('Buscando Agente Externo de Actividades...')
        read_agent(agn.AgenteActividadesExternoAmadeus, agn_externo)
        logger.info('Encontrado')
    logger.info("Pidiendo datos para el futuro")
    g = Graph()
    peticion_actividades = ECSDI['peticion_actividades' + str(get_count())]
    g.add((peticion_actividades, RDF.type, ECSDI.Peticion_Actividades))

    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteActividades.uri, receiver=agn_externo.uri,
                                       msgcnt=get_count(),
                                       content=peticion_actividades), agn_externo.address)

    gresp.serialize(destination='../datos/actividades.ttl', format='turtle')
    logger.info("Datos guardados")


@ttl_cache(maxsize=1000000, ttl=10 * 60)
def get_n_actividades(n, city, type):
    gres = Graph()
    g = Graph()
    g.parse('../datos/actividades.ttl', format='turtle')
    act_list = g.triples((None, RDF.type, type))
    if act_list is not None:
        while n > 0:
            next_act_uri = next(act_list)[0]
            if str(g.value(subject=next_act_uri, predicate=ECSDI.ciudad)) == city:
                n -= 1
                name = g.value(subject=next_act_uri, predicate=ECSDI.nombre)
                coordenadas = g.value(subject=next_act_uri, predicate=ECSDI.coordenadas)
                gres.add((next_act_uri, RDF.type, ECSDI.Actividad))
                gres.add((next_act_uri, ECSDI.nombre, name))
                gres.add((next_act_uri, ECSDI.coordenadas, coordenadas))
    return gres


ACT_PER_DAY = 3


def add_dates(g, fecha):
    act_list = g.triples((None, RDF.type, ECSDI.Actividad))
    i = 1
    for item in act_list:
        next_act_uri = item[0]
        if i <= 0:
            i = ACT_PER_DAY
            fecha += timedelta(days=1)
        date = fecha.date()
        if i == 1:
            fecha = datetime.combine(date, datetime.strptime('21:00', '%H:%M').time())
        elif i == 2:
            fecha = datetime.combine(date, datetime.strptime('12:00', '%H:%M').time())
        else:
            fecha = datetime.combine(date, datetime.strptime('09:00', '%H:%M').time())
        g.add((next_act_uri, ECSDI.fecha, Literal(fecha.strftime("%d-%m-%Y %H:%M"))))
        i -= 1


def get_actividades(g, content):
    ciudad_dict = {'barcelona': 'BCN', 'paris': 'PAR'}
    ciudad_destino_v = str(g.value(subject=content, predicate=ECSDI.ciudad_destino))

    fecha_inicial_v = g.value(subject=content, predicate=ECSDI.fecha_inicial)
    fecha_inicial_date = datetime.strptime(fecha_inicial_v, '%Y-%m-%d')

    fecha_final_v = g.value(subject=content, predicate=ECSDI.fecha_final)
    fecha_final_date = datetime.strptime(fecha_final_v, '%Y-%m-%d')

    ludica_v = int(g.value(subject=content, predicate=ECSDI.porcentaje_actividad_ludica))

    cultural_v = int(g.value(subject=content, predicate=ECSDI.porcentaje_actividad_cultural))

    festiva_v = int(g.value(subject=content, predicate=ECSDI.porcentaje_actividad_festiva))

    days = (fecha_final_date - fecha_inicial_date).days
    actividades_ludicas = int(((days * ACT_PER_DAY) - 1) * (ludica_v / (ludica_v + cultural_v + festiva_v)))
    actividades_culturales = int(((days * ACT_PER_DAY) - 1) * (cultural_v / (ludica_v + cultural_v + festiva_v)))
    actividades_festivas = int(((days * ACT_PER_DAY) - 1) * (festiva_v / (ludica_v + cultural_v + festiva_v)))
    g = Graph()
    g += get_n_actividades(actividades_ludicas, ciudad_dict[ciudad_destino_v.lower()], ECSDI.Ludica)
    g += get_n_actividades(actividades_culturales, ciudad_dict[ciudad_destino_v.lower()], ECSDI.Cultural)
    g += get_n_actividades(actividades_festivas, ciudad_dict[ciudad_destino_v.lower()], ECSDI.Festiva)
    add_dates(g, fecha_inicial_date)
    return g


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
        grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteActividades.uri,
                                   msgcnt=mss_cnt)
        logger.info("PETICION DE ERRONEA RECIBIDA")

    else:
        # obtener performativa
        perf = msg['performative']

        if perf == ACL.request:
            if 'content' in msg:
                content = msg['content']

                accion = grafo_mensaje_entrante.value(subject=content, predicate=RDF.type)
                if accion == ECSDI.Peticion_Actividades:
                    logger.info("PETICION DE ACTIVIDADES RECIBIDA")
                    grespuesta = get_actividades(grafo_mensaje_entrante, content)
                else:
                    grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteActividades.uri,
                                               msgcnt=mss_cnt)
                    logger.info("PETICION DE ERRONEA RECIBIDA")

        else:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            grespuesta = build_message(Graph(), ACL['not-understood'], sender=AgenteActividades.uri,
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
    reload_data()


def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteActividades, DirectoryAgent, AgenteActividades.uri, get_count())
    return gr


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    sched.add_job(reload_data, 'cron', day='*', hour='12')
    sched.start()
    ab1 = Process(target=agentbehavior1)
    ab1.start()


    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
