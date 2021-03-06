#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Test the Report Queries."""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from tenant_schemas.utils import tenant_context

from api.iam.test.iam_test_case import IamTestCase
from api.models import Customer, Tenant
from api.report.queries import ReportQueryHandler
from reporting.models import (AWSCostEntry,
                              AWSCostEntryBill,
                              AWSCostEntryLineItem,
                              AWSCostEntryPricing,
                              AWSCostEntryProduct)


class ReportQueryUtilsTest(TestCase):
    """Test the report query class functions."""

    def test_next_month(self):
        """Test the next_month method."""
        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        last_month = current_month.replace(month=(current_month.month - 1))
        self.assertEqual(current_month,
                         ReportQueryHandler.next_month(last_month))

    def test_previous_month(self):
        """Test the previous_month method."""
        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        last_month = current_month.replace(month=(current_month.month - 1))
        self.assertEqual(last_month,
                         ReportQueryHandler.previous_month(current_month))

    def test_list_days(self):
        """Test the list_days method."""
        first = timezone.now().replace(microsecond=0,
                                       second=0,
                                       minute=0,
                                       hour=0,
                                       day=1)
        second = first.replace(day=2)
        third = first.replace(day=3)
        expected = [first, second, third]
        self.assertEqual(expected, ReportQueryHandler.list_days(first, third))

    def test_n_days_ago(self):
        """Test the n_days_ago method."""
        delta_day = datetime.timedelta(days=1)
        today = timezone.now().replace(microsecond=0,
                                       second=0,
                                       minute=0,
                                       hour=0)
        two_days_ago = (today - delta_day) - delta_day
        self.assertEqual(two_days_ago,
                         ReportQueryHandler.n_days_ago(today, 2))

    def test_has_wildcard_yes(self):
        """Test a list has a wildcard."""
        result = ReportQueryHandler.has_wildcard(['abc', '*'])
        self.assertTrue(result)

    def test_has_wildcard_no(self):
        """Test a list doesn't have a wildcard."""
        result = ReportQueryHandler.has_wildcard(['abc', 'def'])
        self.assertFalse(result)

    def test_has_wildcard_none(self):
        """Test an empty list doesn't have a wildcard."""
        result = ReportQueryHandler.has_wildcard([])
        self.assertFalse(result)

    def test_group_data_by_list(self):
        """Test the _group_data_by_list method."""
        group_by = ['account', 'service']
        data = [{'account': 'a1', 'service': 's1', 'units': 'USD', 'total': 4},
                {'account': 'a1', 'service': 's2', 'units': 'USD', 'total': 5},
                {'account': 'a2', 'service': 's1', 'units': 'USD', 'total': 6},
                {'account': 'a2', 'service': 's2', 'units': 'USD', 'total': 5},
                {'account': 'a1', 'service': 's3', 'units': 'USD', 'total': 5}]
        out_data = ReportQueryHandler._group_data_by_list(group_by, 0, data)
        expected = {'a1':
                    {'s1': [{'account': 'a1', 'service': 's1', 'units': 'USD', 'total': 4}],
                     's2': [{'account': 'a1', 'service': 's2', 'units': 'USD', 'total': 5}],
                        's3': [
                        {'account': 'a1', 'service': 's3', 'units': 'USD', 'total': 5}]},
                    'a2':
                    {'s1': [{'account': 'a2', 'service': 's1', 'units': 'USD', 'total': 6}],
                        's2': [{'account': 'a2', 'service': 's2', 'units': 'USD', 'total': 5}]}}
        self.assertEqual(expected, out_data)


