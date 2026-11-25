.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

==========================
Uruguay - Point of Sale UX
==========================

Cuando se factura una orden del punto de venta y Uruware rechaza el CFE (por ejemplo, por
falta de numeración disponible o por datos incompletos del receptor):

* No se genera el PDF de Odoo como respaldo: el único PDF válido es el que devuelve Uruware.
* La factura vuelve a borrador, para que no quede publicada sin un CFE válido. El error queda
  en el chatter de la factura. Esto aplica también a los errores que se detectan antes de
  enviar (por ejemplo, faltan datos del receptor para un importe mayor al tope).
* Si el rechazo vino de Uruware, la sesión pasa sola a modo contingencia (``pos_ux``) y el cajero ve un aviso con el motivo.
  Mientras dure la contingencia, la caja sigue vendiendo sin facturar y no descarga facturas.
* Las facturas pendientes se generan después, con el botón "Generate invoices" de la sesión.

Credits
=======

ADHOC

Contributors
------------

* ADHOC
