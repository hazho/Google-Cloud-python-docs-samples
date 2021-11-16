# Make a temp directory - copy all python files
# remove tests
# gsutil cp what's left

import os
import tempfile
from shutil import copytree, ignore_patterns
import glob
# Imports the Google Cloud client library
from google.cloud import storage


def _create_dags_list(dags_directory):
    temp_dir = tempfile.mkdtemp()

    # ignore non-DAG Python files
    files_to_ignore = ignore_patterns("__init__.py", "*_test.py")

    # Copy everything but the ignored files to a temp directory
    copytree(dags_directory, f"{temp_dir}/", ignore=files_to_ignore, dirs_exist_ok=True)

    # The only Python files left in our temp directory are DAG files
    # so we can exclude all non Python files
    dags = glob.glob(f"{temp_dir}/*.py")
    return (temp_dir, dags)

def upload_dags_to_composer(dags_directory, bucket_name):
    temp_dir, dags = _create_dags_list(dags_directory)
    print(temp_dir, dags)
    # Note - the GCS client library does not currently support batch requests on uploads
    # if you have a large number of files, consider using
    # the Python subprocess module to run gsutil -m cp -r on your dags
    # See https://cloud.google.com/storage/docs/gsutil/commands/cp for more info

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    for dag in dags:
        # Remove path to temp dir
        dag = dag.replace(f"{temp_dir}/", "")
        print(dag)
        #Upload to your bucket
        blob = bucket.blob(dag)
        blob.upload_from_string(dag)
        print(f"File {dag} uploaded to {bucket_name}/{dag}.")

if __name__ == "__main__":
    DAGS_DIRECTORY = "../dags/"
    BUCKET="your-bucket"
    upload_dags_to_composer(DAGS_DIRECTORY, BUCKET)



