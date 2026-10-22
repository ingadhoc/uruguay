.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: https://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

===================
Uruguay - E-Remitos
===================

Este módulo extiende los e-Remitos de Odoo (``l10n_uy_edi_stock``) con tres botones en la pestaña "UY EDI" de la transferencia validada:

* **Preview**: muestra el XML del CFE que se enviaría a la DGI, antes de generar el e-Remito.
* **Validate**: valida la estructura de ese XML contra Uruware (consulta 350), sin emitir el e-Remito. Si Uruware no responde o falta configuración, muestra el error.
* **Get PDF**: vuelve a pedir a Uruware el PDF de un e-Remito aceptado o recibido, si no se generó o se borró.

Además muestra la transferencia relacionada en el formulario del documento EDI.

NOTA: Todas estas conexiones se hacen a través de un servicio de tercero llamado Uruware

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
