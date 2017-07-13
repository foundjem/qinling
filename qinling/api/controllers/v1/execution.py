# Copyright 2017 Catalyst IT Limited
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

from oslo_log import log as logging
from pecan import rest
import requests
import wsmeext.pecan as wsme_pecan

from qinling.api.controllers.v1 import resources
from qinling.api.controllers.v1 import types
from qinling.db import api as db_api
from qinling import exceptions as exc
from qinling import rpc
from qinling import status
from qinling.utils import rest_utils

LOG = logging.getLogger(__name__)


class ExecutionsController(rest.RestController):
    def __init__(self, *args, **kwargs):
        self.engine_client = rpc.get_engine_client()

        super(ExecutionsController, self).__init__(*args, **kwargs)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        resources.Execution,
        body=resources.Execution,
        status_code=201
    )
    def post(self, execution):
        params = execution.to_dict()

        LOG.info("Creating execution. [execution=%s]", params)

        function_id = params['function_id']
        is_sync = params.get('sync', True)
        func_url = None

        with db_api.transaction():
            func_db = db_api.get_function(function_id)

            # Increase function invoke count, the updated_at field will be also
            # updated.
            func_db.count = func_db.count + 1

            try:
                # Check if the service url is existing.
                mapping_db = db_api.get_function_service_mapping(function_id)
                LOG.info('Found Service url for function: %s', function_id)

                func_url = '%s/execute' % mapping_db.service_url
                LOG.info('Invoke function %s, url: %s', function_id, func_url)
            except exc.DBEntityNotFoundError:
                pass

            if func_url:
                r = requests.post(func_url, json=params.get('input'))
                params.update(
                    {'status': 'success', 'output': {'result': r.json()}}
                )
            else:
                runtime_id = func_db.runtime_id
                runtime_db = db_api.get_runtime(runtime_id)
                if runtime_db.status != status.AVAILABLE:
                    raise exc.RuntimeNotAvailableException(
                        'Runtime %s is not available.' % runtime_id
                    )

                params.update({'status': status.RUNNING})

            db_model = db_api.create_execution(params)

        if not func_url:
            self.engine_client.create_execution(
                db_model.id, function_id, runtime_id,
                input=params.get('input'),
                is_sync=is_sync
            )

        if is_sync:
            db_model = db_api.get_execution(db_model.id)

        return resources.Execution.from_dict(db_model.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Executions)
    def get_all(self):
        LOG.info("Get all executions.")

        executions = [resources.Execution.from_dict(db_model.to_dict())
                      for db_model in db_api.get_executions()]

        return resources.Executions(executions=executions)

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Execution, types.uuid)
    def get(self, id):
        LOG.info("Fetch execution [id=%s]", id)

        execution_db = db_api.get_execution(id)

        return resources.Execution.from_dict(execution_db.to_dict())

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(None, types.uuid, status_code=204)
    def delete(self, id):
        """Delete the specified Execution."""
        LOG.info("Delete execution [id=%s]", id)

        return db_api.delete_execution(id)
