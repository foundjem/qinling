# Copyright 2018 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
import requests
from tempest.lib import decorators

from qinling_tempest_plugin.tests import base


class WebhooksTest(base.BaseQinlingTest):
    name_prefix = 'WebhooksTest'

    def setUp(self):
        super(WebhooksTest, self).setUp()
        self.await_runtime_available(self.runtime_id)
        self.function_id = self.create_function()

    @decorators.idempotent_id('37DCD022-32D6-48D1-B90C-31D605DBE53B')
    def test_webhook_invoke(self):
        webhook_id, url = self.create_webhook()
        resp = requests.post(url, data={'name': 'qinling'}, verify=False)
        self.assertEqual(202, resp.status_code)
        resp_exec_id = resp.json().get('execution_id')
        self.addCleanup(self.client.delete_resource, 'executions',
                        resp_exec_id, ignore_notfound=True)

        resp, body = self.client.get_resources(
            'executions',
            {'description': 'has:%s' % webhook_id}
        )
        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['executions']))
        exec_id = body['executions'][0]['id']
        self.assertEqual(resp_exec_id, exec_id)
        self.await_execution_success(exec_id)

        resp, body = self.client.get_execution_log(exec_id)
        self.assertEqual(200, resp.status)
        self.assertIn('qinling', body)

    @decorators.idempotent_id('8e6e4f76-f748-11e7-8ec3-00224d6b7bc1')
    def test_get_all_admin(self):
        """Admin user can get webhooks of other projects"""
        webhook_id, _ = self.create_webhook()

        resp, body = self.admin_client.get_resources(
            'webhooks?all_projects=true'
        )
        self.assertEqual(200, resp.status)
        self.assertIn(
            webhook_id,
            [item['id'] for item in body['webhooks']]
        )
