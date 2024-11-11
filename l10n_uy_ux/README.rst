.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

==========
Uruguay UX
==========

En este modulo agregamos:

1. Adaptaciones y cosas que no han sido aceptadas por Odoo modulo oficial, pero que nos interesa la funcionalidad se mantenga para nuestros clientes.
2. Cosas que estamos agregando como beta a nuestros clientes, si va todo bien luego las pasamos a Odoo

**Funcionalidades:**

* Almacenar dato de conexion a Uruware de test y de producción. Odoo oficial solo permite tener configurado un dato, con este cambio almacenamos ambos datos, y el usuario o soporte solo necesita cambiar en ajustes la opción producción o testing sin tener que hacer configuraciones o modificaciones extra.

* Padron DGI: Permite consultar los datos de un contacto en su Odoo, si este es o no emisor electronico, y los datos de padron como asistente para que les permita llenar los datos del contacto de manera mas sencilla en su odoo.

* Para la representacion impresa legal de una factura electronica uruguaya la obtenemos desde Uruware con modulo oficial al validar la factura en DGI (no implementado aun como reporte en Odoo), pero tiene un par de problemas

  1) si por alguna razon el pdf no se crea o se borra no tenemos opcion de recuperarlo de volver a attacharlo a la factura,
  2) los botones de imprimir factura de odoo generan el reporte pdf de odoo y no el pdf legal,

  En este modulo siempre imprimimos el pdf legal

  1. accion imprimir factura y facturas sin pagos
  2. opcion boton enviar e imprimir
  3. envio automatico al validar la factura segun configuracion del diario

* Parametros de Reporte: Modulo oficial imprime solo la representacion standard del reporte, en este modulo extendenmos para que

  1. Si vemos que la addenda del comprobante supera las 6 lineas, mandamos a imprimir el reporte pdf con adenda en hoja separada para evitar que salga cortada
  2. Si es un e-factura o e-factura expo y el receptor tiene configurado un idioma != a español imprimimos el reporte en ingles y español
  3. Agregamos un parametro a nivel de compania en los ajustes de sistemas que permite al usuario definir de manera global que todos los pds se generen siguiendo x formato (adenda separada siempre, ingles siempre, detalle de lineas, rollo, etc) o incluso imprimir un reporte personalizado.

* Agregamos funcionalidad para ver el Preview del xml en todo momento (no solo si estamos en demo mode o si ocurrio un error). Agregamos tambien el boton de Validar XML para tema de pruebas.

* Agregar mas logica a las Addendas y Leyendas Obligatorias:

  * Defaults del sistema: agrega un campo condicion el cual ayuda a aplicar la adenda al comprobante si es te cumple con dicha condición.
  * Previsualizar: boton que permite ver como quedan antes de enviarlas.

* Permitir desde un diario de Ventas manual poder traer facturas creadas en Uruware. Si el usuario carga el UUID y da click al boton Obtener Factura Uruware traera automaticamente el numero de docuemnto, tipo de docuemnto, estado dgi y pdf legal.

* En ajustes agregamos campos para almacenar como datos informativo el Certificado DGI y clave asociada, asi tenerlo de respaldo para configurarlos en Uruware prod/test en caso de ser necesario


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
