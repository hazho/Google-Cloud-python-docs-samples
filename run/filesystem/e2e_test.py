# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This sample creates a secure two-service application running on Cloud Run.
# This test builds and deploys the two secure services
# to test that they interact properly together.

import backoff
import datetime
import os
import subprocess
from urllib import request
import uuid

import pytest

# Unique suffix to create distinct service names
SUFFIX = uuid.uuid4().hex
PROJECT = os.environ['GOOGLE_CLOUD_PROJECT']

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def gcloud_cli(command):
    """
    Runs the gcloud CLI with given options, parses the json formatted output
    and returns the resulting Python object.
    Usage: gcloud_cli(options)
        options: command line options
    Example:
        result = gcloud_cli("app deploy --no-promote")
        print(f"Deployed version {result['versions'][0]['id']}")
    Raises Exception with the stderr output of the last attempt on failure.
    """
    output = subprocess.run(
        f"gcloud {command} --quiet --format=json",
        capture_output=True,
        shell=True,
        check=True,
    )
    try:
        entries = json.loads(output.stdout)
        return entries
    except Exception:
        print("Failed to read log")
        print(f"gcloud stderr was {output.stderr}")

    raise Exception(output.stderr)

@pytest.fixture
def deployed_service():
    # Deploy image to Cloud Run
    service_name = f'filesystem-{SUFFIX}'
    connector = os.environ['CONNECTOR']
    ip_address = os.environ['IP_ADDRESS']

    subprocess.check_call(
        [
            'gcloud',
            'builds',
            'submit',
            '--config',
            'cloudbuild.yaml',
            '--project',
            PROJECT,
            f'--substitutions=_SERVICE_NAME={service_name},_FILESTORE_IP_ADDRESS={ip_address},_CONNECTOR={connector}'
        ]
    )

    yield service_name

    subprocess.check_call(
        [
            'gcloud',
            'run',
            'services',
            'delete',
            service_name,
            '--region=us-central1',
            '--platform=managed',
            '--quiet',
            "--async",
            '--project',
            PROJECT,
        ]
    )


@pytest.fixture
def service_url_auth_token(deployed_service):
    # Get Cloud Run service URL and auth token
    service_url = (
        subprocess.run(
            [
                'gcloud',
                'run',
                'services',
                'describe',
                deployed_service,
                '--region=us-central1',
                '--platform=managed',
                '--format=value(status.url)',
                '--project',
                PROJECT,
            ],
            stdout=subprocess.PIPE,
            check=True,
        )
        .stdout.strip()
        .decode()
    )
    auth_token = (
        subprocess.run(
            ['gcloud', 'auth', 'print-identity-token'],
            stdout=subprocess.PIPE,
            check=True,
        )
        .stdout.strip()
        .decode()
    )

    yield service_url, auth_token

    # no deletion needed


def test_end_to_end(service_url_auth_token):
    service_url, auth_token = service_url_auth_token
    # Non mnt directory
    req = request.Request(
        service_url, headers={'Authorization': f'Bearer {auth_token}'}
    )
    response = request.urlopen(req)
    assert response.status == 200

    # Mnt directory
    mnt_url = f'{service_url}/mnt/nfs/filestore'
    req = request.Request(
        mnt_url, headers={'Authorization': f'Bearer {auth_token}'}
    )
    response = request.urlopen(req)
    assert response.status == 200

    date = datetime.datetime.utcnow()
    body = response.read()
    assert '{dt:%a}-{dt:%b}-{dt:%d}-{dt:%H}'.format(dt=date) in body.decode()
