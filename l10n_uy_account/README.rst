.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

======================
Uruguay - Contabilidad
======================

Este módulo agrega funcionalidades contables para la localización Uruguaya, que representa la configuración minima necesaria para que una compañia opere en Uruguay y bajos las regulaciones y pautas dadas por la DGI (Dirección General Impositiva). Entre las funcionalidades estan:

* Plan Contable Genérico Uruguayo
* Impuestos y Grupos de Impuestos de IVA pre configurados.
* Tipos de comprobantes legales en Uruguay.
* Tipos de identificación de contactos válidos en Uruguay.
* Posiciones fiscales.
* Adendas genéricas segun RGs para activar/usar en la validación de comprobantes.
* Configurancion y activación de Monedas Uruguayas (UYU, UYI - Unidad Idenxada Uruguaya).
* Contactos de uso frecuente por defecto ya configurados: DGI, Consumidor Final Uruguayo.
* Agregar data de provincias uruguayas.

NOTA: Este módulo agrega tando modelos como campos que seran usados eventualmente para el módulo de facturación electrónica.

Configuración
-------------

Siga los siguientes pasos para configurar en producción tras instalar el módulo.:

1. Configuración de la compañías: Ve a la compañia y configura un número de RUT y colocale pais Uruguay.
2. Instalación plan contable: Ve al menu Contabilidad / Configuración / Ajustes, en la sección Contabilidad / Localización Fiscal y selecciona el paquete  y "Plan Contable Genérico Uruguayo" y luego da click en Guardar.

    IMPORTANTE:

    1. Esta opcion solo te aparecerá si para la compania donde estas parado aun no tiene plan de cuentas instalado. Una vez instalado el plan de cuentas y facturado ya no se puede cambiar el plan de cuentas.
    2. Esta configuración depende de la compañía, por lo tanto debe asegurarse de estar posionado en la compañía donde quieres que se instale el plan de cuentas.

Demo data para pruebas:

* Compañía Uruguaya con nombre "(UY) Company" con el plan de cuentas Uruguayo ya instalado.
* Contatos uruguayos para pruebas:

   * 1 IEB Internacional
   * 2 Consumidor Final Uruguayo.

* Activamos las adendas que estaban archivadas por defecto para ser usadas en pruebas de facturación

Highlights:

* Se genera un diario de ventas por defecto de Odoo, si se quiere facturar se debe crear un nuevo diario de ventas que use documentos.

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
