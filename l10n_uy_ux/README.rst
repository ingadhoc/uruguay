.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

==========
Uruguay UX
==========

En este modulo agregamos:

1. adaptaciones y cosas que no han sido aceptadas por Odoo modulo oficial, pero que nos interesa la funcionalidad se mantenga para nuestros clientes.
2. Cosas que estamos agregando como beta a nuestros clientes, si va todo bien luego las pasamos a Odoo

**Funcionalidades:**

* Padron DGI: Permite consultar los datos de un contacto en su odoo, si este es o no emisor electronico, y los datos de padron como asistente para que les permita llenar los datos del contacto de manera mas sencilla en su odoo.

   * Boton para manualmente actualizar/checar estado de DGI de un comprobante
   * En ajustes tenemos campos para almacenar como data informativo el certificado DGI y clave asociada, asi tenerlo de respaldo para configurarlos en Uruware prod/test

* Para la representacion impresa legal de una factura electronica uruguaya la obtenemos desde Uruware con modulo oficial al validar la factura en DGI (no implementado aun como reporte en Odoo), pero tiene un par de problemas 1) si por alguna razon el pdf no se crea o se borra no tenemos opcion de recuperarlo de volver a attacharlo a la factura, 2) los botones de imprimir factura de odoo generan el reporte pdf de odoo y no el pdf legal, en este modulo siempre imprimimos el pdf legal

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
