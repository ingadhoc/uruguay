from odoo import _


def get_error_message(title, code_value, data={}):
    code_value = str(code_value)
    return title + ": " + str(code_value) + ' "%s".' % data.get(code_value, 'No disponible')


def _hint_msg(response):
    """ Get expĺanation of errors returned by ucfe webservices and a hint of how to solved """
    res = []
    if response.ErrorCode:
        error_code = {
            None: 'Fue procesado con exito por el webservice',
            500: 'Se produjo un error en elwebservice',
        }
        res.append(get_error_message(_('Código de error de la solicitud'), response.ErrorCode, error_code))
    if response.ErrorMessage:
        res.append(get_error_message(_('Mensaje código de error'), response.ErrorCode))
    if response.Resp.CodRta:
        codrta_codes = {
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
        res.append(get_error_message(_('Codigo Respuesta'), response.Resp.CodRta, codrta_codes))

    # TODO si esto lo logramos agregar como campo borrar de aca ya que no seria necesario
    if response.Resp.EstadoEnDgiCfeRecibido:  # Indica en qué estado se encuentra en DGI el CFE recibido
        dgi_state_codes = {
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
        res.append(get_error_message(_('Estado en DGI'), response.Resp.EstadoEnDgiCfeRecibido, dgi_state_codes))
    if response.Resp.MensajeRta:
        res.append(_('Mensaje de Respuesta') + ': ' + response.Resp.MensajeRta)
    if response.Resp.TipoNotificacion:
        notif_type_codes = {
            '5': 'Aviso de CFE emitido rechazado por DGI',
            '6': 'Aviso de CFE emitido rechazado por el receptor electrónico',
            '7': 'Aviso de CFE recibido',
            '8': 'Aviso de anulación de CFE recibido',
            '9': 'Aviso de aceptación comercial de un CFE recibido',
            '10': 'Aviso de aceptación comercial de un CFE recibido en la gestión UCFE',
            '11': 'Aviso de que se ha emitido un CFE',
            '12': 'Aviso de que se ha emitido un CFE en la gestión UCFE',
            '13': 'Aviso de rechazo comercial de un CFE recibido',
            '14': 'Aviso de rechazo comercial de un CFE recibido en la gestión UCFE',
            '15': 'Aviso de CFE emitido aceptado por DGI',
            '16': 'Aviso de CFE emitido aceptado por el receptor electrónico',
            '17': 'Aviso que a un CFE emitido se lo ha etiquetado',
            '18': 'Aviso que a un CFE emitido se le removió una etiqueta',
            '19': 'Aviso que a un CFE recibido se lo ha etiquetado',
            '20': 'Aviso que a un CFE recibido se le removió una etiqueta',
        }
        res.append(get_error_message(_('Tipo Notificacion'), response.Resp.TipoNotificacion, notif_type_codes))
    if response.Resp.TipoMensaje == 811:
        res.append(get_error_message(_('Tipo Mensaje'), response.Resp.TipoMensaje,
                                     _('No se pudo interpretar el requerimiento recibido')))
    return '* ' + ('\n* '.join(res)) if res else ''
