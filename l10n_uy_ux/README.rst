.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

============
Uruguay - UX
============

Aca agregamos adaptaciones y cosas que no han sido aceptadas por Odoo modulo oficial.

Pero que nos interesa la funcionalidad se mantenga para nuestros clientes.

* Padron DGI: Permite consultar los datos de un contacto en su odoo, si este es o no emisor electronico, y los datos de padron como asistente para que les permita llenar los datos del contacto de manera mas sencilla en su odoo.

* Boton para manualmente actualizar/checar estado de DGI de un comprobante
* En ajustes tenemos campos para almacenar como data informativo el certificado DGI y clave asociada, asi tenerlo de respaldo para configurarlos en Uruware prod/test

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
