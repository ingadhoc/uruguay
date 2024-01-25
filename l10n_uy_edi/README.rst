.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=================================
Uruguay - Facturacion Electronica
=================================

Este modulo permite la integración para que desde su base de Odoo se puedan emitir comprobantes electrónicos a la DGI (comprobantes del tipo ticket/facturas en todas sus variantes y sus respectivas nd/nc.

A demás de emitir el comprobante permite conectarse a la DGI para ver el estado del comprobante (si este fue rechazado o aprobado) ** esto porque la validacion electronica es asincrona

Permite consultar los datos de un contacto en su odoo, si este es o no emisor electronico, y los datos de padron como asistente para que les permita llenar los datos del contacto de manera mas sencilla en su odoo.

NOTA: Todas estas conexiones se hacen a traves de un servicio de tercero llamado Uruware

Para poder tener una representacion impresa de una factura electronica uruguaya se necesita que el pdf cumpla ciertas restricciones de ley, al momento desde el odoo no hemos hecho estas adaptaciones, pero lo que si hicimos fue agregar una marca de agua "no es un documento legal" para que los usuarios puedan identificar rapidamente si imprimen el reporte que este no es el oficial. En si el reporte PDF valido legalmente lo generaremos desde Uruware al momento de validar la factura. Si esta este documento pdf legal adjunto es el que seimprime esto desde cualquier lugar del odoo (y en caso de no estarlo tenemos un boton que permite regenerarlo):

1. accion imprimir factura y facturas sin pagos
2. opcion boton enviar e imprimir
3. envio automatico al validar la factura segun configuracion del diario


Configuración
-------------

Known issues / Roadmap
======================

Credits
=======

ADHOC

Contributors
------------

* ADHOC

Maintainer
----------

This module is maintained by ADHOC
