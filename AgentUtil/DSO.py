"""
.. module:: ontology

 Translated by owl2rdflib

 Translated to RDFlib from ontology http://www.semanticweb.org/eric/ontologies/2021/4/ecsdiOntology

 :Date 19/05/2021 18:26:26
"""
from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

ONTOLOGY = ClosedNamespace(
    uri=URIRef('http://www.semanticweb.org/eric/ontologies/2021/4/ecsdiOntology'),
    terms=[
        # Classes
        'Proveedor_alojamiento',
        'Comunicacion',
        'Peticion_Vuelos',
        'Alojamiento',
        'Agente_Actividades',
        'Agente_Pagos',
        'Factura',
        'Festiva',
        'Peticion_Actividades',
        'Servicio',
        'Agente_Recomendacion',
        'Valoracion',
        'Documento',
        'Plan_de_viaje',
        'Vuelo',
        'Proveedor_de_actividades',
        'Respuesta_Tiempo',
        'Peticion_de_plan',
        'Ciudad',
        'Lúdica',
        'Actividad',
        'Agente_Opinion',
        'Agente_Viaje',
        'Cultural',
        'Plan',
        'Agente_Vuelos',
        'Peticion',
        'Peticion_Valoracion',
        'Lugar',
        'Peticion_Tiempo',
        'Compañia',
        'Respuesta',
        'Respuesta_Alojamiento',
        'Agente_Alojamientos',
        'Tiempo_meteorologico',
        'Usuario',
        'Agente',
        'Localizacion',
        'Respuesta_Vuelos',
        'Respuesta_Plan',
        'Proveedor_de_vuelos',
        'Respuesta_Actividades',
        'Recibo',
        'Peticion_Alojamientos',
        'Respuesta_Valoracion',
        'Plan_de_dia',

        # Object properties
        'tiene_localizacion_como_restriccion',
        'ofrece_vuelo',
        'esta_hecha_por',
        'tiene_como_alojamiento',
        'genera',
        'provoca',
        'tiene_actividades',
        'tiene_como_destino',
        'tiene_para_cada_dia',
        'opina_sobre',
        'solicita',
        'ofrece_actividades',
        'tiene_como_origen',
        'contrata',
        'es_ofrecido_por',
        'tiene_ubicacion',
        'tiene_como_vuelo_de_ida',
        'llega_a',
        'tiene_recibo',
        'tiene_como_vuelo_de_vuelta',
        'contiene',
        'envia',
        'tiene_factura',
        'hace',
        'se_recomienda_a',

        # Data properties
        'porcentaje_actividad_festiva',
        'tiempo',
        'puntuacion',
        'nombre',
        'rango_precio_alojamiento_max',
        'id_vuelo',
        'rango_precio_transporte_min',
        'direccion',
        'id_alojamiento',
        'centrico',
        'rango_precio_transporte_max',
        'fecha_inicial',
        'fecha_final',
        'importe',
        'Archivo',
        'franja_horaria',
        'porcentaje_actividad_ludica',
        'id_actividad',
        'porcentaje_actividad_cultural',
        'rango_precio_alojamiento_min',
        'id_plan'

        # Named Individuals
    ]
)
