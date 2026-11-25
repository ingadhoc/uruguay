.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

===============================
Uruguay - Point of Sale UX
===============================

Cuando se factura una orden del punto de venta y Uruware rechaza el CFE (por ejemplo, por
falta de numeración disponible):

* No se genera el PDF de Odoo como respaldo: el único PDF válido es el que devuelve Uruware.
* La factura vuelve a borrador, para que no quede publicada sin un CFE válido. El error queda
  en el chatter de la factura.

Credits
=======

ADHOC

Contributors
------------

* ADHOC