class ReportQueryTest(IamTestCase):
    """Tests the report queries."""

    def setUp(self):
        """Set up the customer view tests."""
        super().setUp()
        self.create_service_admin()
        customer = self.customer_data[0]
        response = self.create_customer(customer)
        self.assertEqual(response.status_code, 201)
        customer_json = response.json()
        customer_uuid = customer_json.get('uuid')
        customer_obj = Customer.objects.filter(uuid=customer_uuid).get()
        self.tenant = Tenant(schema_name=customer_obj.schema_name)
        self.tenant.save()
        self.add_data_to_tenant()

    def create_hourly_instance_usage(self, payer_account_id, bill,
                                     ce_pricing, ce_product, rate,
                                     cost, start_hour, end_hour):
        """Create houlr instance usage."""
        cost_entry = AWSCostEntry(interval_start=start_hour,
                                  interval_end=end_hour,
                                  bill=bill)
        cost_entry.save()
        line_item = AWSCostEntryLineItem(invoice_id=self.fake.sha1(raw_output=False),
                                         line_item_type='Usage',
                                         usage_account_id=payer_account_id,
                                         usage_start=start_hour,
                                         usage_end=end_hour,
                                         product_code='AmazonEC2',
                                         usage_type='BoxUsage:c4.xlarge',
                                         operation='RunInstances',
                                         availability_zone='us-east-1a',
                                         resource_id='i-{}'.format(self.fake.ean8()),
                                         usage_amount=1,
                                         currency_code='USD',
                                         unblended_rate=rate,
                                         unblended_cost=cost,
                                         blended_rate=rate,
                                         blended_cost=cost,
                                         cost_entry=cost_entry,
                                         cost_entry_bill=bill,
                                         cost_entry_product=ce_product,
                                         cost_entry_pricing=ce_pricing)
        line_item.save()

    def add_data_to_tenant(self):
        """Populate tenant with data."""
        payer_account_id = self.fake.ean(length=13)  # pylint: disable=no-member
        self.payer_account_id = payer_account_id
        one_day = datetime.timedelta(days=1)
        one_hour = datetime.timedelta(minutes=60)
        this_hour = timezone.now().replace(microsecond=0, second=0, minute=0)
        yesterday = this_hour - one_day
        bill_start = this_hour.replace(microsecond=0, second=0, minute=0, hour=0, day=1)
        bill_end = ReportQueryHandler.next_month(bill_start)
        with tenant_context(self.tenant):
            bill = AWSCostEntryBill(bill_type='Anniversary',
                                    payer_account_id=payer_account_id,
                                    billing_period_start=bill_start,
                                    billing_period_end=bill_end)
            bill.save()
            rate = 0.199
            amount = 1
            cost = rate * amount
            # pylint: disable=no-member
            sku = self.fake.pystr(min_chars=12, max_chars=12).upper()
            prod_ec2 = 'Amazon Elastic Compute Cloud'
            ce_product = AWSCostEntryProduct(sku=sku,
                                             product_name=prod_ec2,
                                             product_family='Compute Instance',
                                             service_code='AmazonEC2',
                                             region='US East (N. Virginia)',
                                             instance_type='c4.xlarge',
                                             memory=7.5,
                                             vcpu=4)
            ce_product.save()
            ce_pricing = AWSCostEntryPricing(public_on_demand_cost=rate * 1,
                                             public_on_demand_rate=rate,
                                             term='OnDemand',
                                             unit='Hrs')
            ce_pricing.save()
            current = yesterday
            while current < this_hour:
                end_hour = current + one_hour
                self.create_hourly_instance_usage(payer_account_id, bill,
                                                  ce_pricing, ce_product, rate,
                                                  cost, current, end_hour)
                current = end_hour

    def test_has_filter_no_filter(self):
        """Test the has_filter method with no filter in the query params."""
        handler = ReportQueryHandler({}, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertFalse(handler.check_query_params('filter', 'time_scope_value'))

    def test_has_filter_with_filter(self):
        """Test the has_filter method with filter in the query params."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertIsNotNone(handler.check_query_params('filter', 'time_scope_value'))

    def test_get_group_by_no_data(self):
        """Test the get_group_by_data method with no data in the query params."""
        handler = ReportQueryHandler({}, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertFalse(handler.get_group_by_data('service'))

    def test_get_group_by_with_service_list(self):
        """Test the get_group_by_data method with no data in the query params."""
        expected = ['a', 'b']
        query_string = '?group_by[service]=a&group_by[service]=b'
        handler = ReportQueryHandler({'group_by':
                                      {'service': expected}},
                                     query_string,
                                     self.tenant,
                                     'unblended_cost',
                                     'currency_code')
        service = handler.get_group_by_data('service')
        self.assertEqual(expected, service)

    def test_get_resolution_empty_default(self):
        """Test get_resolution returns default when query params are empty."""
        query_params = {}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_resolution(), 'daily')
        self.assertEqual(handler.get_resolution(), 'daily')

    def test_get_resolution_empty_month_time_scope(self):
        """Test get_resolution returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -1}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_resolution(), 'monthly')

    def test_get_resolution_empty_day_time_scope(self):
        """Test get_resolution returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -10}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_resolution(), 'daily')

    def test_get_time_scope_units_empty_default(self):
        """Test get_time_scope_units returns default when query params are empty."""
        query_params = {}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_time_scope_units(), 'day')
        self.assertEqual(handler.get_time_scope_units(), 'day')

    def test_get_time_scope_units_empty_month_time_scope(self):
        """Test get_time_scope_units returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -1}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_time_scope_units(), 'month')

    def test_get_time_scope_units_empty_day_time_scope(self):
        """Test get_time_scope_units returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -10}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_time_scope_units(), 'day')

    def test_get_time_scope_value_empty_default(self):
        """Test get_time_scope_value returns default when query params are empty."""
        query_params = {}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_time_scope_value(), -10)
        self.assertEqual(handler.get_time_scope_value(), -10)

    def test_get_time_scope_value_empty_month_time_scope(self):
        """Test get_time_scope_value returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_units': 'month'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_time_scope_value(), -1)

    def test_get_time_scope_value_empty_day_time_scope(self):
        """Test get_time_scope_value returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_units': 'day'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        self.assertEqual(handler.get_time_scope_value(), -10)

    def test_get_time_frame_filter_current_month(self):
        """Test _get_time_frame_filter for current month."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -1,
                         'time_scope_units': 'month'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        next_month = ReportQueryHandler.next_month(current_month)
        start = handler.start_datetime
        end = handler.end_datetime
        interval = handler.time_interval
        self.assertEqual(start, current_month)
        self.assertEqual(end, next_month)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) >= 28)

    def test_get_time_frame_filter_previous_month(self):
        """Test _get_time_frame_filter for previous month."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -2,
                         'time_scope_units': 'month'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        prev_month = ReportQueryHandler.previous_month(current_month)
        start = handler.start_datetime
        end = handler.end_datetime
        interval = handler.time_interval
        self.assertEqual(start, prev_month)
        self.assertEqual(end, current_month)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) >= 28)

    def test_get_time_frame_filter_last_ten(self):
        """Test _get_time_frame_filter for last ten days."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -10,
                         'time_scope_units': 'day'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        current_day = timezone.now().replace(microsecond=0,
                                             second=0,
                                             minute=0)
        ten_days_ago = ReportQueryHandler.n_days_ago(current_day, 10)
        start = handler.start_datetime
        end = handler.end_datetime
        interval = handler.time_interval
        self.assertEqual(start, ten_days_ago)
        self.assertEqual(end, current_day)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) == 11)

    def test_get_time_frame_filter_last_thirty(self):
        """Test _get_time_frame_filter for last thirty days."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -30,
                         'time_scope_units': 'day'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        current_day = timezone.now().replace(microsecond=0,
                                             second=0,
                                             minute=0)
        ten_days_ago = ReportQueryHandler.n_days_ago(current_day, 30)
        start = handler.start_datetime
        end = handler.end_datetime
        interval = handler.time_interval
        self.assertEqual(start, ten_days_ago)
        self.assertEqual(end, current_day)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) == 31)

    def test_execute_query_current_month_daily(self):
        """Test execute_query for current month on daily breakdown."""
        query_params = {'filter':
                        {'resolution': 'daily', 'time_scope_value': -1,
                         'time_scope_units': 'month'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('value'))
        self.assertEqual(total.get('value'), Decimal('4.776000000'))

    def test_execute_query_current_month_monthly(self):
        """Test execute_query for current month on monthly breakdown."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'}}
        handler = ReportQueryHandler(query_params, '', self.tenant, 'unblended_cost',
                                     'currency_code')
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('value'))
        self.assertEqual(total.get('value'), Decimal('4.776000000'))

    def test_execute_query_current_month_by_service(self):
        """Test execute_query for current month on monthly breakdown by service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'service': ['*']}}
        handler = ReportQueryHandler(query_params, '?group_by[service]=*',
                                     self.tenant, 'unblended_cost',
                                     'currency_code')
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('value'))
        self.assertEqual(total.get('value'), Decimal('4.776000000'))

        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        cmonth_str = current_month.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('services')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                compute = month_item.get('service')
                self.assertEqual(compute, 'Compute Instance')
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_by_filtered_service(self):
        """Test execute_query monthly breakdown by filtered service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'service': ['Compute Instance']}}
        handler = ReportQueryHandler(query_params, '?group_by[service]=Compute Instance',
                                     self.tenant, 'unblended_cost',
                                     'currency_code')
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('value'))
        self.assertEqual(total.get('value'), Decimal('4.776000000'))

        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        cmonth_str = current_month.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('services')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                compute = month_item.get('service')
                self.assertEqual(compute, 'Compute Instance')
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_current_month_by_account(self):
        """Test execute_query for current month on monthly breakdown by account."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*']}}
        handler = ReportQueryHandler(query_params, '?group_by[account]=*',
                                     self.tenant, 'unblended_cost',
                                     'currency_code')
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('value'))
        self.assertEqual(total.get('value'), Decimal('4.776000000'))

        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        cmonth_str = current_month.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                account = month_item.get('account')
                self.assertEqual(account, self.payer_account_id)
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_by_account_by_service(self):
        """Test execute_query for current month breakdown by account by service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*'],
                                     'service': ['*']}}
        query_string = '?group_by[account]=*&group_by[service]=Compute Instance'
        handler = ReportQueryHandler(query_params, query_string,
                                     self.tenant, 'unblended_cost',
                                     'currency_code')
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('value'))
        self.assertEqual(total.get('value'), Decimal('4.776000000'))

        current_month = timezone.now().replace(microsecond=0,
                                               second=0,
                                               minute=0,
                                               hour=0,
                                               day=1)
        cmonth_str = current_month.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                account = month_item.get('account')
                self.assertEqual(account, self.payer_account_id)
                self.assertIsInstance(month_item.get('services'), list)
