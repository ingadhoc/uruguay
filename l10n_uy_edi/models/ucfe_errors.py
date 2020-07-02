from odoo import _


def get_error_message(title, code_value, data):
    code_value = str(code_value)
    return title + ": " + str(code_value) + '"%s"' % data.get(code_value)


def _hint_msg(response):
    """ Get expĺanation of errors returned by ucfe webservices and a hint of how to solved """
    data = {}
    data.update({
    })

    # CodRta responses codes
    CodRta = {
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
    codrta_res = get_error_message(_('Codigo Respuesta'), response.Resp.CodRta, CodRta)

    # Indica en qué estado se encuentra en DGI el CFE recibido, los posibles valores se listan a continuación:
    EstadoEnDgiCfeRecibido = {
        '00': 'aceptado por DGI',
        '05': 'rechazado por DGI',
        '06': 'observado por DGI',
        '11': 'UCFE no pudo consultar a DGI (puede intentar volver a ejecutar la consulta con la función 650 –'
              ' Consulta a DGI por CFE recibido)',
        '10': 'aceptado por DGI pero no se pudo ejecutar la consulta QR',
        '15': 'rechazado por DGI pero no se pudo ejecutar la consulta QR',
        '16': 'observado por DGI pero no se pudo ejecutar la consulta QR',
        '20': 'aceptado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido',
        '25': 'rechazado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido',
        '26': 'observado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido',
    }
    estado_dif_cfe_recibido_res = get_error_message(
        _('DGI CFE Estado Recibido'), response.Resp.EstadoEnDgiCfeRecibido, EstadoEnDgiCfeRecibido)

    MensajeRta = _('Mensaje de Respuesta') + ': ' + response.Resp.MensajeRta

    # TODO TipoNotificacion
    # 5, Aviso de CFE emitido rechazado por DGI
    # 6, Aviso de CFE emitido rechazado por el receptor electrónico
    # 7, Aviso de CFE recibido
    # 8, Aviso de anulación de CFE recibido
    # 9, Aviso de aceptación comercial de un CFE recibido
    # 10, Aviso de aceptación comercial de un CFE recibido en la gestión UCFE
    # 11, Aviso de que se ha emitido un CFE
    # 12, Aviso de que se ha emitido un CFE en la gestión UCFE
    # 13, Aviso de rechazo comercial de un CFE recibido
    # 14, Aviso de rechazo comercial de un CFE recibido en la gestión UCFE
    # 15, Aviso de CFE emitido aceptado por DGI
    # 16, Aviso de CFE emitido aceptado por el receptor electrónico
    # 17, Aviso que a un CFE emitido se lo ha etiquetado
    # 18, Aviso que a un CFE emitido se le removió una etiqueta
    # 19, Aviso que a un CFE recibido se lo ha etiquetado
    # 20. Aviso que a un CFE recibido se le removió una etiqueta

    # TODO TipoMensaje

    return data.get(response.ErrorCode, '') + ''.join([codrta_res, estado_dif_cfe_recibido_res, MensajeRta])
