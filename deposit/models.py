# -*- encoding: utf-8 -*-

# Dissemin: open access policy enforcement tool
# Copyright (C) 2014 Antonin Delpeuch
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#


from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext_lazy as _

from django.db import models
from papers.models import Paper, OaiSource
from django.contrib.auth.models import User
from upload.models import UploadedPDF
from deposit.protocol import *
from deposit.registry import *

DEPOSIT_STATUS_CHOICES = [
   ('created', _('Created')),
   ('metadata_defective', _('Metadata defective')),
   ('document_defective', _('Document defective')),
   ('deposited', _('Deposited')),
   ]

class Repository(models.Model):
    """
    This stores the parameters for a particular repository.
    """
    #: Name
    name = models.CharField(max_length=64)
    #: Description
    description = models.TextField()
    #: URL of the homepage (ex: http://arxiv.org/ )
    url = models.URLField(max_length=256, null=True, blank=True)
    #: Logo
    logo = models.ImageField(upload_to='repository_logos/')

    # The identifier of the interface (protocol) used for that repository
    protocol = models.CharField(max_length=32)
    # The source with which the OaiRecords associated with the deposits are created
    oaisource = models.ForeignKey(OaiSource)
    
    # The identifier of the account under which papers should be deposited
    username = models.CharField(max_length=64, null=True, blank=True)
    # The password for that account
    password = models.CharField(max_length=128, null=True, blank=True)
    # An API key required by the protocol
    api_key = models.CharField(max_length=256, null=True, blank=True)
    # The API's endpoint
    endpoint = models.CharField(max_length=256, null=True, blank=True)

    #: Setting this to false forbids any deposit in this repository
    enabled = models.BooleanField(default=True)

    def get_implementation(self):
        """
        Returns an instance of the class corresponding to the protocol identifier,
        bound with this repository.
        """
        cls = protocol_registry.get(self.protocol)
        if cls is None:
            return
        return cls(self)

    def protocol_for_deposit(self, paper, user):
        """
        Returns an instance of the protocol initialized for the given
        paper and user, if initialization succeeded.
        """
        if not self.enabled:
            return
        instance = self.get_implementation()
        if instance is None:
            return
        if instance.init_deposit(paper, user):
            return instance

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Repositories'

class DepositRecord(models.Model):
    paper = models.ForeignKey(Paper)
    user = models.ForeignKey(User)

    repository = models.ForeignKey(Repository)

    request = models.TextField(null=True, blank=True)
    identifier = models.CharField(max_length=512, null=True, blank=True)
    #deposition id on zenodo/hal/whatever
    pdf_url = models.URLField(max_length=1024, null=True, blank=True)
    date = models.DateTimeField(auto_now=True) # deposit date
    upload_type = models.CharFile = models.FileField(upload_to='deposits')

    file = models.ForeignKey(UploadedPDF)

    class Meta:
        db_table = 'papers_depositrecord'

    def __unicode__(self):
        if self.identifier:
            return self.identifier
        else:
            return unicode(_('Deposit'))


