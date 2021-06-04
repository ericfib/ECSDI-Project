# -*- coding: utf-8 -*-

from multiprocessing import Process, Queue
import socket

from AgentUtil.ACLMessages import get_agent_info, send_message, build_message, get_message_properties, register_agent
from rdflib import Namespace, Graph, Literal, URIRef, RDF, XSD, logger, FOAF
from flask import Flask, request, render_template

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent

__author__ = 'arnau'

# Configuration stuff
from AgentUtil.OntoNamespaces import ACL, DSO, ECSDI

hostname = socket.gethostname()
port = 9002

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

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
    logger.info('Buscamos en el servicio de registro')

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
    logger.info('Recibimos informacion del agente')

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
        read_agent(agn.AgenteActividades, ag_activity)
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_activity.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_activity.address)
    return gresp


def get_hotels(g, peticion_plan):
    if ag_hoteles.address == '':
        read_agent(agn.AgenteAlojamientos, ag_hoteles)
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_hoteles.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_hoteles.address)
    return gresp


def get_flights(g, peticion_plan):
    if ag_flights.address == '':
        read_agent(agn.AgenteVuelos, ag_flights)
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_flights.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_flights.address)
    return gresp


def create_peticion_de_plan_graph(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                                  cultural, ludic, festivity, aloj_min_price, aloj_max_price, peticion_plan, n):
    g = Graph()

    ciudad_origen = ECSDI['ciudad' + str(n)]
    g.add((ciudad_origen, RDF.type, ECSDI.ciudad))
    g.add((ciudad_origen, ECSDI.nombre, Literal(origin)))
    ciudad_destino = ECSDI['ciudad' + str(n)]
    g.add((ciudad_destino, RDF.type, ECSDI.ciudad))
    g.add((ciudad_destino, ECSDI.nombre, Literal(destination)))
    data_inicio = ECSDI['fecha_inicial' + str(n)]
    g.add((data_inicio, RDF.type, ECSDI.fecha))
    g.add((data_inicio, ECSDI.fecha, Literal(dep_date)))
    data_fin = ECSDI['fecha_final' + str(n)]
    g.add((data_fin, RDF.type, ECSDI.fecha))
    g.add((data_fin, ECSDI.fecha, Literal(ret_date)))
    ludica = ECSDI['porcentaje_actividad_ludica' + str(n)]
    g.add((ludica, RDF.type, ECSDI.tipo_actividad))
    g.add((ludica, ECSDI.tipo, Literal(ludic)))
    cultura = ECSDI['porcentaje_actividad_cultural' + str(n)]
    g.add((cultura, RDF.type, ECSDI.tipo_actividad))
    g.add((cultura, ECSDI.tipo, Literal(cultural)))
    festiva = ECSDI['porcentaje_actividad_festiva' + str(n)]
    g.add((festiva, RDF.type, ECSDI.tipo_actividad))
    g.add((festiva, ECSDI.tipo, Literal(festivity)))
    r_al_max = ECSDI['rango_precio_alojamiento_max' + str(n)]
    g.add((r_al_max, RDF.type, ECSDI.rango_precio))
    g.add((r_al_max, ECSDI.numero, Literal(aloj_max_price)))
    r_al_min = ECSDI['rango_precio_alojamiento_min' + str(n)]
    g.add((r_al_min, RDF.type, ECSDI.rango_precio))
    g.add((r_al_min, ECSDI.numero, Literal(aloj_min_price)))
    r_fl_max = ECSDI['rango_precio_vuelo_max' + str(n)]
    g.add((r_fl_max, RDF.type, ECSDI.rango_precio))
    g.add((r_fl_max, ECSDI.numero, Literal(flight_max_price)))
    r_fl_min = ECSDI['rango_precio_vuelo_min' + str(n)]
    g.add((r_fl_min, RDF.type, ECSDI.rango_precio))
    g.add((r_fl_min, ECSDI.numero, Literal(flight_min_price)))

    return g


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

        n = get_count()
        peticion_plan = ECSDI['peticion_de_plan' + str(n)]
        g = create_peticion_de_plan_graph(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                                          cultural, ludic, festivity, hotel_min_price, hotel_max_price, peticion_plan, n)
        # activities = get_activities(g, peticion_plan)
        hotels = get_hotels(g, peticion_plan)
        # flights = get_flights(g, peticion_plan)

        # result = activities + hotels + flights

        return render_template('formulario.html')


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
    ab1 = Process(target=agentbehavior1, args=(cola1, ))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
