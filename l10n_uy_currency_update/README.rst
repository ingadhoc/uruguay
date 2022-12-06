.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

==============================
Uruguayan Currency Rate Update
==============================

Este modulo genera la conexión con el webservice del BCU (Banco Central Uruguayo - proveedor oficial en Uruguay) para obtener de automaticamente las cotizaciones de las monedas que esten activas en su Odoo.

En caso de no querer utilizar este modulo pueden consultar las cotizaciones en esta pagina y luego crearlas manualmente en su Odoo https://www.bcu.gub.uy/Estadisticas-e-Indicadores/Paginas/Cotizaciones.aspx

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. By default the automatic rate updates are inactive, you can active them by company by going to
   *Accounting / Configuration / Settings* menu and there found and set the *Interval* and *Next Run*
   date in the *Automatic Currency Rates* section (don't forget to click Save button) When activated, the
   currency rates of your companies will be updated automatically. We recommend to use daily interval
   since BCU update the rates daily.

#. Already configured to update currency rates one per day, you can change
   this configurations going to General Settings / Invoicing / Automatic
   currency Rates section.

Usage
=====

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/uruguay/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Testing and Development
=======================

URLS webservices used in this module:

* get rates https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcucotizaciones
* get currency names and codes https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcumonedas
* get last date rates were updated https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsultimocierre

For technical questions about the ws we can sent a emial to mesadeayuda@bcu.gub.uy

Credits
=======

Images
------

* |company| |icon|

Contributors
------------

Maintainer
----------

|company_logo|

This module is maintained by the |company|.

To contribute to this module, please visit https://www.adhoc.com.ar.
