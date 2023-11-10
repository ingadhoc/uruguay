.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=================================
Uruguay - Facturacion Electronica
=================================

Este modulo permite la integración para que desde su base de Odoo se puedan emitir comprobantes electrónicos a la DGI (comprobantes del tipo ticket/facturas en todas sus variantes y sus respectivas nd/nc).

A demás de emitir el comprobante permite conectarse a la DGI para ver el estado del comprobante (si este fue rechazado o aprobado) ** esto porque la validacion electronica es asincrona

Permite consultar los datos de un contacto en su odoo, si este es o no emisor electronico, y los datos de padron como asistente para que les permita llenar los datos del contacto de manera mas sencilla en su odoo.

NOTA: Todas estas conexiones se hacen a traves de un servicio de tercero llamado Uruware

Este módulo también permite conectarnos a Uruware para sincronizar automáticamente los comprobantes de proveedor recibidos en Uruware en el Odoo a través de una acción planificada (UY: Create vendor bills (sync from Uruware)) que se corre cada 10 minutos. Todos los comprobantes sincronizados son creados en estado "Borrador" con sus respectivos adjuntos: pdf legal y xml.

IMPORTANTE: Siempre las facturas de proveedor son creadas en estado "Borrador" para que sean revisadas manualmente por el usuario que debe cotejar los datos de la factura de proveedor más los datos del pdf y cualquier otro mensaje detallando alguna observación o error en su mensajería.

La configuración necesaria para poder tener esta funcionalidad es:

   1) Que la base tenga conexión a Uruware para facturación electrónica.
   2) Crear compañía uruguaya y dar de alta su correspondiente plan de cuentas.
   3) Tener creado en Odoo al menos un diario de Compras electrónico con la opción tildada "Usa Documentos". Los comprobantes de compras que sean creados en Odoo a través de la sincronización con Uruware serán registrados en este diario.
   4) En Contabilidad / Configuración / Ajustes tener tildado "Create vendor bills from Uruware" en la sección "Localización Uruguaya" para habilitar la sincronización.

Consideraciones a tener en cuenta:

   * Si hubo algún error en la conexión con Uruware. o en el procesado de extracción de datos del CFE por algo no contemplado en este desarrollo, quedaría igualmente creado el comprobante en estado "Borrador" pero dejaremos una nota con el mensaje de error para que sea revisado por los usuario y así pueda completar manualmente el comprobante con la información faltante/errónea.
   * Las líneas de factura siempre son creadas sin producto.
   * Si el partner de la factura no existe entonces el mismo es creado a través de esta funcionalidad.
   * Si alguna de las líneas del comprobante que se crea tiene un impuesto que no tenemos creado o no lo contemplamos entonces lo aclaramos en la línea de la factura correspondiente en la descripción.

Técnico:

   * La sincronización la hacemos con la acción planificada a través de notificaciones que genera Uruware y que nosotros leemos desde el Odoo. Cada notificación contiene información de un comprobante en particular con el detalle del mismo en formato xml. Usamos el campo "idReq" el ID de notificación que luego usamos para obtener los datos.
   * Se lee la primera notificación disponible, se crea el comprobante correspondiente al cual la notificación hace referencia. Luego se descarta la notificación para leer la siguiente hasta que no haya más notificaciones disponibles. Si no descarta no se puede continuar leyendo el resto de los CFE recibidos (es una pila).
   * Tambíen, en la pestaña DGI está el botón "Update Fields" desde el cual se puede volver a leer el xml y analizar si puede completarse automáticamente el comprobante con la información faltante o bien hacer los arreglos correspondientes desde nuestro lado (debuggear).

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
