import logging
from functools import reduce

from octodns.provider.base import BaseProvider
from octodns.record import *

__VERSION__ = '0.0.1'


class TerraformProvider(BaseProvider):
    SUPPORTS_GEO = True
    SUPPORTS_DYNAMIC = True
    SUPPORTS_POOL_VALUE_STATUS = True
    SUPPORTS_MULTIVALUE_PTR = True
    SUPPORTS = {'A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'DNAME', 'LOC', 'MX', 'NAPTR', 'NS', 'PTR', 'SSHFP', 'SPF', 'SRV',
                'TXT', 'URLFWD'}

    def __init__(
            self,
            id,
            directory,
            default_ttl=3600,
            enforce_order=True,
            populate_should_replace=False,
            supports_root_ns=True,
            *args,
            **kwargs,
    ):
        klass = self.__class__.__name__
        self.log = logging.getLogger(f'{klass}[{id}]')
        self.log.debug(
            '__init__: id=%s, directory=%s, default_ttl=%d, '
            'enforce_order=%d, populate_should_replace=%d',
            id,
            directory,
            default_ttl,
            enforce_order,
            populate_should_replace,
        )
        super(TerraformProvider, self).__init__(id, *args, **kwargs)
        self.directory = directory
        self.default_ttl = default_ttl
        self.enforce_order = enforce_order
        self.populate_should_replace = populate_should_replace
        self.supports_root_ns = supports_root_ns

    def populate(self, zone, target=False, lenient=False):
        return False

    def _create_record_lines_default(self, change):
        try:
            values = [change.record.data["value"]]
        except KeyError as e:
            values = change.record.data["values"]

        return f'{{ name = "{change.record.name}", type = "{change.record._type}", ttl = "{change.record.data["ttl"]}", records = {values} }}'

    def _create_record_lines_A(self, change):
        return self._create_record_lines_default(change)

    def _create_record_lines_AAAA(self, change):
        return self._create_record_lines_default(change)

    def _create_record_lines_CNAME(self, change):
        #<CnameRecord CNAME 86400, ftp.example.org., www.example.org.> (axfr)
        return self._create_record_lines_default(change)

    def _create_record_lines_MX(self, change):
        #<MxRecord MX 86400, tagesschau.org., [''50 mail.example.de.'', ''100 example.ndr.de.'', ''200 fallback.mail.de.uu.net.'']>
        try:
            # TODO: Test single MX record
            values = [change.record.data["value"]]
        except KeyError as e:
            values = change.record.data["values"]

        values = list(map(lambda v: f"{v['preference']} {v['exchange']}", values))

        return f'{{ name = "{change.record.name}", type = "{change.record._type}", ttl = "{change.record.data["ttl"]}", records = {values} }}'

    def _create_record_lines_NS(self, change):
        return self._create_record_lines_default(change)

    def _create_record_lines_TXT(self, change):
        #<TxtRecord TXT 86400, example.de., ['MS=ms59725411', 'zl/nwaDgbGnm4ks9NmjNnPooUr8ucSK9zLYSZpxK8NSpLuz87nHipqU/isXGPrEdwzq3+mSmNwUxxvEyIe7N8w==']>
        try:
            values = [change.record.data["value"]]
        except KeyError as e:
            values = change.record.data["values"]

        for value in values:
            return f'{{ name = "{change.record.name}", type = "{change.record._type}", ttl = "{change.record.data["ttl"]}", records = ["{value}"] }}'

    def _apply(self, plan):
        hcl = f"""
        module "dns-{plan.desired.name[:-1].replace(".", "-")}" {{
          source     = "terraform-google-modules/cloud-dns/google"
          version    = "4.1.0"
          project_id = var.project
          name       = {plan.desired.name[:-1].replace(".", "-")}
          domain     = {plan.desired.name}
          
          recordsets = [
        """
        for change in plan.changes:
            lines = getattr(self, f'_create_record_lines_{change.record._type}')(change)
            hcl += lines
        hcl += """
          ]
        }
        """
        with open("output.tf", "a") as f:
            f.write(hcl)
        print(hcl)

