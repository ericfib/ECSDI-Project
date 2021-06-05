# -*- coding: utf-8 -*-
from functools import lru_cache
from multiprocessing import Process, Queue
import socket

from cachetools.func import ttl_cache

from AgentUtil.ACLMessages import get_agent_info, send_message, build_message, get_message_properties, register_agent
from rdflib import Namespace, Graph, Literal, URIRef, RDF, XSD, FOAF
from flask import Flask, request, render_template

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent

__author__ = 'arnau'

# Configuration stuff
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ACL, DSO, ECSDI

hostname = socket.gethostname()
port = 9005

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Logging
logger = config_logger(level=1)

# Datos del Agente

AgenteViaje = Agent('AgenteViaje',
                    agn.AgenteViaje,
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

# Agentes
ag_hoteles = Agent('', '', '', None)
ag_flights = Agent('', '', '', None)
ag_activity = Agent('', '', '', None)


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

    gmess = Graph()

    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[AgenteViaje.name + '-search']
    gmess.add((reg_obj, RDF.type, DSO.Search))
    gmess.add((reg_obj, DSO.AgentType, type))

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgenteViaje.uri,
                        receiver=DirectoryAgent.uri,
                        content=reg_obj,
                        msgcnt=mss_cnt)
    gr = send_message(msg, DirectoryAgent.address)
    mss_cnt += 1

    return gr


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    pass


def get_activities(g, peticion_plan):
    if ag_activity.address == '':
        logger.info('Buscando Agente de Actividades...')
        read_agent(agn.AgenteActividades, ag_activity)
        logger.info('Encontrado')
    logger.info('Pidiendo actividades al agente de Actividades...')
    g.add((peticion_plan, RDF.type, ECSDI.Peticion_Actividades))
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_activity.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_activity.address)
    result = []
    act_list = gresp.triples((None, RDF.type, ECSDI.Actividad))
    logger.info('Recibidas')
    for item in act_list:
        next_act_uri = item[0]
        nombre = str(gresp.value(subject=next_act_uri, predicate=ECSDI.nombre))
        fecha = str(gresp.value(subject=next_act_uri, predicate=ECSDI.fecha))
        coordenadas = str(gresp.value(subject=next_act_uri, predicate=ECSDI.coordenadas))
        result.append({'nombre': nombre, 'fecha': fecha, 'coordenadas': coordenadas})
    result.sort(key=lambda x: x['fecha'])
    return result


def get_hotels(g, peticion_plan):
    if ag_hoteles.address == '':
        logger.info('Buscando Agente de Alojamientos...')
        read_agent(agn.AgenteAlojamientos, ag_hoteles)
        logger.info('Encontrado')
    logger.info('Pidiendo alojamientos al agente de Alojamientos')
    g.add((peticion_plan, RDF.type, ECSDI.Peticion_Alojamientos))
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_hoteles.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_hoteles.address)
    logger.info('Recibidos')
    return gresp


def get_flights(g, peticion_plan):
    if ag_flights.address == '':
        logger.info('Buscando Agente de Vuelos...')
        read_agent(agn.AgenteVuelos, ag_flights)
        logger.info('Encontrado')
    logger.info('Pidiendo vuelos al agente de Vuelos')
    g.add((peticion_plan, RDF.type, ECSDI.Peticion_Vuelos))
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_flights.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_flights.address)
    logger.info('Recibidos')
    return gresp


