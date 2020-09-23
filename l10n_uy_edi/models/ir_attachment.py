# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import io
import logging
import requests
import zipfile
from os.path import join
from lxml import etree, objectify

from odoo import models, tools

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):

    _inherit = 'ir.attachment'

    def _extract_dgi_xsd_from_zip(self, url, response, file_name=None):
        """ This method is used to extract file from DGI's XSD zipfile """
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        file = ''
        for file_path in archive.namelist():
            if file_name in file_path:
                file = file_path
                break
        try:
            return archive.open(file).read()
        except KeyError as e:
            _logger.info(e)
            return ''

    def _modify_and_validate_dgi_xsd_content(self, content):
        """
        :return object: returns ObjectifiedElement.
        :param content: file content as bytes
        """
        try:
            return objectify.fromstring(content)
        except etree.XMLSyntaxError as e:
            _logger.warning('You are trying to load an invalid xsd file.\n%s', e)
            return ''
