from odoo import _


def _hint_msg(response):
    """ Get expĺanation of errors returned by ucfe webservices and a hint of how to solved """
    data = {}
    data.update({
    })

    # CodRta responses codes
    codrta = {
        '00': 'Petición aceptada y procesada',
        '01': 'Petición denegada',
        '03': 'Comercio inválido',
        '05': 'CFE rechazado por DGI',
        '06': 'CFE observado por DGI',
        '11': 'CFE aceptado por UCFE, en espera de respuesta de DGI',
        '12': 'Requerimiento inválido',
        '30': 'Error en formato',
        '31': 'Error en formato de CFE',
        '89': 'Terminal inválida',
        '96': 'Error en sistema',
        '99': 'Sesión no iniciada.',
    }
    codrta_res = _('This is the description of the response code') + ": \"%s\"" % codrta.get(response.CodRta, response.CodRta + ' Requerimiento Denegado')

    return data.get(reponse.ErrorCode, '') + codrta_res
