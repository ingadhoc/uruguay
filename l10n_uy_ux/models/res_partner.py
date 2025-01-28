import logging
from stdnum.exceptions import InvalidLength, InvalidChecksum, InvalidFormat
from lxml import etree

from odoo import _, api, fields, models

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):

    _inherit = "res.partner"

    fiscal_countries = fields.Many2many("res.country", compute="compute_fiscal_countries")

    def action_l10n_uy_is_electronic_issuer(self):
        """ Return True/False if the partner is an electronic issuer or not
        630 - Consulta si un RUT es emisor electronico """
        self.ensure_one()
        company = self.company_id or self.env.company
        # TODO KZ need to ensure that use the proper company
        edi_doc = self.env["l10n_uy_edi.document"]
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == "2":
            result = edi_doc._ucfe_inbox("630", {"RutEmisor": self.vat})

            cod_rta = False
            response = result.get("response")
            if response is not None:
                cod_rta = response.findtext(".//{*}CodRta")

            if cod_rta == "00":
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "type": "info",
                        "message": _("It is an electronic issuer"),
                        "next": {"type": "ir.actions.act_window_close"},
                    }
                }
            elif cod_rta == "01":
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "type": "danger",
                        "message": _("It is NOT an electronic issuer"),
                        "next": {"type": "ir.actions.act_window_close"},
                    }
                }
        else:
            raise UserError(_("You can only check if the partner has a RUT identification type"))

    def action_l10n_uy_get_data_from_dgi(self):
        """ 640 - Consulta a DGI por datos de RUT """
        self.ensure_one()
        company = self.company_id or self.env.companies.filtered(lambda x: x.country_id.code == 'UY')[:1]
        values = {}

        data_mapping = {
            "street": ".//{*}Calle_Nom",

            "city": ".//{*}Loc_Nom",
            "zip": ".//{*}Dom_Pst_Cod",
            "phone":
                ".//{*}WS_Domicilio.WS_DomicilioItem.Contacto"
                "[{*}TipoCtt_Des='TELEFONO FIJO']/"
                "{*}DomCtt_Val",
            "mobile":
                ".//{*}WS_Domicilio.WS_DomicilioItem.Contacto"
                "[{*}TipoCtt_Des='TELEFONO MOVIL']/"
                "{*}DomCtt_Val",
            "email":
                ".//{*}WS_Domicilio.WS_DomicilioItem.Contacto["
                "{*}TipoCtt_Des='CORREO ELECTRONICO']/"
                "{*}DomCtt_Val",

            "name": ".//{*}Denominacion",
            "ref": ".//{*}NombreFantasia",
            "street2":  ".//{*}Dom_Coment",

            # TODO remove
            "street_number": ".//{*}Dom_Pta_Nro",
            "state": ".//{*}Dpto_Nom",
        }

        # If partner has RUC
        edi_doc = self.env["l10n_uy_edi.document"]
        # TODO KZ need to ensure that use the proper company
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == "2":
            if company.l10n_uy_edi_ucfe_env == 'demo':
                raise UserError(_("UCFE enviroment is on demo. Please set a "
                                "testing enviroment to be able to connect to DGI."))
            result = edi_doc._ucfe_inbox("640", {"RutEmisor": self.vat})
            if errors := result.get('errors'):
                raise UserError(_("Could not connect to DGI to extract data %s". str(errors)))
            if response := result.get('response'):
                if response.findtext(".//{*}CodRta") == "00":
                    # TODO ver detalle de los demas campos que podemos integrar en pagin 83 Manual de integración
                    tree = etree.fromstring(response.findtext(".//{*}XmlCfeFirmado").encode('utf-8'))

                    # TODO delete after finish the tests
                    print(etree.tostring(tree, pretty_print=True))

                    values = {}
                    for odoo_field, mapping_value in data_mapping.items():
                        val = tree.findtext(mapping_value)
                        if val:
                            values.update({odoo_field: val})

                    state_name = values.pop("state")
                    state_id = state_name and self.env["res.country.state"].search(
                        [("name", "=ilike", state_name)], limit=1)

                    values["state_id"] = state_id.id or False
                    if state_id:
                        values["country_id"] = state_id.country_id.id
                    if "street" in values:
                        values["street"] += " " + values.get("street_number")

                    # Este campo no existe en odoo base, asi que tenemos que
                    # removerlo siempre del values
                    values.pop("street_number")
                elif response.findtext(".//{*}CodRta") == "01":
                    raise UserError(_("%s. Si está en un ambiente de testing, usted puede consultar los siguientes RUTs: "
                                      "219999830019, 219999820013, 219000090011", response.findtext(".//{*}MensajeRta")))
                else:
                    raise UserError(_("There was an error in the response %s", etree.tostring(response, pretty_print=True)))
        else:
            raise UserError(_("You can only check if the partner has a RUT identification type"))

        return values

    # TODO KZ From here to to bottom is a patch, we think this should be fixed directly
    # in l10n_latam_base module, if approved, then we need to move it to l10n_latam_base.
    # meanwhile we leave here as a patch
    def _get_countries(self):
        self.ensure_one()
        countries = self.env["res.country"].search([("code", "in", self.fiscal_country_codes.split(","))])
        if not countries:
            countries = self.country_id
        return countries

    @api.onchange("country_id", "company_id")
    def _onchange_country(self):
        """ Take into account the fiscal countries to filter the identification types,
        if not define ones, then use the partner country
        """
        # TODO Ahora que vamos a re-usar los tipos genericos toca ver de revisar esto, porque tenemos que tomar en cuenta los que no tienen pais,
        super()._onchange_country()
        countries = self._get_countries()
        if countries:
            identification_type = self.l10n_latam_identification_type_id
            if not identification_type or (identification_type.country_id not in countries):
                self.l10n_latam_identification_type_id = self.env["l10n_latam.identification.type"].search(
                    [("country_id", "in", countries.ids), ("is_vat", "=", True)], limit=1) or self.env.ref(
                        "l10n_latam_base.it_vat", raise_if_not_found=False)

    # Do not remember
    @api.onchange("company_id")
    def compute_fiscal_countries(self):
        """ Esto es usado en la vista para poder filtrar correctamente los tipos de documentos, En odoo oficial solo
        puedes ver los tipos de documento  """
        for rec in self:
            rec.fiscal_countries = rec._get_countries()

    """ TODO KZ despues que se mezcle el pr de check vat, agregar esto
    def check_vat(self, vat):
        # NOTE by the moment we include the RUT (VAT UY) validation also here because we extend the messages errors to be
        # more friendly to the user. In a future when Odoo improve the base_vat message errors  we can change
        # this method and use the base_vat.check_vat_uy method instead.
        valid = super().check_vat_uy()
        if not valid and vat:
            self._l10n_uy_edi_check_ruc_rut(vat)
        return valid

    @api.model
    def _l10n_uy_edi_check_ruc_rut(self, vat):
        # Check if the VAT is valid.
        # Return: False if valid vat number, a msg containing the error if not
        # NOTE: This method is only to add more info to the error
        # TODO this will not work we need to improved to properly show message error
        msg = False
        try:
            stdnum.util.get_cc_module("uy", "rut").validate(vat)
        except ImportError:
            _logger.warning("Urugayan RUT/RUC can not be validated (missing stnum lib)")
        except InvalidChecksum:
            msg = _("The validation digit is not valid")
        except InvalidLength:
            msg = _("Invalid length")
        except InvalidFormat:
            msg = _("Only numbers allowed")

        return msg
    """
