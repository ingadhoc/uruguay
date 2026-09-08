.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

======================================
Uruguay - CFE Special Taxpayer Regimes
======================================

Este módulo permite emitir CFE válidos para compañías bajo régimen especial de DGI
(Literal E / IVA mínimo o monotributo).

Cuando la compañía está bajo un régimen especial, Uruware firma los CFE con un CAE especial
(valores 2, 3 o 4) y DGI exige que el comprobante cumpla dos condiciones que el módulo estándar
``l10n_uy_edi`` no contempla:

* Indicador de montos brutos ``MntBruto = 3`` (zona A10 del encabezado).
* Indicador de facturación ``IndFact = 16`` (IVA mínimo, Monotributo u otros) en lugar de los
  indicadores de tasa de IVA (1 exento, 2 tasa mínima, 3 tasa básica, 4 otra tasa). Los
  indicadores conceptuales se siguen usando igual que en el régimen general: 5 (entrega
  gratuita), 6/7 (no facturable, ej. anticipos y líneas de descuento) y 10 (exportación) —
  confirmado por Uruware.

Sin estos indicadores DGI rechaza el comprobante con el error
*"Si el valor del CAE Especial es 2, 3 o 4 entonces el Ind. Mnt Bruto debe ser 3"* (código 05,
rechazo definitivo que quema el número de CAE).

El indicador ``MntBruto = 3`` aplica a todos los tipos de CFE que emite la compañía —
e-Ticket (101), e-Factura (111), sus notas de crédito y débito (102, 103, 112, 113) y también
los CFE de exportación (121, 122, 123): el CAE especial es una propiedad del contribuyente, por
lo que Uruware firma todos los comprobantes con él y DGI exige el indicador en todos. Las líneas
de exportación conservan su indicador de facturación propio (``IndFact = 10``).

Además, el módulo valida que las líneas del comprobante no tengan IVA a tasa distinta de 0%
(exento): al confirmar la factura se le avisa al usuario con un error bloqueante, y el mismo
chequeo corre antes del envío. Cada rechazo de DGI quema un número de CAE, por lo que conviene
frenar el error en Odoo lo antes posible.

Configuración
-------------

#. En Odoo: en la compañía, campo **Régimen de contribuyente DGI**, seleccionar el régimen que
   corresponda (por defecto: régimen general, que no cambia ningún comportamiento).
#. En Uruware: menú **Empresa** → sección **Información Extra** → marcar **"Literal E o
   monotributo"** en *Sí*. Sin esta configuración Uruware no firma con el CAE especial.

Ambas configuraciones deben estar alineadas: son espejo una de la otra.

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
