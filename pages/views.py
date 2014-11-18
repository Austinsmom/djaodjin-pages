# Copyright (c) 2014, DjaoDjin inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from bs4 import BeautifulSoup
from django.views.generic import TemplateView
from pages.models import PageElement
from django.template.response import TemplateResponse
import markdown, re
from django.template.loader import find_template_loader
from django.template.base import TemplateDoesNotExist
from .mixins import AccountMixin

from .settings import USE_S3
from django.conf import settings

from pages.encrypt_path import encode

class PageView(AccountMixin, TemplateView):
    """
    Display or Edit a ``Page`` of a ``Project``.

    """
    http_method_names = ['get']

    def get_template_path(self):
        #pylint: disable=unused-variable
        loaders = []
        for loader_name in settings.TEMPLATE_LOADERS:
            loader = find_template_loader(loader_name)
            if loader is not None:
                loaders.append(loader)
        for loader in loaders:
            try:
                source, display_name = loader.load_template_source(
                    self.get_template_names()[0])
                break
            except TemplateDoesNotExist:
                source = (
                    "Template Does Not Exist: %s"\
                    % (self.get_template_names()[0]))
        return display_name

    def get_context_data(self, **kwargs):
        context = super(PageView, self).get_context_data(**kwargs)
        context.update({'template_path': encode(self.get_template_path())})
        return context

    def get(self, request, *args, **kwargs):#pylint: disable=too-many-statements
        response = super(PageView, self).get(request, *args, **kwargs)
        if self.template_name and isinstance(response, TemplateResponse):
            response.render()
            soup = BeautifulSoup(response.content)
            account = self.get_account()
            if account:
                page_elements = PageElement.objects.filter(account=account)
            else:
                page_elements = PageElement.objects.all()
            for editable in soup.find_all(class_="editable"):
                try:
                    id_element = editable['id']
                except KeyError:
                    continue
                try:
                    if account:
                        edit = page_elements.get(
                            slug=id_element, account=account)
                        # edit = edit.get(account=account)
                    else:
                        edit = page_elements.get(slug=id_element)
                    new_text = re.sub(r'[\ ]{2,}', '', edit.text)
                    if 'edit-markdown' in editable['class']:
                        new_text = markdown.markdown(new_text)
                        new_text = BeautifulSoup(new_text)
                        editable.name = 'div'
                        editable.string = ''
                        children_done = []
                        for element in new_text.find_all():
                            if element.name != 'html' and\
                                element.name != 'body':
                                if len(element.findChildren()) > 0:
                                    element.append(element.findChildren()[0])
                                    children_done += [element.findChildren()[0]]
                                if not element in children_done:
                                    editable.append(element)
                    else:
                        editable.string = new_text
                except PageElement.DoesNotExist:
                    pass

            #load all media pageelemeny
            db_medias = page_elements.filter(slug__startswith='djmedia-')
            for media in soup.find_all(class_="droppable-image"):
                try:
                    id_element = media['id']
                except KeyError:
                    continue
                try:
                    # db_image = PageElement.objects.filter(slug=id_element)
                    account = self.get_account()
                    if account:
                        db_media = db_medias.get(
                            slug=id_element, account=account)
                    else:
                        db_media = db_medias.get(slug=id_element)
                    if USE_S3:
                        media['src'] = db_media.text
                    else:
                        media['src'] = db_media.text
                except:#pylint: disable=bare-except
                    continue
            response.content = soup.prettify()
        return response
