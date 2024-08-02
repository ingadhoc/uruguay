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


* Facturas de Proveedor: permite conectarnos a Uruware para sincronizar automáticamente los comprobantes de proveedor recibidos en Uruware en el Odoo a través de una acción planificada (UY: Create vendor bills (sync from Uruware)) que se corre cada 10 minutos. Todos los comprobantes sincronizados son creados en estado "Borrador" con sus respectivos adjuntos: pdf legal y xml.

   IMPORTANTE: Siempre las facturas de proveedor son creadas en estado "Borrador" para que sean revisadas manualmente por el usuario que debe cotejar los datos de la factura de proveedor más los datos del pdf y cualquier otro mensaje detallando alguna observación o error en su mensajería.

   La configuración necesaria para poder tener esta funcionalidad es:

      1) Que la base tenga conexión a Uruware para facturación electrónica.
      2) Crear compañía uruguaya y dar de alta su correspondiente plan de cuentas.
      3) Tener creado en Odoo al menos un diario de Compras electrónico con la opción tildada "Usa Documentos". Los comprobantes de compras que sean creados en Odoo a través de la sincronización con Uruware serán registrados en este diario.
      4) En Uruware es necesario hacer una configuración que consiste en dar de alta una acción para activar notificaciones. Esto se hace en Uruware desde la consola, menú: COMPROBANTES > CFE RECIBIDOS > CONFIGURACION > ACCIONES.

         - Dar de alta la acción que crea notificaciones: botón del menú inferior ALTA:
         - Desencadenador: CFE RECIBIDO
         - Condición: NINGUNA (cualquier CFE recibido activará la generación de una notificación, en caso de que quieran ser específicos, pueden configurar la condición).
         - Acción: PERMITIR CONSULTA REGISTRO POR BANDEJA

      5) En Contabilidad / Configuración / Ajustes tener tildado "Create vendor bills from Uruware" en la sección "Localización Uruguaya" para habilitar la sincronización.

   Consideraciones a tener en cuenta:

      * Si hubo algún error en la conexión con Uruware. o en el procesado de extracción de datos del CFE por algo no contemplado en este desarrollo, quedaría igualmente creado el comprobante en estado "Borrador" pero dejaremos una nota con el mensaje de error para que sea revisado por los usuario y así pueda completar manualmente el comprobante con la información faltante/errónea.
      * Las líneas de factura siempre son creadas sin producto.
      * Si el partner de la factura no existe entonces el mismo es creado a través de esta funcionalidad.
      * Si alguna de las líneas del comprobante que se crea tiene un impuesto que no tenemos creado o no lo contemplamos entonces lo aclaramos en la línea de la factura correspondiente en la descripción.

   Técnico:

      * La sincronización la hacemos con la acción planificada a través de notificaciones que genera Uruware y que nosotros leemos desde el Odoo. Cada notificación contiene información de un comprobante en particular con el detalle del mismo en formato xml. Usamos el campo "idReq" el ID de notificación que luego usamos para obtener los datos.
      * Se lee la primera notificación disponible, se crea el comprobante correspondiente al cual la notificación hace referencia. Luego se descarta la notificación para leer la siguiente hasta que no haya más notificaciones disponibles. Si no descarta no se puede continuar leyendo el resto de los CFE recibidos (es una pila).
      * Tambíen, en la pestaña DGI está el botón "Update Fields" desde el cual se puede volver a leer el xml y analizar si puede completarse automáticamente el comprobante con la información faltante o bien hacer los arreglos correspondientes desde nuestro lado (debuggear).


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