def create_peticion_de_plan_graph(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                                  cultural, ludic, festivity, aloj_min_price, aloj_max_price, centrico, peticion_plan,
                                  n):
    g = Graph()
    ciudad_origen = ECSDI['ciudad_origen' + str(n)]
    g.add((ciudad_origen, RDF.type, ECSDI.ciudad))
    g.add((ciudad_origen, ECSDI.nombre, Literal(origin)))
    g.add((peticion_plan, ECSDI.ciudad_origen, ciudad_origen))
    ciudad_destino = ECSDI['ciudad_destino' + str(n)]
    g.add((ciudad_destino, RDF.type, ECSDI.ciudad))
    g.add((ciudad_destino, ECSDI.nombre, Literal(destination)))
    g.add((peticion_plan, ECSDI.ciudad_destino, ciudad_destino))
    data_inicio = ECSDI['fecha_inicial' + str(n)]
    g.add((data_inicio, RDF.type, ECSDI.fecha))
    g.add((data_inicio, ECSDI.fecha, Literal(dep_date)))
    g.add((peticion_plan, ECSDI.fecha_inicio, data_inicio))
    data_fin = ECSDI['fecha_final' + str(n)]
    g.add((data_fin, RDF.type, ECSDI.fecha))
    g.add((data_fin, ECSDI.fecha, Literal(ret_date)))
    g.add((peticion_plan, ECSDI.fecha_final, data_fin))
    ludica = ECSDI['porcentaje_actividad_ludica' + str(n)]
    g.add((ludica, RDF.type, ECSDI.tipo_actividad))
    g.add((ludica, ECSDI.tipo, Literal(ludic)))
    g.add((peticion_plan, ECSDI.ludica, ludica))
    cultura = ECSDI['porcentaje_actividad_cultural' + str(n)]
    g.add((cultura, RDF.type, ECSDI.tipo_actividad))
    g.add((cultura, ECSDI.tipo, Literal(cultural)))
    g.add((peticion_plan, ECSDI.cultural, cultura))
    festiva = ECSDI['porcentaje_actividad_festiva' + str(n)]
    g.add((festiva, RDF.type, ECSDI.tipo_actividad))
    g.add((festiva, ECSDI.tipo, Literal(festivity)))
    g.add((peticion_plan, ECSDI.festiva, festiva))
    r_al_max = ECSDI['rango_precio_alojamiento_max' + str(n)]
    g.add((r_al_max, RDF.type, ECSDI.rango_precio))
    g.add((r_al_max, ECSDI.numero, Literal(aloj_max_price)))
    g.add((peticion_plan, ECSDI.rango_precio_alojamiento_max, r_al_max))
    r_al_min = ECSDI['rango_precio_alojamiento_min' + str(n)]
    g.add((r_al_min, RDF.type, ECSDI.rango_precio))
    g.add((r_al_min, ECSDI.numero, Literal(aloj_min_price)))
    g.add((peticion_plan, ECSDI.rango_precio_alojamiento_min, r_al_min))
    r_fl_max = ECSDI['rango_precio_vuelo_max' + str(n)]
    g.add((r_fl_max, RDF.type, ECSDI.rango_precio))
    g.add((r_fl_max, ECSDI.numero, Literal(flight_max_price)))
    g.add((peticion_plan, ECSDI.rango_precio_vuelos_max, r_fl_max))
    r_fl_min = ECSDI['rango_precio_vuelo_min' + str(n)]
    g.add((r_fl_min, RDF.type, ECSDI.rango_precio))
    g.add((r_fl_min, ECSDI.numero, Literal(flight_min_price)))
    g.add((peticion_plan, ECSDI.rango_precio_vuelos_min, r_fl_min))
    centrico_uri = ECSDI['alojamiento_centrico' + str(n)]
    g.add((centrico_uri, RDF.type, ECSDI.centrico))
    g.add((centrico_uri, ECSDI.centrico, Literal(centrico)))
    g.add((peticion_plan, ECSDI.alojamiento_centrico, centrico_uri))

    return g


@ttl_cache(maxsize=1000000, ttl=10 * 60)
def create_result(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price, cultural, ludic,
                  festivity, hotel_min_price, hotel_max_price, centrico):
    n = get_count()
    peticion_plan = ECSDI['peticion_de_plan' + str(n)]
    g = create_peticion_de_plan_graph(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                                      cultural, ludic, festivity, hotel_min_price, hotel_max_price, centrico,
                                      peticion_plan, n)
    activities = get_activities(g, peticion_plan)
    # hotels = get_hotels(g, peticion_plan)
    # flights = get_flights(g, peticion_plan)
    return {'activities': activities}


@app.route("/iface", methods=['GET', 'POST'])
def form():
    if request.method == 'GET':
        return render_template('formulario.html')
    else:
        origin = request.form['corigin']
        destination = request.form['cdestination']
        dep_date = request.form['idate']
        ret_date = request.form['fdate']
        flight_max_price = request.form['fmaxp']
        flight_min_price = request.form['fminp']
        hotel_max_price = request.form['fmaxh']
        hotel_min_price = request.form['fminh']
        cultural = request.form['cact']
        ludic = request.form['lact']
        festivity = request.form['fact']
        centrico = request.form.get('centrico', False)
        if centrico:
            centrico = True

        result = create_result(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                               cultural, ludic, festivity, hotel_min_price, hotel_max_price, centrico)

        return render_template('result.html', activities=result['activities'])


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def get_count():
    global mss_cnt
    if not mss_cnt:
        mss_cnt = 0
    mss_cnt += 1
    return mss_cnt


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def read_agent(tipus, agente):
    gr = directory_search_message(tipus)
    msg = gr.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = gr.value(subject=msg, predicate=ACL.content)
    ragn_addr = gr.value(subject=content, predicate=DSO.Address)
    ragn_uri = gr.value(subject=content, predicate=DSO.Uri)
    agente.uri = ragn_uri
    agente.address = ragn_addr


def agentbehavior1(cola):
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
