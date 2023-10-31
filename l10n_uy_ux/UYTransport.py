from lxml import etree
from odoo.tools.zeep import Transport


class UYTransport(Transport):

    def post(self, address, message, headers):
        """ We overwrite this method only to be able to save the xml request and response.
        This will only affect the connections that are made in this field and it does not extend the original
        Transport class of zeep package.

        NOTE: we try using the HistoryPlugin to save the xml request/response but seems this one could have problems
        when using with multi thread/workers"""
        response = super().post(address, message, headers)
        self.xml_request = etree.tostring(
            etree.fromstring(message), pretty_print=True).decode('utf-8')
        self.xml_response = etree.tostring(
            etree.fromstring(response.content), pretty_print=True).decode('utf-8')
        return response
